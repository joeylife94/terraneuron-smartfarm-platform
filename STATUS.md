# TerraNeuron — Implementation Status

> **Last updated:** 2026-07-17
> **Scope of this document:** the single source of truth for what is actually implemented
> in the current codebase. It supersedes the historical `docs/PROJECT_STATUS.md`,
> `AUDIT_REPORT.md`, and `docs/IMPLEMENTATION_GAPS.md`, which described an earlier repository state and contradicted
> the current code.

This is an architecture prototype that demonstrates production-grade patterns (microservices,
Kafka, CloudEvents, human-in-the-loop safety). It is **not** a production deployment. The
notes below are deliberately factual and verified against the current `main`-derived code.

---

## Implemented / enforced

- **RBAC is enforced** in terra-ops via
  [`SecurityConfig`](services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java):
  approve/reject endpoints require `ADMIN`/`OPERATOR`, read endpoints require an authenticated
  role, and `anyRequest().authenticated()` is the default. Covered by `SecurityConfigTest`.
- **JWT authentication** is wired (`JwtTokenProvider`, `JwtAuthenticationFilter`). The signing
  key is sourced from `JWT_SECRET` with **no insecure in-repo fallback**
  (`jwt.secret=${JWT_SECRET}`).
- **Interactive users are authenticated from MySQL.** `AuthController` delegates to
  `UserAuthenticationService`, which verifies BCrypt hashes, rejects disabled/misconfigured
  accounts, records successful login time, and reloads enabled state and roles on refresh.
  Access and refresh JWTs have enforced, non-interchangeable type claims.
- **Human-in-the-loop approval flow** is implemented and now correct: a PENDING plan that
  requires approval can be approved and proceeds to execution. See
  [`ActionPlanService.approvePlan`](services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java).
- **4-layer SafetyValidator** runs on every approval (see advisory note below).
- **Runtime JSON Schema validation** is enforced for canonical CloudEvents on all four ingress
  paths. Both services load the packaged canonical schemas from `docs/contracts`; terra-ops
  validates processed insights, action plans, and command feedback, while terra-sense validates
  commands after normalizing legacy string parameters.
- **Kafka consumers** persist action plans and insights to MySQL; approved/executed plans are
  published to the `terra.control.command` topic.
- **Command and feedback event contracts are documented** as Draft 7 JSON Schemas for
  `terra.ops.command.execute` on `terra.control.command` and
  `terra.sense.command.feedback` on `terra.control.feedback`. A unit test loads every contract
  schema and validates all embedded examples. Command `parameters` are published as an object;
  terra-sense retains support for the legacy JSON-string representation.
- **Kafka consumer retry and dead-letter handling** is implemented for all three terra-ops
  listeners. A shared `DefaultErrorHandler` retries failures twice with a fixed one-second
  backoff, then `DeadLetterPublishingRecoverer` publishes the record to `<source-topic>.DLT`.
  The three DLTs are declared through `KafkaAdmin`, and listener failures now propagate to the
  container. Unit tests cover bounded recovery, DLT naming, failure propagation, and the insight
  happy path.
- **terra-sense** contains the command/feedback and persistence wiring
  (`DeviceCommandConsumer`, `InfluxDbWriterService`, `MqttGatewayService`, plus their config
  classes). These are present and configured. *(Full end-to-end runtime is not re-verified in
  this PR — see Known gaps.)*
- **CI exists:** `.github/workflows/ci-cd.yml` and `.github/workflows/security-scan.yml`.
  The reusable Trivy workflow uploads a complete all-severity SARIF report and separately
  blocks fixable HIGH/CRITICAL dependency vulnerabilities on every PR and `main` push.
- **Tests exist:** terra-ops has unit tests for security, event validation, insight parsing,
  the SafetyValidator, and the approval lifecycle.

## Partially implemented / advisory

- **SafetyValidator layers 2 (Context) and 4 (Device State) are advisory/warning-only.** They
  emit warnings but never produce blocking errors, so they cannot fail validation today. Only
  **layer 1 (Logical)** and **layer 3 (Permission)** are enforced (blocking).
- **Permission layer is structural, not identity-based.** Layer 3 checks plan status, the
  `requiresApproval` flag, and approver metadata. Real RBAC/ownership/device-access checks are
  marked `TODO` and are not yet implemented inside the validator (HTTP-layer RBAC is enforced
  separately by `SecurityConfig`).
- **Action `parameters` are stored as a JSON string** on the `ActionPlan` entity rather than a
  typed/queryable column.

## Known gaps (out of scope for this PR)

- **Docker Compose startup is covered by the repository E2E smoke test**, but production-like
  resilience and external-service behavior are not exhaustively verified.
- **Refresh tokens remain stateless:** they are not persisted, rotated, or individually
  revocable. Disabling an account blocks login/refresh/validate immediately, while an already
  issued access token remains valid on protected APIs until expiry.
- **Account administration and production secrets management** beyond externally supplied
  `JWT_SECRET` are not implemented. The seeded users are local Compose/E2E fixtures only.

## Recently fixed (core TerraNeuron audit findings)

- **Approval/safety lifecycle bug:** `approvePlan()` previously ran the SafetyValidator while
  the plan was still `PENDING`, so layer 3 ("requires human approval") auto-rejected every
  normal plan. Approval metadata (status `APPROVED`, approver, timestamp) is now set **before**
  validation, so a valid human approval succeeds while invalid plans are still rejected.
- **Added focused tests:** `SafetyValidatorTest` (layer behavior) and
  `ActionPlanServiceApprovalTest` (approval happy path, rejection path, audit path).
- **Removed unused DTOs:** `ActionPlanDto` and `CloudEventsEnvelope` were never referenced by
  runtime or tests; the actual path is raw `Map` + `ActionPlanEventValidator`. Contract docs
  updated to match.
- **Retired stale audit docs** (`AUDIT_REPORT.md`, `docs/IMPLEMENTATION_GAPS.md`) in favor of
  this document.

## Recently fixed (PR #7: "add Kafka retry and DLQ handling")

- **Listener exceptions now propagate** from the action-plan, insight, and command-feedback
  consumers instead of being logged and swallowed.
- **Bounded retry and dead-letter recovery** now retries each failed record twice and publishes
  exhausted records to the corresponding `.DLT` topic. Consumer auto-commit is explicitly
  disabled and record acknowledgment is explicit.

## Recently fixed (PR #8: "add command and feedback schemas")

- **Added command and feedback JSON Schemas** matching the live terra-ops → terra-sense command
  request and terra-sense → terra-ops feedback paths.
- **Added schema/example consistency coverage** for every contract file. Runtime enforcement
  was subsequently added in PR #11.
- **Normalized command `parameters` at publication** from the entity's stored JSON text to a
  JSON object and included `farm_id` explicitly in the command payload. The terra-sense
  consumer remains backward-compatible with JSON-string parameters.

## Recently fixed (PR #10: "persist insight trace fields and audit detection")

- **Insight metadata is now persisted:** trace, asset, sensor, severity, raw value, confidence,
  and RAG context fields parsed from canonical CloudEvents are retained on the insight entity;
  available sensor/severity/value/confidence fields are also retained for legacy events.
- **Insight detection is now recorded in audit logs** after the insight is saved, using the
  persisted trace ID or a saved-insight-ID fallback for legacy events without one.

## Recently fixed (PR #11: "add runtime schema validation")

- **Canonical CloudEvents are runtime-validated** against the corresponding schemas in
  `docs/contracts` before domain parsing or processing.
- **Validation failures propagate** to the listener container instead of being caught and
  skipped. terra-ops validation failures propagate to the existing retry/DLT handling.
  terra-sense command validation failures propagate to the listener container; no FAILED feedback
  is emitted for schema-invalid commands, and no terra-sense DLT is introduced in this PR.
- **Legacy compatibility remains intact:** legacy flat insight events are still parsed without
  claiming schema validation, and legacy JSON-string command parameters are normalized to an
  object before command-schema validation.

## Recommended next PRs

1. Promote SafetyValidator layers 2/4 from advisory warnings to enforced checks where the
   domain requires hard gating.
2. Add refresh-token persistence/rotation and an account administration or external identity
   provider boundary.

## Recently fixed (PR #37: database-backed authentication)

- Removed the hardcoded plaintext user map from `AuthController`; login now verifies the
  MySQL `users.password_hash` value with BCrypt and records `last_login`.
- Added fail-closed account and role validation plus dummy BCrypt work for unknown usernames.
- Added explicit access/refresh token type claims and rejected cross-use at the refresh endpoint
  and protected API filter.
- Added JPA, service, seed-hash contract, MVC security, and Docker E2E coverage.
