# TerraNeuron — Implementation Status

> **Last updated:** 2026-09-01  
> **Status:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — PROGRESSION ACTIVE`  
> **Authority:** authoritative implementation status / execution contract for this repository  
> **Proof v1.0 implementation baseline SHA:** `7ef9315890f1e2c06345bce94fb3334c2cff1c0e`  
> **Current accepted progression main SHA before this STATUS reconciliation:** `c5c19f96c7b3d397da4044fb8121a34bb7d17923`

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

### Changed

- added `tests/kafka-restart-ack-recovery-test.py` and a dedicated `Kafka Restart ACK Recovery Proof` workflow;
- required MySQL/Kafka/application readiness instead of assuming startup/recovery;
- drove a persisted plan to `DELIVERED`, stopped only Kafka while MySQL/MQTT/application state remained available, published a correlated terminal `EXECUTED` ACK through MQTT, restarted Kafka, then verified reconciliation of the same persisted plan;
- replayed the terminal ACK after recovery and verified terminal-state idempotency;
- after review identified that pull-request checkout used GitHub's synthetic merge ref, pinned the dedicated workflow checkout to `${{ github.event.pull_request.head.sha || github.sha }}` so acceptance evidence executes on the actual PR head.

### Actually Executed

- corrected PR #58 exact head: `7de61c4fc30685dcad72bfae730b06bfb05c08cd`;
- `Kafka Restart ACK Recovery Proof` run #2 completed `success` on that exact head;
- `CI/CD Pipeline` run #280 completed `success` on that same exact head;
- `Late ACK Recovery Proof` run #13 and `Terra-Ops Restart ACK Recovery Proof` run #5 also completed `success` on that exact head;
- the review thread about exact-head checkout was addressed and resolved;
- PR #58 was squash-merged with expected-head guard as `b272fa820da7537fc66d4ffa9ecd9f109f1d5040`;
- Issue #57 closed as completed.

### Verified

Within the executed synthetic Compose software boundary:

- an already-persisted command plan remained recoverable across a bounded Kafka broker interruption;
- after broker restart/readiness, the same persisted plan reached terminal `EXECUTED` while retaining its original `commandId`;
- replay of the same terminal ACK preserved terminal-state idempotency;
- the dedicated Kafka recovery proof and broader CI/CD pipeline both passed on the corrected exact merge-candidate head.

## Progression milestone — MQTT subscription recovery across broker restart

Issue #59 / PR #60 added bounded executable evidence that the running Terra-Sense integration path can recover its inbound MQTT status subscription after a Mosquitto restart without restarting Terra-Sense.

### Changed

- changed `MqttGatewayService` to use `MqttCallbackExtended` and restore the configured inbound MQTT subscriptions from `connectComplete(...)` after automatic reconnect;
- added `tests/mqtt-restart-subscription-recovery-test.py` and a dedicated exact-head `MQTT Restart Subscription Recovery Proof` workflow with diagnostics;
- drove a persisted plan to `DELIVERED`, restarted only Mosquitto, required broker recovery plus Terra-Sense automatic reconnect without a Terra-Sense restart, then published a correlated terminal `EXECUTED` status through the restored subscription;
- fixed the proof harness after the first run exposed a missing `command_id` argument to the existing terminal-plan waiter.

### Actually Executed

- corrected PR #60 exact head: `79a38131a745d7c86b17c69910df814dd5831f5d`;
- `MQTT Restart Subscription Recovery Proof` run #2 completed `success` on that exact head;
- `CI/CD Pipeline` run #284 completed `success` on that same exact head;
- `Late ACK Recovery Proof` run #17, `Terra-Ops Restart ACK Recovery Proof` run #9, and `Kafka Restart ACK Recovery Proof` run #6 also completed `success` on that exact head;
- PR #60 was squash-merged as `0be87e0aca592e89f0f58a985d1629bfb5e4d76c`;
- Issue #59 closed as completed.

### Verified

Within the executed synthetic Compose software boundary:

- after a bounded Mosquitto broker restart, Terra-Sense automatically reconnected without a Terra-Sense service restart and restored its inbound status subscription;
- a correlated terminal `EXECUTED` ACK published after broker recovery was consumed through the restored subscription and reconciled the same persisted plan while retaining its original `commandId`;
- replay of the same terminal ACK preserved terminal-state idempotency;
- the dedicated MQTT recovery proof and broader CI/CD pipeline both passed on the corrected exact merge-candidate head.

## Progression milestone — complete plan audit timeline across command lifecycle

Issue #61 / PR #62 strengthened operator/audit usability by making the existing plan audit view include command-side lifecycle rows correlated by the plan's persisted `commandId`, while excluding unrelated commands.

### Changed

- extended the existing plan-history repository query so `GET /api/actions/{planId}/audit` includes both plan events and command events correlated through the same persisted plan/command relationship;
- preserved chronological ordering and kept unrelated command audit rows outside the returned plan timeline;
- added executable JPA coverage for plan event → command timeout → terminal command event ordering and unrelated-command exclusion.

### Actually Executed

- PR #62 exact head: `dad04f4d7c987bd2456d1dd47bea9076e09dde60`;
- `CI/CD Pipeline` run #287 completed `success` on that exact head;
- `Late ACK Recovery Proof` run #20, `Terra-Ops Restart ACK Recovery Proof` run #12, `Kafka Restart ACK Recovery Proof` run #9, `MQTT Restart Subscription Recovery Proof` run #5, and `Dashboard Authentication` run #43 also completed `success` on that same exact head;
- no unresolved inline review threads or submitted review blockers remained;
- PR #62 was squash-merged with expected-head guard as `c5c19f96c7b3d397da4044fb8121a34bb7d17923`;
- Issue #61 closed as completed.

### Verified

Within the bounded software/operator boundary:

- the existing plan audit entry point can expose a single chronological software lifecycle containing both plan-side and correlated command-side audit evidence;
- command lifecycle rows are correlated by the plan's persisted `commandId` rather than by timestamp alone;
- unrelated command rows are excluded by executable repository coverage;
- broader CI and the established command-recovery proofs remained green on the exact merge-candidate head.

## Not Verified / limitations

All v1.0 non-claims remain in force. The accepted baseline and progression milestones do **not** verify or claim:

- production MQTT client identity, authentication, authorization, or TLS;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, physical-equipment certification, or physical device truth;
- manufacturer/model-specific capability adapters;
- production secrets management/key rotation;
- production HA, backup/restore, DR, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that device-reported or software state equals physical equipment state.

The service/broker restart milestones are bounded synthetic software integration evidence. They do not establish production HA/fault-injection maturity, production network guarantees, or physical-equipment behavior. The audit milestone establishes software/operator trace usability only; it does not establish physical-state truth or production compliance/audit certification.

## Remaining risks

- broader network failure handling beyond the accepted bounded Kafka/MQTT broker-restart cases requires separate executable evidence;
- operator/audit usability can still be strengthened where another concrete delivery gap is demonstrated;
- deployment/handoff and production security/availability boundaries remain separate from the accepted bounded software Proof;
- production and physical-world trust boundaries remain explicitly outside the accepted software Proof.

## Exact Next Action

- perform a fresh Progression Review against current `main` before selecting another milestone;
- if justified, prefer exactly one bounded milestone in this order: operator observability/audit usability, synthetic device harness, deployment/handoff reproducibility, then material workflow security boundaries;
- require concrete use/show/delivery value, executable acceptance criteria, one-Issue/one-PR scope, and no unresolved product-direction or physical-safety decision;
- do not automatically select production MQTT TLS/identity, manufacturer adapters, HA/secrets/DR/load/fault-injection, physical certification, or unattended-control work;
- if no next milestone is justified, remain enabled in lightweight HOLD/no-mutation mode rather than creating state-only churn.
