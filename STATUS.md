# TerraNeuron — Implementation Status

> **Last updated:** 2026-06-22
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

- **Kafka DLQ / retry / error-handler is not implemented.** Consumers catch, log, and skip
  malformed events; there is no dead-letter topic or retry policy.
- **Docker Compose / full E2E startup is not repaired or verified here.**
- **No full runtime JSON Schema validation.** Inbound events are checked for the CloudEvents
  envelope shape, not validated against `docs/contracts/*.schema.json`.
- **DB-backed auth and secrets management** beyond `JWT_SECRET` are not implemented.

## Recently fixed (this PR: "address core TerraNeuron audit findings")

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

## Recommended next PRs

1. Kafka DLQ + retry + error-handler for the action-plan and insight consumers.
2. Docker Compose / E2E startup repair and an automated smoke test.
3. Full runtime JSON Schema validation against `docs/contracts/*.schema.json`.
4. DB-backed authentication (replace hardcoded users, hash with BCrypt) and broader secrets
   management.
5. Promote SafetyValidator layers 2/4 from advisory warnings to enforced checks where the
   domain requires hard gating.
