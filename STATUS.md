# TerraNeuron — Implementation Status

> **Last updated:** 2026-07-20  
> **Status:** production-oriented architecture prototype; not a production deployment  
> **Authority:** this document is the single source of truth for repository implementation status.

Historical status and audit documents may describe older repository states. When they conflict with this file or the current code, this file and the current code take precedence.

## Current system boundary

TerraNeuron demonstrates an event-driven smart-farm control platform with:

- Java/Spring Boot ingestion and operations services;
- Python/FastAPI analysis and RAG service;
- Kafka event transport;
- MySQL and InfluxDB persistence;
- Redis command/device-state coordination;
- MQTT device messaging;
- a human approval and audit workflow;
- Prometheus/Grafana observability;
- GitHub Actions build, test, integration and dependency-security gates.

The repository validates production-grade software patterns in a local integration stack. It does not claim production infrastructure, physical equipment certification or unattended autonomous control.

## Implemented and enforced

### Event contracts and processing

- Canonical CloudEvents are runtime-validated against packaged JSON Schemas before domain processing.
- Terra-Ops listeners use bounded retries and publish exhausted records to source-specific dead-letter topics.
- Terra-Cortex uses stable event identifiers, a durable semantic deduplication ledger and Kafka transactional publication.
- Critical Cortex task failures terminate the process rather than allowing partial processing against stale state.
- Terra-Ops creates device commands through a transactional outbox.
- A unique plan-to-outbox constraint prevents duplicate command creation.
- Legacy command payloads and previously persisted outbox rows are reconciled without silently replaying terminal command truth.

### Command delivery and feedback

- Terra-Sense claims command IDs through Redis before dispatch.
- Duplicate Kafka delivery does not produce duplicate MQTT commands.
- MQTT publication success/failure is represented through correlated feedback.
- Device terminal ACKs are correlated to the original command and action plan.
- ACK timeout and late-feedback behavior are represented in the action-plan lifecycle.
- Safety-block terminal feedback can be replayed from Redis completion state when the Kafka command is redelivered.
- Physical device ACK feedback does not have a separate durable outbox; if Kafka publication fails after an ACK, recovery depends on the device sending that ACK again.

### Four-layer approval validation

Terra-Ops evaluates four layers before creating an outbox command:

1. **Logical — blocking:** required identity, action and lifecycle checks.
2. **Context — advisory:** currently records contextual warnings such as a critical plan reduced to `alert_only`; it does not yet contain domain rules that block execution.
3. **Permission — blocking:** requires the expected approval lifecycle and approver metadata. HTTP RBAC is separately enforced by Spring Security.
4. **Device state — blocking for physical actions:** calls the Terra-Sense Device Safety Gate and fails closed.

The exact non-actuating pair `action_category=alert` and `action_type=alert_only` treats physical device state as not applicable. All other identity, contract, approval, outbox and delivery rules still apply.

### Device Safety Gate

Device safety is enforced twice:

- **Approval time:** Terra-Ops calls `POST /internal/device-safety/evaluate` using a short-lived service JWT.
- **Pre-dispatch:** Terra-Sense evaluates the same policy after the Redis command claim and immediately before MQTT publication.

The policy uses shared Redis state keyed by exact `(farmId, assetId)` identity and blocks physical actions when state is:

- missing or stale;
- offline, error, unknown or unrecognized;
- in maintenance mode;
- associated with an unknown or mismatched device type;
- incompatible with the action category or action type;
- missing a supported adjustment parameter.

Approval-time safety failures create the retryable `SAFETY_BLOCKED` state:

- approval identity and time are retained;
- no command ID or outbox row is created;
- the original expiration deadline remains authoritative;
- explicit safety revalidation is required after state recovery;
- a successful revalidation creates exactly one command/outbox pair in the same MySQL transaction.

Pre-dispatch safety failures never call MQTT. Terra-Sense emits bounded, correlated terminal feedback and preserves command idempotency across redelivery.

See [`docs/DEVICE_SAFETY_GATE.md`](docs/DEVICE_SAFETY_GATE.md).

### Authentication and authorization

- Interactive users are loaded from MySQL and passwords are verified using BCrypt.
- Disabled accounts and invalid roles fail closed.
- Access and refresh JWTs carry distinct token types and cannot be substituted for each other.
- Refresh JWTs carry unique token IDs and server-generated rotation-family IDs.
- Refresh sessions are persisted in MySQL; only SHA-256 token digests are stored, never raw refresh JWTs.
- Every successful refresh atomically revokes the presented token and returns a replacement token in the same family.
- A pessimistic row lock prevents two concurrent requests from successfully rotating the same token.
- Reuse of an already-rotated token revokes all remaining active sessions in that token family.
- `POST /api/auth/logout` idempotently revokes one presented refresh-token session.
- Current enabled account state and roles are reloaded before a replacement access/refresh pair is issued.
- Terra-Dashboard authenticates through same-origin Next.js BFF routes; browser JavaScript never receives or stores JWT values.
- Dashboard access and refresh JWTs are held in HttpOnly, SameSite=Strict cookies and protected Terra-Ops calls receive server-injected Bearer authentication.
- The Dashboard BFF rotates a refresh token at most once after a protected request returns `401`, replaces both cookies and retries once.
- Protected Dashboard proxy paths are explicitly allowlisted and state-changing requests enforce same-origin checks.
- Terra-Ops endpoints enforce authenticated access and role-based approval/rejection permissions.
- Cortex → Ops and Ops → Sense use separate service-JWT boundaries with explicit subject, audience, scope and expiry checks.
- CORS origins are explicit; wildcard configuration is not the intended deployment path.

See [`docs/REFRESH_TOKEN_LIFECYCLE.md`](docs/REFRESH_TOKEN_LIFECYCLE.md) and [`docs/DASHBOARD_AUTHENTICATION.md`](docs/DASHBOARD_AUTHENTICATION.md).

### Database ownership

- Flyway is the sole Terra-Ops production schema owner.
- Hibernate uses `ddl-auto=validate` rather than mutating production schema.
- Empty databases install from canonical migrations.
- Compatible pre-Flyway databases are baselined and forward-reconciled.
- Legacy native ENUM columns, action-plan command references and duplicate outbox rows are normalized through versioned migrations.
- Flyway V6 creates the refresh-token session table and its unique identity/hash indexes.
- Compose-only seed users and sample data are isolated from production migrations.

### CI, security and observability

The active CI/CD workflow verifies:

- Terra-Sense and Terra-Ops Gradle builds and tests;
- Terra-Cortex dependency installation, lint and tests;
- Terra-Dashboard production build;
- JSON/YAML and contract consistency checks;
- Prometheus configuration and alert-rule tests;
- Docker Compose startup and the current neural-flow integration script.

A dedicated Dashboard Authentication workflow verifies same-origin login, HttpOnly cookie issuance, authenticated session restoration, protected Terra-Ops proxy access, route allowlisting, logout and post-logout denial against the Compose stack.

Command lifecycle, safety revalidation, MQTT publication and ACK/feedback behavior are verified through focused Terra-Ops and Terra-Sense tests. The current Compose neural-flow script does not exercise those paths end to end.

The reusable Trivy workflow:

- uploads an all-severity SARIF report;
- separately fails CI for fixable HIGH or CRITICAL dependency vulnerabilities;
- runs from the active PR/main pipeline and remains available for scheduled/manual scans.

Prometheus metrics and alerts use bounded labels and avoid raw farm IDs, asset IDs, event IDs, command IDs, payloads and secrets.

## Partially implemented or advisory

- **Context validation remains advisory.** The framework is blocking-capable, but current context rules only generate warnings.
- **Permission validation is lifecycle-oriented.** It validates approval metadata inside the action plan; farm/device ownership policy is not modeled as a domain authorization service.
- **Device ACK feedback durability is incomplete.** Command completion is rolled back when ACK-to-Kafka publication fails, so recovery depends on the physical device repeating the terminal ACK.
- **Action parameters are persisted as JSON text** on the current action-plan entity rather than a typed/queryable database structure.
- **Device capability coverage is conservative and generic.** Manufacturer/model-specific adapters must implement explicit capability resolution.
- **Alert-only delivery is not an acknowledgement system.** The physical safety exemption does not prove that a human received or acted on a notification.

## Known production gaps

### Device and physical safety

- MQTT client authentication, topic authorization and TLS are not yet production-enforced.
- Device-reported status can be forged by an actor with broker access.
- Application freshness checks do not prove physical equipment state.
- The final safety check cannot eliminate a state change between evaluation and actuation.
- Electrical interlocks, emergency stops, local controller limits and certified physical controls remain external requirements.
- Manufacturer/model capability adapters and real-device integration evidence are incomplete.

### Identity and account lifecycle

- Already issued access tokens remain usable until expiry; refresh-token revocation does not immediately revoke an access JWT.
- Global logout, active-session administration and account-wide token revocation are not implemented.
- Expired and revoked refresh-session retention and cleanup require an operational policy.
- Account administration, MFA, password reset and external identity-provider integration are not implemented.
- Dashboard cookie security depends on production HTTPS, trusted proxy headers, CSP and secure deployment configuration.

### Infrastructure and operations

- Production secrets management, automated key rotation and deployment-specific access controls are not implemented in this repository.
- Kafka, Redis, MySQL, InfluxDB, Mosquitto, Prometheus and Grafana are configured as a local/integration stack rather than a highly available production platform.
- Production deployment manifests, backup/restore drills, disaster recovery objectives and runbooks require further work.
- Large-scale load tests, long-duration soak tests and systematic fault-injection evidence are incomplete.

## Documentation authority

- [`README.md`](README.md) — repository overview and local execution
- [`docs/REFRESH_TOKEN_LIFECYCLE.md`](docs/REFRESH_TOKEN_LIFECYCLE.md) — persisted refresh-token rotation and revocation
- [`docs/DASHBOARD_AUTHENTICATION.md`](docs/DASHBOARD_AUTHENTICATION.md) — Dashboard BFF authentication, cookie and proxy behavior
- [`docs/DEVICE_SAFETY_GATE.md`](docs/DEVICE_SAFETY_GATE.md) — enforced device-safety flow, guarantees and limits
- [`docs/ACTION_PROTOCOL.md`](docs/ACTION_PROTOCOL.md) — action/event contracts
- [`docs/TERRA_OPS_SCHEMA_MIGRATIONS.md`](docs/TERRA_OPS_SCHEMA_MIGRATIONS.md) — schema ownership and upgrade behavior
- [`docs/SECURITY_SCANNING.md`](docs/SECURITY_SCANNING.md) — dependency-security policy
- [`AUDIT_REPORT.md`](AUDIT_REPORT.md) — retired historical audit pointer

## Recommended next PRs

1. Add MQTT client identity, topic authorization and TLS deployment contracts.
2. Define manufacturer/model capability adapter boundaries and contract tests.
3. Add production deployment, secrets, high-availability and fault-injection evidence.
4. Add global logout, active-session administration and refresh-session retention policy.
