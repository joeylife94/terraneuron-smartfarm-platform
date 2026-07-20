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

Dashboard client code uses `/api/dashboard-ops` instead of the historical unauthenticated `/api/ops` rewrite.

The BFF:

1. accepts only the allowlisted top-level paths `actions`, `crops`, and `farms`;
2. rejects path traversal and does not expose Terra-Ops `/auth` or `/internal` routes;
3. reads the HttpOnly access cookie on the server;
4. adds `Authorization: Bearer <access-token>` to the Terra-Ops request;
5. forwards only the request method, body and required content type;
6. returns the upstream status and response without exposing session cookies or tokens.

Terra-Ops remains the authorization authority. Dashboard role display or controls are usability features and do not replace Spring Security or controller identity checks.

## Refresh rotation

If the access token is absent or Terra-Ops returns `401 Unauthorized`, the BFF may attempt one refresh rotation with the HttpOnly refresh cookie.

- A successful rotation replaces both cookies and retries the protected request once.
- A failed rotation clears both Dashboard cookies and returns `401`.
- The browser never handles the replacement refresh token.
- The Terra-Ops single-use, replay-detection and token-family guarantees remain unchanged.
- The BFF never loops on repeated `401` responses.

`GET /api/dashboard-auth/session` follows the same validation and one-time rotation behavior so the navigation shell can restore the current user after a page reload.

## Logout

`POST /api/dashboard-auth/logout` forwards the refresh token to Terra-Ops for individual server-side revocation and clears both Dashboard cookies regardless of the upstream result.

Already issued access JWTs remain stateless at Terra-Ops, but clearing the HttpOnly access cookie prevents the Dashboard BFF from sending that token again from the logged-out browser session.

## Cross-site request controls

- Authentication cookies use `SameSite=Strict` and are scoped to `/api`.
- Login, logout and protected mutation requests reject a present `Origin` that does not equal the configured `DASHBOARD_PUBLIC_ORIGIN` or, when unset, the request URL origin.
- The application does not derive the public origin directly from arbitrary `X-Forwarded-*` headers. Production ingress should set `DASHBOARD_PUBLIC_ORIGIN` explicitly and prevent direct access that bypasses the trusted proxy.
- All authentication and protected API responses set `Cache-Control: no-store`.

## Validation

`tests/dashboard-auth-e2e-test.py` runs against the Docker Compose stack and verifies:

- cross-origin login rejection;
- successful login using the Compose-only operator account;
- absence of token values from browser-visible JSON;
- HttpOnly, SameSite and `/api` cookie scope attributes;
- authenticated session validation;
- protected Terra-Ops access through the BFF;
- rejection of non-allowlisted proxy routes;
- logout and post-logout access denial.

The dedicated `Dashboard Authentication` GitHub Actions workflow builds the Compose services and executes this test.

## Limits

- This is not access-token revocation. A copied access JWT remains valid directly against Terra-Ops until expiry.
- Cookies reduce accidental token exposure but cannot protect a compromised Dashboard server or a browser with arbitrary script execution.
- Production HTTPS, CSP, trusted ingress isolation, secret management and key rotation remain deployment responsibilities.
- Global logout, active-session administration, MFA, password reset and external identity providers remain separate work.
