# TerraNeuron — Implementation Status

> **Last updated:** 2026-09-03  
> **Status:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — PROGRESSION ACTIVE`  
> **Authority:** authoritative implementation status / execution contract for this repository  
> **Proof v1.0 implementation baseline SHA:** `7ef9315890f1e2c06345bce94fb3334c2cff1c0e`  
> **Current accepted progression main SHA before this STATUS reconciliation:** `ef3daf50c7c10412b7fbd120bc0410b1471ec861`

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

## Progression milestone — stale DELIVERED cannot regress terminal device failure

Issue #71 / PR #72 added bounded executable ordering evidence that once a correctly correlated synthetic device failure makes a persisted plan `EXECUTION_FAILED`, a later stale transport `DELIVERED` event for the same command cannot overwrite that stronger terminal truth.

### Changed / Actually Executed / Verified

- added `tests/stale-delivered-after-device-failure-test.py` and dedicated exact-head `Stale DELIVERED After Device Failure Proof` workflow;
- review identified that consumer-group lag alone could false-PASS if the stale event were rejected and dead-lettered; the corrected workflow explicitly verifies `terra.control.feedback.DLT` contains no record after the isolated proof;
- an execution failure in the lag wait was traced to Kafka empty partitions reporting `CURRENT-OFFSET=- / LOG-END-OFFSET=0 / LAG=-`; the same-gap correction treats only those empty partitions as caught up while preserving unknown lag as unsafe for non-empty partitions;
- corrected PR #72 exact head `2ca81fd6c9eac65c8575fbe8c52b429ae18a3db1` passed `Stale DELIVERED After Device Failure Proof` run #3, including the explicit `Verify stale feedback was not dead-lettered` step;
- that exact head also passed `CI/CD Pipeline` run #308, `Mismatched MQTT ACK Rejection Proof` run #10, `MQTT Restart Subscription Recovery Proof` run #26, `Software Proof Handoff` run #19, `Kafka Restart ACK Recovery Proof` run #30, `Correlated MQTT Device Failure Proof` run #6, `Terra-Ops Restart ACK Recovery Proof` run #33, `Late ACK Recovery Proof` run #41, and `Synthetic MQTT Device Harness Proof` run #14;
- the inline review blocker was resolved after corrected exact-head execution evidence;
- PR #72 was squash-merged with expected-head guard as `815933edc25f68d744da73dad689c9e394d50a42` and Issue #71 closed completed;
- within the bounded synthetic software integration path, terminal `EXECUTION_FAILED` truth, original `commandId`, `DEVICE_EXECUTION_FAILED`, the original synthetic device error, and the cleared ACK deadline survived an actually consumed, non-dead-lettered stale `DELIVERED` event for the same command.

## Progression milestone — duplicate terminal FAILED replay idempotency

Issue #73 / PR #74 added bounded executable evidence that duplicate terminal `FAILED` feedback cannot rewrite an already-persisted execution failure.

### Changed / Actually Executed / Verified

- added `tests/duplicate-terminal-failure-replay-test.py` and dedicated exact-head `Duplicate Terminal Failure Replay Proof` workflow;
- review identified that replaying a second MQTT status could be ignored after Terra-Sense removed the pending command, so the corrected proof publishes a schema-valid correlated `FAILED` feedback record directly to `terra.control.feedback` and waits for `terra-ops-group` catch-up;
- corrected PR #74 exact head `6376b2a9796f93daf24a090469eb615c56c8f2f2` passed `Duplicate Terminal Failure Replay Proof` run #2, `CI/CD Pipeline` run #312, `Late ACK Recovery Proof` run #45, `Mismatched MQTT ACK Rejection Proof` run #14, `Synthetic MQTT Device Harness Proof` run #18, `Kafka Restart ACK Recovery Proof` run #34, `Software Proof Handoff` run #23, `Stale DELIVERED After Device Failure Proof` run #7, `Correlated MQTT Device Failure Proof` run #10, `MQTT Restart Subscription Recovery Proof` run #30, and `Terra-Ops Restart ACK Recovery Proof` run #37;
- the inline review blocker was answered against the corrected exact head and resolved;
- PR #74 was squash-merged with expected-head guard as `072bbe7bda4101e89f0849ef81daf09debfb5db1` and Issue #73 closed completed;
- within the bounded synthetic software integration path, duplicate correlated terminal `FAILED` feedback traversed the Terra-Ops Kafka consumer without dead-lettering and preserved `EXECUTION_FAILED`, the original `commandId`, original failure timestamps/result fields, `DEVICE_EXECUTION_FAILED`, the original synthetic device error, and the cleared ACK deadline.

## Progression milestone — mismatched plan identity feedback rejection

Issue #75 / PR #76 added bounded executable negative-path evidence that a schema-valid Kafka feedback event carrying a real dispatched `commandId` but the wrong valid `plan_id` cannot mutate the command owner's persisted plan.

### Changed / Actually Executed / Verified

- added `tests/mismatched-plan-feedback-rejection-test.py` and dedicated exact-head `Mismatched Plan Feedback Rejection Proof` workflow;
- the first proof attempt exposed an unsupported helper argument in DLT polling; a same-gap correction removed that misuse, and the final correction made rejection evidence deterministic by recording `terra.control.feedback.DLT` end offsets before the bad event and requiring a subsequent offset increase;
- final PR #76 exact head `c8b0e178d21ca645e278cc20b9abd3429724f90e` passed all 12 exact-head workflows, including `Mismatched Plan Feedback Rejection Proof` run #3 and `CI/CD Pipeline` run #317, with no queued, in-progress, or failed exact-head runs;
- the P1 inline review thread was answered with final exact-head evidence and resolved;
- PR #76 was squash-merged with expected-head guard as `52c2c335498c6bb22904f865b45ce388ee252f2f` and Issue #75 closed completed;
- within the bounded synthetic software integration path, mismatched plan ownership feedback reached the configured failure path without advancing the target plan, after which correctly correlated feedback for the same original `commandId` still completed the intended plan normally.

## Progression milestone — mismatched farm / asset feedback ownership rejection

Issue #77 / PR #78 added bounded executable negative-path evidence that schema-valid Kafka feedback carrying a real dispatched `commandId` but the wrong persisted `farm_id` or `target_asset_id` cannot mutate the command owner's persisted plan.

### Changed / Actually Executed / Verified

- added `tests/mismatched-owner-feedback-rejection-test.py` and dedicated exact-head `Mismatched Owner Feedback Rejection Proof` workflow;
- the proof records `terra.control.feedback.DLT` end offsets before each mismatched event, requires the configured rejection path to advance for both wrong-farm and wrong-asset feedback, and verifies the target plan lifecycle remains unchanged after each rejection;
- after both negative cases, correctly correlated feedback for the same original `commandId` still completes the intended plan normally;
- PR #78 exact head `c3ae0539d9aa2e99ec3ff895d1b62eaf01a5ec44` passed all 13 exact-head workflows, including `Mismatched Owner Feedback Rejection Proof` run #1 and `CI/CD Pipeline` run #320; all relevant accepted regression workflows also completed `success`;
- PR #78 had no submitted review blockers or unresolved inline review threads on the accepted exact head;
- PR #78 was squash-merged with expected-head guard as `1f60c10a7ed90308cbbac3291d8953e85487abd8` and Issue #77 closed completed;
- within the bounded synthetic software integration path, mismatched persisted farm or asset ownership feedback reached the configured failure path without advancing the target plan, after which correctly correlated feedback for the original command still completed the intended plan.

## Progression milestone — contradictory FAILED cannot regress terminal EXECUTED

Issue #79 / PR #80 added bounded executable ordering evidence that a correctly correlated late `FAILED` feedback event cannot downgrade an already terminal-success command plan.

### Changed / Actually Executed / Verified

- added `tests/contradictory-failure-after-success-test.py` and dedicated exact-head `Contradictory Failure After Success Proof` workflow;
- the proof drives a real dispatched command to `EXECUTED / DEVICE_CONFIRMED`, records the terminal lifecycle fields and `terra.control.feedback.DLT` end offset, then publishes schema-valid correlated `FAILED` feedback for the same persisted owner and command;
- PR #80 exact head `4d8ee637d5cda507b9c66f5085304dcabc01129c` produced 14 PR-triggered workflow runs and they completed successfully, including `Contradictory Failure After Success Proof` run #1 and `CI/CD Pipeline` run #323;
- PR #80 had no submitted review blocker or unresolved inline review thread on the accepted exact head;
- PR #80 was squash-merged with expected-head guard as `ae27da10fe4d555dd7dce515b789fdc66c7bf0a5` and Issue #79 closed completed;
- within the bounded synthetic software integration path, contradictory correlated `FAILED` feedback reached the configured rejection path without changing the already terminal `EXECUTED / DEVICE_CONFIRMED` plan or its original command/lifecycle fields.

## Progression milestone — contradictory EXECUTED cannot regress terminal EXECUTION_FAILED

Issue #81 / PR #82 added bounded executable ordering evidence that a correctly correlated late `EXECUTED` feedback event cannot overwrite an already terminal execution-failure command plan.

### Changed / Actually Executed / Verified

- added `tests/contradictory-success-after-failure-test.py` and dedicated exact-head `Contradictory Success After Failure Proof` workflow;
- the proof dispatches a real command, drives it through the accepted synthetic MQTT failure path to `EXECUTION_FAILED / DEVICE_EXECUTION_FAILED`, records the terminal lifecycle fields and `terra.control.feedback.DLT` end offset, then publishes schema-valid correlated `EXECUTED` feedback for the same persisted owner and command;
- PR #82 exact head `ff69275576c1ce1149c574a76e9096115094da02` produced 15 PR-triggered workflow runs and all completed successfully, including `Contradictory Success After Failure Proof` run #1 (`33595312706`) and `CI/CD Pipeline` run #326 (`33595312804`);
- PR #82 had no submitted review blocker or unresolved inline review thread on the accepted exact head;
- PR #82 was squash-merged with expected-head guard as `1dd1cf648eafc432943a28fa0b628acde5533cb0` and Issue #81 closed completed;
- within the bounded synthetic software integration path, contradictory correlated `EXECUTED` feedback reached the configured rejection path without changing the already terminal `EXECUTION_FAILED / DEVICE_EXECUTION_FAILED` plan or its original command/lifecycle fields.

## Progression milestone — contradictory EXECUTED cannot regress terminal DELIVERY_FAILED

Issue #83 / PR #84 added bounded executable ordering evidence that a correctly correlated late `EXECUTED` feedback event cannot overwrite an already terminal MQTT delivery-failure command plan.

### Changed / Actually Executed / Verified

- added `tests/contradictory-success-after-delivery-failure-test.py` and dedicated exact-head `Contradictory Success After Delivery Failure Proof` workflow;
- the proof stops bounded Mosquitto immediately before dispatch so the running Terra-Sense path emits its existing `MQTT_PUBLISH_FAILED:` feedback and the persisted plan reaches `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` with a real `commandId`; after broker recovery it records the feedback DLT end offset and injects schema-valid correctly correlated `EXECUTED` feedback for the same persisted owner and command;
- PR #84 exact head `a1ce3fc1d7f2e9a524f0bc708028d2cf2ee1fe96` produced 16 PR-triggered workflows and all completed `success`, including `Contradictory Success After Delivery Failure Proof` run #1 (`33610157515`) and `CI/CD Pipeline` run #329 (`33610157717`);
- PR #84 had no submitted reviews or inline review comments on the accepted exact head;
- PR #84 was squash-merged with expected-head guard as `dd097da8635fb0d682a19423cd10c630c44e6690` and Issue #83 closed completed;
- within the bounded synthetic software integration path, contradictory correlated `EXECUTED` feedback advanced the configured DLT rejection path while preserving the original `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` terminal truth, command identity, timestamps, failure evidence, and ACK-deadline fields.

## Progression milestone — stale DELIVERED cannot regress terminal DELIVERY_FAILED

Issue #85 / PR #86 added bounded executable ordering evidence that a schema-valid correctly correlated stale transport `DELIVERED` event cannot overwrite an already terminal MQTT delivery-failure command plan.

### Changed / Actually Executed / Verified

- added `tests/stale-delivered-after-delivery-failure-test.py` and dedicated exact-head `Stale DELIVERED After Delivery Failure Proof` workflow;
- the proof stops bounded Mosquitto before dispatch so the running Terra-Sense path emits `MQTT_PUBLISH_FAILED:` feedback and the persisted plan reaches `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` with a real `commandId`; after broker recovery it snapshots terminal lifecycle fields and the feedback DLT end offset, then injects schema-valid correctly correlated `DELIVERED` feedback for the same persisted owner and command;
- PR #86 exact head `ed546395d4d37ad569dacc7bf22a50e3c8c48228` produced 17 PR-triggered workflows and all completed `success`, including `Stale DELIVERED After Delivery Failure Proof` run #1 (`33615854954`) and `CI/CD Pipeline` run #332 (`33615855235`);
- PR #86 had no review/comment blocker on the accepted exact head;
- PR #86 was squash-merged with expected-head guard as `89a46ae60d577b2a8d1c5c7a9d71554b76d53f51` and Issue #85 closed completed;
- within the bounded synthetic software integration path, stale correlated `DELIVERED` feedback advanced the configured DLT rejection path while preserving the original `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` terminal truth, original `commandId`, timestamps, failure evidence, and ACK-deadline fields.

## Progression milestone — duplicate terminal DELIVERY_FAILED replay idempotency

Issue #87 / PR #88 added bounded executable evidence that duplicate/retried terminal `FAILED` feedback cannot rewrite an already-persisted MQTT delivery failure.

### Changed / Actually Executed / Verified

- added `tests/duplicate-delivery-failure-replay-test.py` and dedicated exact-head `Duplicate Delivery Failure Replay Proof` workflow;
- the proof first creates `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` through the running synthetic MQTT publish-failure path, records the original terminal lifecycle and first `MQTT_PUBLISH_FAILED:` evidence, then publishes a second schema-valid correlated `FAILED` feedback with different error text directly to `terra.control.feedback` and waits for `terra-ops-group` catch-up;
- PR #88 exact head `f5f667451026eb64ca877e5169c8352c25ef7ea1` produced 18 exact-head workflow runs; all completed with no failed, queued, or in-progress run, including `Duplicate Delivery Failure Replay Proof` run #1 (`33620817751`);
- PR #88 had no review/comment blocker on the accepted exact head;
- PR #88 was squash-merged with expected-head guard as `ff873b1a682babcec85e2b1329405daf13f92eb7` and Issue #87 closed completed;
- within the bounded synthetic software integration path, duplicate correlated terminal `FAILED` feedback was consumed without replacing the original `DELIVERY_FAILED / MQTT_DELIVERY_FAILED` state, original command identity, first failure evidence, timestamps, result fields, or cleared ACK-deadline truth.

## Progression milestone — delayed FAILED recovery after ACK timeout

Issue #89 / PR #90 added bounded executable recovery evidence that a correctly correlated delayed device `FAILED` can recover an `ACK_TIMEOUT` plan to truthful terminal execution failure.

### Changed / Actually Executed / Verified

- added `tests/late-failure-recovery-test.py` and dedicated exact-head `Late Failure Recovery Proof` workflow;
- the proof drives a real dispatched command through `DELIVERED → ACK_TIMEOUT`, then publishes a correlated synthetic MQTT `FAILED` status and verifies the running MQTT → Terra-Sense → Kafka feedback → Terra-Ops path converges the same persisted plan to `EXECUTION_FAILED / DEVICE_EXECUTION_FAILED`;
- PR #90 exact head `a4f2bb8d4c4c21025ce69f4b8965465dd363d816` produced 19 PR-triggered workflow runs and all completed `success`, including `Late Failure Recovery Proof` run #1 (`33631138639`) and `CI/CD Pipeline` run #338 (`33631138942`), with all accepted regression workflows on that exact head also green;
- PR #90 was squash-merged with expected-head guard as `58c5ffadf181446b4f36e00dd9c2ae569d3905a3` and Issue #89 closed completed;
- within the bounded synthetic software integration path, the same persisted `commandId` survived ACK timeout, the delayed correlated failure cleared the ACK deadline, preserved deterministic delayed device-failure evidence, and converged the plan to `EXECUTION_FAILED / DEVICE_EXECUTION_FAILED` rather than leaving timeout state stale.

## Progression milestone — repeated ACK-timeout scan idempotency

Issue #91 / PR #92 added bounded executable scheduler/audit evidence that repeated ACK-timeout scans do not rewrite an already persisted timeout lifecycle or duplicate its operator-visible timeout audit row.

### Changed / Actually Executed / Verified

- added `tests/ack-timeout-scan-idempotency-test.py` and dedicated exact-head `ACK Timeout Scan Idempotency Proof` workflow;
- two same-gap test-harness defects were corrected before acceptance: the proof now waits for the first committed `COMMAND_TIMEOUT` audit row before starting the idempotency observation window, and it parses the audit endpoint's authoritative JSON-list response contract directly;
- corrected PR #92 exact head `0f07d9b9ebaaa0517a2303f95f333a7009dbefbd` produced 20 exact-head workflow runs and all completed `success`, including `CI/CD Pipeline` run #343 (`33655907427`) and the dedicated `ACK Timeout Scan Idempotency Proof` run #3;
- the earlier inline review thread concerned the corrected audit parsing defect and was resolved on the accepted exact head;
- PR #92 was squash-merged with expected-head guard as `6d04311caac3ea6f98a33f0347004a498c65513b` and Issue #91 closed completed;
- within the bounded synthetic software scheduler/database/audit boundary, after one real `DELIVERED → ACK_TIMEOUT / DEVICE_ACK_TIMEOUT` transition, multiple additional timeout-scan cycles preserved the original lifecycle snapshot and retained exactly one `COMMAND_TIMEOUT` audit row for the original command.

## Progression milestone — command outbox publication recovery after Kafka outage

Issue #93 / PR #94 added bounded executable transactional-outbox recovery evidence that an approval committed while Kafka is unavailable can retain command identity, record retry evidence, and publish the same command after bounded broker recovery.

### Changed / Actually Executed / Verified

- added `tests/outbox-kafka-publication-recovery-test.py` and dedicated exact-head `Outbox Kafka Publication Recovery Proof` workflow;
- two same-gap test-harness defects were corrected before acceptance: MySQL password warnings were removed from the query path, and SQL stdout was isolated from Docker Compose stderr so warnings could not be misparsed as extra outbox rows;
- corrected PR #94 exact head `ed55c56fa3b4d048cc40576a2e2d48698e3ff57b` produced 21 exact-head workflow runs; the exact-head set completed successfully, including `CI/CD Pipeline` run #348 (`33686136253`) and the dedicated `Outbox Kafka Publication Recovery Proof` run #3;
- PR #94 was squash-merged as `97d482f991e435058492949cab46bb510d0da858` and Issue #93 closed completed;
- within the bounded synthetic Compose software integration path, approval/outbox persistence survived a bounded Kafka outage, persisted retry evidence without replacing the command identity, recovered publication on the same outbox/command after broker restart, and the same command completed through MQTT plus a correlated synthetic terminal ACK to `EXECUTED`.

## Progression milestone — stale PROCESSING outbox claim recovery after Terra-Ops restart

Issue #95 / PR #96 added bounded executable evidence that a stale transactional-outbox claim can recover after Terra-Ops restart without replacing the persisted command identity.

### Changed / Actually Executed / Verified

- added `tests/stale-outbox-claim-recovery-test.py` and dedicated exact-head `Stale Outbox Claim Recovery Proof` workflow;
- the proof creates one real persisted command/outbox identity, stops Terra-Ops, deterministically marks that same outbox row stale `PROCESSING`, then restarts Terra-Ops and requires the running stale-claim recovery path to republish the same outbox/command;
- PR #96 exact head `6128196409783ef3069531d3e5a35ea34469ce36` produced 22 PR-triggered workflow runs and all completed `success`;
- PR #96 was squash-merged with expected-head guard as `ef3daf50c7c10412b7fbd120bc0410b1471ec861` and Issue #95 closed completed;
- within the bounded synthetic Compose software integration path, the same stale `PROCESSING` outbox row recovered to publication after Terra-Ops restart, retained the original `commandId`, and the command completed through MQTT plus a correlated synthetic terminal ACK to `EXECUTED`;
- this proof deterministically injects the stale persisted state while Terra-Ops is stopped; it does not claim reproduction of a particular production crash instruction boundary.

## Not Verified / limitations

All v1.0 non-claims remain in force. The accepted baseline and progression milestones do **not** verify or claim:

- production MQTT client identity, authentication, authorization, or TLS;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, physical-equipment certification, or physical device truth;
- manufacturer/model-specific capability adapters;
- production secrets management/key rotation;
- production HA, backup/restore, DR, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that device-reported or software state equals physical equipment state.

The service/broker restart milestones are bounded synthetic software integration evidence. They do not establish production HA/fault-injection maturity, production network guarantees, or physical-equipment behavior. The audit milestone establishes software/operator trace usability only; it does not establish physical-state truth or production compliance/audit certification. The handoff milestone establishes reproducibility of the bounded synthetic software Proof only; its demo-only local secret is not production secrets-management evidence. The synthetic device harness, mismatched-ACK rejection, correlated device-failure, stale-feedback-ordering, duplicate-terminal-failure-replay, mismatched-plan-feedback, mismatched-owner-feedback, contradictory-failure-after-success, contradictory-success-after-failure, contradictory-success-after-delivery-failure, stale-delivered-after-delivery-failure, duplicate-delivery-failure-replay, late-failure-after-ack-timeout, repeated-ACK-timeout-scan-idempotency, outbox-Kafka-publication-recovery, and stale-outbox-claim-recovery milestones establish software MQTT/Kafka contract, correlation, failure-propagation, ordering, idempotency, persisted ownership rejection, recovery, scheduler/audit behavior, outbox retry/publication recovery, stale-claim recovery, and terminal-state behavior only; they do not establish cryptographic device identity, manufacturer fault semantics, physical-device semantics, actuator behavior, or production messaging trust.

## Remaining risks

- broader network failure handling beyond the accepted bounded Kafka/MQTT broker-restart cases requires separate executable evidence;
- operator/audit usability can still be strengthened where another concrete delivery gap is demonstrated;
- synthetic device/digital-twin coverage can still be strengthened where a new executable software-Proof gap is concrete and does not imply physical-device truth;
- production security/availability boundaries remain separate from the accepted bounded software Proof;
- production and physical-world trust boundaries remain explicitly outside the accepted software Proof.

## Exact Next Action

- perform a fresh Progression Review against current `main` before selecting another milestone;