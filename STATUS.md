# TerraNeuron — Implementation Status

> **Last updated:** 2026-09-02  
> **Status:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — PROGRESSION ACTIVE`  
> **Authority:** authoritative implementation status / execution contract for this repository  
> **Proof v1.0 implementation baseline SHA:** `7ef9315890f1e2c06345bce94fb3334c2cff1c0e`  
> **Current accepted progression main SHA before this STATUS reconciliation:** `b6feb62f72d7ce8bb1a47b8eba298a70c02fc1ca`

When documents disagree, use:

`current main code / executable evidence → STATUS.md → README.md / historical audits / PR descriptions / previous agent reports`

Proof v1.0 remains an accepted bounded software checkpoint. `FREEZE` freezes that accepted version; it does not prevent later bounded progression. Progression must preserve all explicit non-claims and must not retroactively broaden the v1.0 acceptance boundary.

## Accepted v1.0 baseline

Human Review completed on 2026-08-22 with result:

`PASS — FREEZE APPROVED`

The accepted v1.0 buyer-facing boundary remains unchanged: a production-oriented event-driven smart-farm architecture prototype with executable neural-flow and command-lifecycle software Proof, Dashboard BFF authentication propagation under the verified boundary, persisted security/session controls, service-JWT boundaries, rate limiting, transactional outbox, retry/DLQ, schema validation, observability, dependency scanning, and software safety-gate behavior under the implemented policy boundary.

## Progression milestone — duplicate terminal ACK idempotency

Issue #51 / PR #52 extended the existing synthetic Compose command-lifecycle Golden Path with bounded executable evidence for duplicate terminal device ACK handling.

### Actually Executed / Verified

- PR #52 exact head `7839bd0b1a902b69c53c097b6ac38bd7045bc49e` passed `CI/CD Pipeline` run #265;
- PR #52 was squash-merged as `03c3b172784caabd37d0edc54c49a9c0549471fc` and Issue #51 closed completed;
- within the synthetic software boundary, duplicate terminal ACK processing did not regress `EXECUTED`, change `commandId`, or change `DEVICE_CONFIRMED`.

## Progression milestone — late terminal ACK recovery after ACK timeout

Issue #53 / PR #54 added bounded executable software recovery Proof for:

`DELIVERED → ACK_TIMEOUT → delayed correlated EXECUTED ACK → EXECUTED / DEVICE_CONFIRMED_LATE`

### Actually Executed / Verified

- PR #54 exact head `a95357baa59ba0eb862670315be0a00a10412519` passed `Late ACK Recovery Proof` run #6 and `CI/CD Pipeline` run #273;
- PR #54 was squash-merged with expected-head guard as `cfb41521639454099287c588a8f983125bd7fcdc` and Issue #53 closed completed;
- within the synthetic Compose boundary, delayed correlated terminal ACK recovery retained the same `commandId`, produced `DEVICE_CONFIRMED_LATE`, and preserved terminal-state idempotency on replay.

## Progression milestone — terminal ACK recovery across Terra-Ops restart

Issue #55 / PR #56 added one bounded synthetic service-restart Proof for a terminal device ACK published while Terra-Ops is temporarily down.

### Actually Executed / Verified

- PR #56 exact head `8616554c9dfb7db44736645daf5b517adf0ab8b6` passed `Terra-Ops Restart ACK Recovery Proof` run #1, `CI/CD Pipeline` run #276, and `Late ACK Recovery Proof` run #9;
- PR #56 was squash-merged with expected-head guard as `a747ae679ea85d23853c924131c9af601d052983` and Issue #55 closed completed;
- within the synthetic Compose software boundary, a persisted plan reached `DELIVERED`, a correlated terminal `EXECUTED` ACK published while Terra-Ops was down remained recoverable through the running integration path, the same plan reached `EXECUTED` with its original `commandId` after Terra-Ops restart, and replay preserved terminal-state idempotency.

## Progression milestone — terminal ACK recovery across Kafka broker restart

Issue #57 / PR #58 added one bounded synthetic broker-interruption Proof for an already-persisted command plan while Kafka is temporarily unavailable.

### Changed / Actually Executed / Verified

- added `tests/kafka-restart-ack-recovery-test.py` and a dedicated exact-head `Kafka Restart ACK Recovery Proof` workflow;
- corrected PR #58 exact head `7de61c4fc30685dcad72bfae730b06bfb05c08cd` passed `Kafka Restart ACK Recovery Proof` run #2, `CI/CD Pipeline` run #280, `Late ACK Recovery Proof` run #13, and `Terra-Ops Restart ACK Recovery Proof` run #5;
- PR #58 was squash-merged with expected-head guard as `b272fa820da7537fc66d4ffa9ecd9f109f1d5040` and Issue #57 closed completed;
- within the executed synthetic Compose software boundary, an already-persisted command plan remained recoverable across a bounded Kafka broker interruption, retained its original `commandId`, reached terminal `EXECUTED` after broker recovery, and preserved terminal-state idempotency on ACK replay.

## Progression milestone — MQTT subscription recovery across broker restart

Issue #59 / PR #60 added bounded executable evidence that the running Terra-Sense integration path can recover its inbound MQTT status subscription after a Mosquitto restart without restarting Terra-Sense.

### Changed / Actually Executed / Verified

- changed `MqttGatewayService` to use `MqttCallbackExtended` and restore configured inbound subscriptions from `connectComplete(...)` after automatic reconnect;
- corrected PR #60 exact head `79a38131a745d7c86b17c69910df814dd5831f5d` passed `MQTT Restart Subscription Recovery Proof` run #2, `CI/CD Pipeline` run #284, `Late ACK Recovery Proof` run #17, `Terra-Ops Restart ACK Recovery Proof` run #9, and `Kafka Restart ACK Recovery Proof` run #6;
- PR #60 was squash-merged as `0be87e0aca592e89f0f58a985d1629bfb5e4d76c` and Issue #59 closed completed;
- within the executed synthetic Compose software boundary, Terra-Sense automatically reconnected after bounded Mosquitto restart without a Terra-Sense restart, restored its inbound status subscription, consumed a correlated terminal `EXECUTED` ACK, reconciled the same persisted plan with the original `commandId`, and preserved terminal-state idempotency on replay.

## Progression milestone — complete plan audit timeline across command lifecycle

Issue #61 / PR #62 strengthened operator/audit usability by making the existing plan audit view include command-side lifecycle rows correlated by the plan's persisted `commandId`, while excluding unrelated commands.

### Changed / Actually Executed / Verified

- extended the plan-history repository query so `GET /api/actions/{planId}/audit` includes plan events plus command events correlated through the same persisted plan/command relationship while preserving chronology and excluding unrelated command rows;
- PR #62 exact head `dad04f4d7c987bd2456d1dd47bea9076e09dde60` passed `CI/CD Pipeline` run #287 plus established recovery/authentication workflows;
- PR #62 was squash-merged with expected-head guard as `c5c19f96c7b3d397da4044fb8121a34bb7d17923` and Issue #61 closed completed;
- within the bounded software/operator boundary, the existing plan audit entry point now exposes one chronological software lifecycle containing plan-side and correlated command-side audit evidence.

## Progression milestone — reproducible bounded software Proof handoff

Issue #63 / PR #64 strengthened deployment/handoff reproducibility so a clean checkout can execute one bounded software-Proof handoff path instead of relying on stale production-sounding documentation.

### Changed

- added `tests/software-proof-handoff.sh`, which validates Compose configuration, starts only the required synthetic stack, waits for MySQL/Terra-Sense/Terra-Ops readiness, executes the existing command-lifecycle Proof, and returns explicit PASS/FAIL;
- the script now supplies an explicit demo-only local `JWT_SECRET` only when the caller did not provide one, allowing the documented one-command handoff to start from a clean checkout without implying production secret handling;
- replaced stale `Production-Validated`, fixed historical success-rate/data-loss/load language in `QUICKSTART.md` with the current bounded software-Proof contract and explicit non-claims;
- added `Software Proof Handoff` workflow pinned to the actual PR head;
- after review identified diagnostics loss on failure, the workflow now retains the Compose stack through diagnostics capture/artifact upload and performs explicit cleanup afterward.

### Actually Executed

- corrected PR #64 exact head: `7e77da339ffe35052794f81b76df945714132967`;
- `Software Proof Handoff` run #3 completed `success` on that exact head;
- `CI/CD Pipeline` run #292 completed `success` on that same exact head;
- `MQTT Restart Subscription Recovery Proof` run #10, `Late ACK Recovery Proof` run #25, `Terra-Ops Restart ACK Recovery Proof` run #17, and `Kafka Restart ACK Recovery Proof` run #14 also completed `success` on the same exact head;
- both inline review blockers were answered against the corrected exact head and resolved;
- PR #64 was squash-merged with expected-head guard as `d3608b12f7e58c95d58d6f16c5ebf108fa9ab5bf`;
- Issue #63 closed as completed.

### Verified

Within the current synthetic Compose software boundary:

- a reviewer/operator can run one repository handoff command from a clean checkout and obtain executable PASS/FAIL evidence for the bounded command-lifecycle software Proof;
- the clean-checkout path does not require an undocumented `.env` solely to satisfy the Compose JWT requirement;
- exact-head CI executes the same handoff script used by the documented human path;
- diagnostics remain capturable before cleanup on CI failures;
- broader CI and established command-recovery regression proofs remained green on the exact merge-candidate head.

## Progression milestone — reusable synthetic MQTT device command/ACK harness

Issue #65 / PR #66 added one reusable synthetic MQTT device actor and executable command→correlated-ACK Proof without claiming physical-device truth.

### Changed / Actually Executed / Verified

- added a reusable synthetic MQTT device actor that announces bounded synthetic state, subscribes only to its configured command topic, validates required farm/asset/plan/command correlation, and emits a terminal `EXECUTED` ACK with the received `commandId`;
- added a bounded executable proof for `PENDING → approval/dispatch → independent synthetic actor consumes command → correlated ACK → same persisted plan EXECUTED / DEVICE_CONFIRMED` plus a dedicated exact-head workflow;
- the first exact head exposed a contract-invalid synthetic `planId`; the same-gap fix changed the harness proof to the authoritative `^plan-[a-z0-9]+$` form rather than broadening scope;
- corrected PR #66 exact head `85cf878af0639b85c8be01d9891b5ee93d23fd49` passed `Synthetic MQTT Device Harness Proof` run #2, `CI/CD Pipeline` run #296, `Kafka Restart ACK Recovery Proof` run #18, `MQTT Restart Subscription Recovery Proof` run #14, `Late ACK Recovery Proof` run #29, `Software Proof Handoff` run #7, and `Terra-Ops Restart ACK Recovery Proof` run #21;
- PR #66 had no submitted reviews or unresolved review threads on the accepted exact head;
- PR #66 was squash-merged with expected-head guard as `92d246025f10d04207cb27f0a52193287b4a3030` and Issue #65 closed completed;
- within the bounded synthetic software boundary, an independent reusable actor can consume the existing MQTT command contract and return a correlated terminal ACK that drives the same persisted plan to `EXECUTED / DEVICE_CONFIRMED`.

## Progression milestone — mismatched MQTT terminal ACK rejection

Issue #67 / PR #68 added bounded executable negative-path evidence that a terminal MQTT status carrying a valid commandId from the wrong asset identity cannot complete another asset's persisted plan.

### Changed / Actually Executed / Verified

- added `tests/mismatched-mqtt-ack-rejection-test.py` and a dedicated exact-head `Mismatched MQTT ACK Rejection Proof` workflow;
- review identified two same-gap races: the negative assertion could run before Terra-Sense consumed the wrong-asset status, and command capture could start approval before the non-retained MQTT subscriber was ready;
- corrected PR #68 exact head `2caac4b45a2a306f7933f4ab52b60ddc694a4b16` waits for the wrong asset's exact `reportedAt` to be observed before asserting the target plan remains non-terminal and uses the established subscriber-readiness barrier before approval/dispatch;
- that exact head passed `Mismatched MQTT ACK Rejection Proof` run #2, `CI/CD Pipeline` run #300, `Synthetic MQTT Device Harness Proof` run #6, `MQTT Restart Subscription Recovery Proof` run #18, `Kafka Restart ACK Recovery Proof` run #22, `Terra-Ops Restart ACK Recovery Proof` run #25, `Software Proof Handoff` run #11, and `Late ACK Recovery Proof` run #33;
- both inline review blockers were answered against the corrected exact head and resolved;
- PR #68 was squash-merged with expected-head guard as `c7aa2571765fb6710fe799a3fd09d4cec3c31178` and Issue #67 closed completed;
- within the bounded synthetic Compose software boundary, a wrong-asset terminal ACK carrying the dispatched commandId did not advance the target plan to terminal success after the mismatched status was actually consumed; a later correctly correlated ACK allowed the same persisted plan to reach `EXECUTED / DEVICE_CONFIRMED` while retaining the original `commandId`.

## Progression milestone — correlated MQTT device failure propagation

Issue #69 / PR #70 added bounded executable evidence that a correctly correlated terminal MQTT device `FAILED` status propagates through the running MQTT → Terra-Sense → Kafka feedback → Terra-Ops path as truthful software execution failure.

### Changed / Actually Executed / Verified

- added `tests/correlated-mqtt-device-failure-test.py` and dedicated exact-head `Correlated MQTT Device Failure Proof` workflow;
- PR #70 exact head `396b964c15282d9384c96cc0285894c921ab5693` passed `Correlated MQTT Device Failure Proof` run #1, `CI/CD Pipeline` run #303, `Late ACK Recovery Proof` run #36, `Kafka Restart ACK Recovery Proof` run #25, `Mismatched MQTT ACK Rejection Proof` run #5, `Software Proof Handoff` run #14, `MQTT Restart Subscription Recovery Proof` run #21, `Synthetic MQTT Device Harness Proof` run #9, and `Terra-Ops Restart ACK Recovery Proof` run #28;
- PR #70 had no submitted reviews or unresolved review threads on the accepted exact head;
- PR #70 was squash-merged with expected-head guard as `b6feb62f72d7ce8bb1a47b8eba298a70c02fc1ca` and Issue #69 closed completed;
- within the bounded synthetic Compose software boundary, a correctly correlated terminal device `FAILED` status drove the same persisted plan to `EXECUTION_FAILED`, retained the original `commandId`, cleared its ACK deadline, and preserved operator-visible `DEVICE_EXECUTION_FAILED` plus the deterministic synthetic device error.

## Not Verified / limitations

All v1.0 non-claims remain in force. The accepted baseline and progression milestones do **not** verify or claim:

- production MQTT client identity, authentication, authorization, or TLS;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, physical-equipment certification, or physical device truth;
- manufacturer/model-specific capability adapters;
- production secrets management/key rotation;
- production HA, backup/restore, DR, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that device-reported or software state equals physical equipment state.

The service/broker restart milestones are bounded synthetic software integration evidence. They do not establish production HA/fault-injection maturity, production network guarantees, or physical-equipment behavior. The audit milestone establishes software/operator trace usability only; it does not establish physical-state truth or production compliance/audit certification. The handoff milestone establishes reproducibility of the bounded synthetic software Proof only; its demo-only local secret is not production secrets-management evidence. The synthetic device harness, mismatched-ACK rejection, and correlated device-failure milestones establish software MQTT contract/correlation/failure-propagation behavior only; they do not establish cryptographic device identity, manufacturer fault semantics, physical-device semantics, actuator behavior, or production MQTT trust.

## Remaining risks

- broader network failure handling beyond the accepted bounded Kafka/MQTT broker-restart cases requires separate executable evidence;
- operator/audit usability can still be strengthened where another concrete delivery gap is demonstrated;
- synthetic device/digital-twin coverage can still be strengthened where a new executable software-Proof gap is concrete and does not imply physical-device truth;
- production security/availability boundaries remain separate from the accepted bounded software Proof;
- production and physical-world trust boundaries remain explicitly outside the accepted software Proof.

## Exact Next Action

- perform a fresh Progression Review against current `main` before selecting another milestone;
- if justified, prefer exactly one bounded milestone in this order: software-level command lifecycle reliability/recovery/idempotency, MQTT/Kafka reproducibility/failure handling, operator observability/audit usability, synthetic device/digital-twin reproducibility, deployment/handoff reproducibility, then material workflow security boundaries;
- require concrete use/show/delivery value, executable acceptance criteria, one-Issue/one-PR scope, and no unresolved product-direction or physical-safety decision;
- do not automatically select production MQTT TLS/identity, manufacturer adapters, HA/secrets/DR/load/fault-injection, physical certification, or unattended-control work;
- if no next milestone is justified, remain enabled in lightweight HOLD/no-mutation mode rather than creating state-only churn.
