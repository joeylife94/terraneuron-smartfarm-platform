# Terra-Ops database-backed authentication

Terra-Ops authenticates interactive users from the MySQL `users` table. Raw
passwords are never stored: login compares the submitted password with the
account's BCrypt hash through Spring Security's `PasswordEncoder`.

## Account contract

Each account contains:

- a normalized lowercase `username`;
- a BCrypt `password_hash`;
- a comma-separated subset of `ROLE_ADMIN`, `ROLE_OPERATOR`, and `ROLE_VIEWER`;
- an `enabled` flag;
- `last_login` and lifecycle timestamps.

Unknown usernames execute a dummy BCrypt comparison before rejection. Disabled
accounts, invalid hashes, empty roles, and unknown roles all fail closed with the
same public login error. Password hashes are excluded from the entity's string
representation.

Successful login updates `last_login` and returns a typed access token plus a
typed refresh token. Access tokens cannot be used at `/api/auth/refresh`, and
refresh tokens cannot authenticate protected APIs. Refresh reloads the account's
enabled state and roles from MySQL before issuing a new access token.

## Local bootstrap

`infra/mysql/init.sql` provisions three local Compose/E2E accounts with BCrypt
cost 12. Their credentials remain documented in the API reference for local use.
The seed SQL runs only when MySQL initializes an empty data volume. Existing
volumes are not silently overwritten; apply an explicit account migration or
recreate a disposable local volume when testing the new seed.

Production environments must provision their own users and password hashes. The
repository's demo credentials must not be reused outside local development and
CI.

## Security boundary and remaining limits

- JWT signing material still comes only from the external `JWT_SECRET` setting.
- Refresh tokens are signed and typed but remain stateless. They are not stored,
  rotated, or individually revocable in this change.
- Disabling an account prevents login, refresh, and `/api/auth/validate`
  immediately. An already issued access token remains usable on protected APIs
  until its configured expiry because request authentication is intentionally
  stateless.
- Production transport security, secret management, account administration,
  password reset, MFA, and refresh-token rotation remain deployment/application
  responsibilities outside this PR.

## Verification

Unit tests cover credential validation, disabled accounts, role validation,
dummy BCrypt work, typed JWT separation, and JPA persistence. A seed contract
test verifies all three documented local passwords against the committed BCrypt
hashes. Docker E2E logs in through MySQL, rejects an invalid password, rejects
token-type substitution, refreshes an access token, and validates it.
