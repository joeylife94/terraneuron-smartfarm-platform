# Internal Service Authentication

TerraNeuron uses separate service-JWT trust domains. Neither credential is a user token, and the signing keys must not be reused.

## Terra-Cortex → Terra-Ops

Terra-Cortex calls the read-only crop conditions API:

- endpoint: `GET /api/farms/{farmId}/optimal-conditions`
- subject: `terra-cortex`
- issuer: `terraneuron-internal`
- audience: `terra-ops`
- token type: `service`
- required scope: `crop:read`
- default lifetime: 60 seconds
- shared secret: `SERVICE_AUTH_JWT_SECRET`

Terra-Ops runs this service-token filter only for the crop conditions route. A valid Cortex token presented to another route cannot inherit the generic authenticated-user rule.

## Terra-Ops → Terra-Sense

Terra-Ops calls the device safety evaluation API before creating a command outbox:

- endpoint: `POST /internal/device-safety/evaluate`
- subject: `terra-ops`
- issuer: `terraneuron-internal`
- audience: `terra-sense`
- token type: `service`
- required scope: `device:safety:evaluate`
- default lifetime: 30 seconds
- accepted maximum lifetime: 60 seconds
- default clock skew: 5 seconds
- shared secret: `DEVICE_SAFETY_JWT_SECRET`

Terra-Sense accepts this credential only for the internal safety POST. The same valid service token receives `403` on other Terra-Sense endpoints. Missing, expired, wrong-subject, wrong-audience, or wrong-scope credentials fail closed and prevent outbox creation.

## Secret handling and rotation

Use independent random values of at least 32 bytes for:

1. user-facing `JWT_SECRET`;
2. Cortex-to-Ops `SERVICE_AUTH_JWT_SECRET`;
3. Ops-to-Sense `DEVICE_SAFETY_JWT_SECRET`.

Store production values in the deployment secret manager, not in source control. The Compose override contains clearly named local-only defaults so CI and local development can start without external secret provisioning.

Both service tokens expire in approximately one minute or less. Rotate one trust domain by updating the matching secret on only its producer and consumer, then restart those two services in a coordinated deployment. Do not use a database password, API key, or user JWT signing key as a service credential.
