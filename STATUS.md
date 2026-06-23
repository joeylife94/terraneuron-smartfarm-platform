# TerraNeuron — Implementation Status

> **Last updated:** 2026-06-23
> **Scope of this document:** the single source of truth for what is actually implemented
> in the current codebase. It supersedes the historical `AUDIT_REPORT.md` and
> `docs/IMPLEMENTATION_GAPS.md`, which described an earlier repository state and contradicted
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
- **Human-in-the-loop approval flow** is implemented and now correct: a PENDING plan that
  requires approval can be approved and proceeds to execution. See
  [`ActionPlanService.approvePlan`](services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java).
- **4-layer SafetyValidator** runs on every approval (see advisory note below).
- **CloudEvents v1.0 envelope validation** for inbound events:
  [`ActionPlanEventValidator`](services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanEventValidator.java)
  and `InsightEventParser`. Both are unit-tested.
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
- **Authentication uses hardcoded demo users.** `AuthController` compares plaintext passwords
  against an in-memory map; the `users` table and `BCryptPasswordEncoder` are not yet wired.
- **Action `parameters` are stored as a JSON string** on the `ActionPlan` entity rather than a
  typed/queryable column.

## Known gaps (out of scope for this PR)

- **Docker Compose startup is covered by the repository E2E smoke test**, but production-like
  resilience and external-service behavior are not exhaustively verified.
- **No full runtime JSON Schema validation.** Inbound events are checked for the CloudEvents
  envelope shape, not validated against `docs/contracts/*.schema.json`.
- **DB-backed auth and secrets management** beyond `JWT_SECRET` are not implemented.

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
- **Added schema/example consistency coverage** for every contract file. This does not add
  runtime JSON Schema validation; that remains a known gap.
- **Normalized command `parameters` at publication** from the entity's stored JSON text to a
  JSON object and included `farm_id` explicitly in the command payload. The terra-sense
  consumer remains backward-compatible with JSON-string parameters.

## Recommended next PRs

1. Full runtime JSON Schema validation against `docs/contracts/*.schema.json`.
2. DB-backed authentication (replace hardcoded users, hash with BCrypt) and broader secrets
   management.
3. Promote SafetyValidator layers 2/4 from advisory warnings to enforced checks where the
   domain requires hard gating.
