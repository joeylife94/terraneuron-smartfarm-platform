# Terra-Cortex → Terra-Ops Service Authentication

Terra-Cortex uses a dedicated HMAC signing key to call the read-only crop conditions API:

- endpoint: `GET /api/farms/{farmId}/optimal-conditions`
- subject: `terra-cortex`
- issuer: `terraneuron-internal`
- audience: `terra-ops`
- token type: `service`
- required scope: `crop:read`
- default lifetime: 60 seconds

The service credential is independent from the user-facing `JWT_SECRET`. Set the same random
`SERVICE_AUTH_JWT_SECRET` value in Terra-Cortex and Terra-Ops. Use at least 32 random bytes and
store it in the deployment secret manager rather than in source control.

The Compose override contains a clearly named local-only default so CI and local development can
start without secret provisioning. Production deployment definitions must override it.

## Authorization boundary

Terra-Ops only runs the service-token filter for the crop conditions GET route. A valid
Terra-Cortex token presented to another route is not authenticated and cannot inherit the generic
`authenticated()` access rule. User JWTs continue to access the endpoint through the existing
ADMIN, OPERATOR, and VIEWER roles.

## Rotation

Because tokens expire after approximately one minute, rotation only requires updating the shared
secret on both services and restarting them in a coordinated deployment. Do not reuse the user JWT
signing key, an API key, or a database password.
