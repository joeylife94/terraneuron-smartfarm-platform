# Dashboard interactive authentication

Terra-Dashboard uses a Next.js backend-for-frontend (BFF) boundary for interactive Terra-Ops authentication. Browser JavaScript never receives or stores the access JWT or refresh JWT.

## Architecture

The browser calls same-origin Dashboard endpoints:

- `POST /api/dashboard-auth/login`
- `GET /api/dashboard-auth/session`
- `POST /api/dashboard-auth/logout`
- `/api/dashboard-ops/{allowed-path}` for protected Terra-Ops reads and mutations

Next.js route handlers call Terra-Ops through the server-only `TERRA_OPS_INTERNAL_URL`. The default Compose value is `http://terra-ops:8080/api`. This value must not use a `NEXT_PUBLIC_` prefix.

`DASHBOARD_PUBLIC_ORIGIN` may define the single externally visible Dashboard origin, for example `https://dashboard.example.com`. When it is absent, the BFF uses the request URL origin. The configured value must be an absolute HTTP(S) origin and must remain server-only.

The historical `/api/ops/:path*` rewrite is removed. Protected Terra-Ops traffic must pass through the allowlisted BFF route, so `/api/ops/auth/login` cannot return raw tokens to browser code.

## Login

1. The browser submits username and password to the same-origin Dashboard login route.
2. The BFF forwards the credentials to `POST /api/auth/login` in Terra-Ops.
3. Terra-Ops authenticates the MySQL account and issues an access/refresh pair.
4. The BFF removes both token values from the browser-visible response.
5. The tokens are stored as separate cookies with:
   - `HttpOnly`;
   - `SameSite=Strict`;
   - `Path=/api`, limiting delivery to Dashboard API handlers;
   - expiry derived from the Terra-Ops token response;
   - `Secure` when the public Dashboard origin uses HTTPS.
6. The browser receives only the authenticated username and roles.

Passwords and raw tokens are not logged by the Dashboard implementation.

## Protected Terra-Ops proxy

Dashboard client code uses `/api/dashboard-ops` instead of the removed unauthenticated `/api/ops` rewrite.

The BFF:

1. accepts only the allowlisted top-level paths `actions`, `crops`, and `farms`;
2. rejects path traversal and does not expose Terra-Ops `/auth` or `/internal` routes;
3. reads the HttpOnly access cookie on the server;
4. adds `Authorization: Bearer <access-token>` to the Terra-Ops request;
5. forwards only the request method, body and required content type;
6. returns the upstream status and response without exposing session cookies or tokens;
7. never rotates a refresh token inside the protected proxy.

Terra-Ops remains the authorization authority. Dashboard role display or controls are usability features and do not replace Spring Security or controller identity checks.

## Serialized refresh rotation

When a protected request returns `401 Unauthorized`, Dashboard client code restores the session through `GET /api/dashboard-auth/session` and retries the original protected request once.

Refresh is serialized at two levels:

- one module-level Promise coalesces concurrent requests in the current browser tab;
- the same-origin Web Locks API serializes session restoration across tabs;
- the Dashboard server coalesces simultaneous requests carrying the same refresh-token digest while the Terra-Ops rotation is in flight.

The protected proxy itself retains the refresh cookie and returns `401`; it cannot independently race to rotate the same single-use credential.

A successful session restoration:

1. validates the current access token when present;
2. otherwise rotates the HttpOnly refresh token through Terra-Ops;
3. replaces both cookies;
4. returns only the current username and roles;
5. allows the client to retry the original request once.

A failed rotation clears the Dashboard cookies and leaves the protected request unauthorized. The browser never handles the replacement refresh token, and Terra-Ops remains the owner of replay detection and token-family revocation.

The server-side in-flight map is process-local defense in depth and is removed immediately after the rotation settles. A multi-replica production deployment must preserve the supported browser serialization path and should evaluate shared BFF session coordination or opaque server-side sessions.

## Logout

`POST /api/dashboard-auth/logout` clears both Dashboard cookies and attempts individual server-side revocation through Terra-Ops with a 1.5-second timeout. An unavailable Terra-Ops instance cannot leave the browser waiting indefinitely with unchanged cookies.

Already issued access JWTs remain stateless at Terra-Ops, but clearing the HttpOnly access cookie prevents the Dashboard BFF from sending that token again from the logged-out browser session.

## Cross-site request controls

- Authentication cookies use `SameSite=Strict` and are scoped to `/api`.
- Login, logout and protected mutation requests reject a present `Origin` that does not equal the configured `DASHBOARD_PUBLIC_ORIGIN` or, when unset, the request URL origin.
- The application does not derive the public origin directly from arbitrary `X-Forwarded-*` headers. Production ingress should set `DASHBOARD_PUBLIC_ORIGIN` explicitly and prevent direct access that bypasses the trusted proxy.
- All authentication and protected API responses set `Cache-Control: no-store`.

## Validation

`tests/dashboard-auth-e2e-test.py` runs against the Docker Compose stack and verifies:

- cross-origin login rejection;
- removal of the legacy `/api/ops/auth/login` bypass;
- successful login using the Compose-only operator account;
- absence of token values from browser-visible JSON;
- HttpOnly, SameSite and `/api` cookie scope attributes;
- authenticated session validation;
- protected Terra-Ops access through the BFF;
- rejection of non-allowlisted proxy routes;
- access-cookie loss producing `401` without consuming the refresh token;
- session-route rotation followed by a successful protected-request retry;
- logout and post-logout access denial.

The dedicated `Dashboard Authentication` GitHub Actions workflow builds the Compose services and executes this test.

## Limits

- This is not access-token revocation. A copied access JWT remains valid directly against Terra-Ops until expiry.
- Cookies reduce accidental token exposure but cannot protect a compromised Dashboard server or a browser with arbitrary script execution.
- Browsers without Web Locks receive same-tab Promise coalescing but do not have the same cross-tab coordination guarantee.
- Production HTTPS, CSP, trusted ingress isolation, secret management and key rotation remain deployment responsibilities.
- Global logout, active-session administration, MFA, password reset and external identity providers remain separate work.
