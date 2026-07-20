# Refresh token lifecycle

Terra-Ops persists refresh-token sessions in MySQL and treats every refresh token as single-use.

## Login

`POST /api/auth/login` returns:

- a stateless access JWT;
- a refresh JWT with a unique `jti` token identifier;
- a server-generated rotation-family identifier;
- access and refresh expiry durations.

The raw refresh JWT is returned to the client once and is never stored in MySQL. Terra-Ops stores only a SHA-256 digest together with the token ID, family ID, username, issue time and expiry time.

## Rotation

`POST /api/auth/refresh` consumes the presented refresh token and returns both a new access token and a new refresh token.

Rotation is transactional:

1. Verify the JWT signature, expiry, token type, subject, `jti` and family claim.
2. Lock the matching `refresh_token_sessions` row with a pessimistic database lock.
3. Compare the presented token digest and identity claims with the stored session.
4. Reload the current enabled account and roles.
5. Revoke the current row with reason `ROTATED`.
6. Insert one replacement row in the same token family.
7. Return the replacement refresh token.

Two concurrent refresh requests using the same token cannot both rotate it. The first transaction succeeds. When the second transaction obtains the row lock, it observes the already-rotated token and triggers reuse handling.

Clients must replace their stored refresh token after every successful refresh response. The previous token is no longer valid.

## Reuse detection

Presenting a token that was already revoked with reason `ROTATED` is treated as suspected token theft or replay. Terra-Ops revokes every still-active session in that token family with reason `REUSE_DETECTED`.

A digest, username or family mismatch also fails closed and revokes the active family with reason `INTEGRITY_FAILURE`.

Disabling or deleting the account before rotation revokes the active family with reason `ACCOUNT_UNAVAILABLE`.

## Individual revocation

`POST /api/auth/logout` accepts the refresh token body used by the refresh endpoint and idempotently revokes only that session with reason `LOGOUT`.

The endpoint returns `204 No Content` and deliberately does not disclose whether the token existed, was already revoked or was invalid.

Multiple login sessions use separate family IDs. Logging out one refresh token does not revoke unrelated sessions.

## Storage

Flyway V6 creates `refresh_token_sessions` with:

- unique token ID and token digest;
- username and rotation family indexes;
- issue, expiry and revocation timestamps;
- revocation reason and replacement-token correlation;
- no raw JWT column.

Expired and revoked rows are retained as security history. A future retention job may delete rows after the operational audit window.

## Guarantees

- Raw refresh JWTs are not persisted.
- A refresh token can produce at most one replacement under concurrent requests.
- Successful refresh always returns a replacement refresh token.
- Reuse of a rotated token invalidates the remaining family.
- Logout revocation is individual and idempotent.
- Current account state and roles are reloaded before issuing replacement tokens.

## Limits

- Access JWTs remain stateless and usable until expiry; refresh-token revocation does not immediately revoke an already issued access token.
- Token-family revocation is local to the Terra-Ops database and is not an external identity-provider session.
- Account administration, MFA, password reset and global logout are not implemented.
- Retention and cleanup of expired session rows require an operational policy.
- The JWT signing key still requires external secret management and rotation in a production deployment.
