# TerraNeuron — Implementation Status

> **Last updated:** 2026-09-03  
> **Status:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — D1+D2 SOFTWARE DESTINATIONS REACHED / HUMAN REVIEW NEXT DESTINATION`  
> **Authority:** authoritative implementation status / execution contract for this repository  
> **Proof v1.0 implementation baseline SHA:** `7ef9315890f1e2c06345bce94fb3334c2cff1c0e`  
> **Accepted progression through D2:** `9ffee0a63a183304a07b5f22a7ec94d16068db4e`

When documents disagree, use:

`current main code / executable evidence → STATUS.md → README.md / historical audits / PR descriptions / previous agent reports`

Proof v1.0 remains an accepted bounded software checkpoint. `FREEZE` freezes that accepted version; it does not prevent later bounded progression. Progression must preserve all explicit non-claims and must not retroactively broaden the v1.0 acceptance boundary.

## Accepted v1.0 baseline

Human Review completed on 2026-08-22 with result:

`PASS — FREEZE APPROVED`

The accepted v1.0 buyer-facing boundary remains unchanged: a production-oriented event-driven smart-farm architecture prototype with executable neural-flow and command-lifecycle software Proof, Dashboard BFF authentication propagation under the verified boundary, persisted security/session controls, service-JWT boundaries, rate limiting, transactional outbox, retry/DLQ, schema validation, observability, dependency scanning, and software safety-gate behavior under the implemented policy boundary.

## Accepted progression evidence ledger

The following bounded progression slices were accepted by exact-head executable evidence and merged. Git history, the linked Issues/PRs, and workflow runs remain the detailed evidence source; this ledger preserves the accepted heads/merges and the invariant each slice established.

| Issue / PR | Accepted exact head | Merge SHA | Accepted bounded software evidence |
|---|---|---|---|
| #51 / #52 | `7839bd0b1a902b69c53c097b6ac38bd7045bc49e` | `03c3b172784caabd37d0edc54c49a9c0549471fc` | duplicate terminal ACK idempotency |
| #53 / #54 | `a95357baa59ba0eb862670315be0a00a10412519` | `cfb41521639454099287c588a8f983125bd7fcdc` | delayed correlated terminal ACK recovery after ACK timeout |
| #55 / #56 | `8616554c9dfb7db44736645daf5b517adf0ab8b6` | `a747ae679ea85d23853c924131c9af601d052983` | terminal ACK recovery across Terra-Ops restart |
| #57 / #58 | `7de61c4fc30685dcad72bfae730b06bfb05c08cd` | `b272fa820da7537fc66d4ffa9ecd9f109f1d5040` | terminal ACK recovery across bounded Kafka restart |
| #59 / #60 | `79a38131a745d7c86b17c69910df814dd5831f5d` | `0be87e0aca592e89f0f58a985d1629bfb5e4d76c` | MQTT subscription recovery across bounded Mosquitto restart |
| #61 / #62 | `dad04f4d7c987bd2456d1dd47bea9076e09dde60` | `c5c19f96c7b3d397da4044fb8121a34bb7d17923` | chronological plan + correlated command audit timeline |
| #63 / #64 | `7e77da339ffe35052794f81b76df945714132967` | `d3608b12f7e58c95d58d6f16c5ebf108fa9ab5bf` | one-command reproducible bounded software-Proof handoff with failure diagnostics |
| #65 / #66 | `85cf878af0639b85c8be01d9891b5ee93d23fd49` | `92d246025f10d04207cb27f0a52193287b4a3030` | reusable independent synthetic MQTT device command/ACK actor |
| #67 / #68 | `2caac4b45a2a306f7933f4ab52b60ddc694a4b16` | `c7aa2571765fb6710fe799a3fd09d4cec3c31178` | mismatched asset ACK rejection with later correct completion |
| #69 / #70 | `396b964c15282d9384c96cc0285894c921ab5693` | `b6feb62f72d7ce8bb1a47b8eba298a70c02fc1ca` | correlated synthetic device FAILED propagation |
| #71 / #72 | `2ca81fd6c9eac65c8575fbe8c52b429ae18a3db1` | `815933edc25f68d744da73dad689c9e394d50a42` | stale DELIVERED cannot regress terminal device failure |
| #73 / #74 | `6376b2a9796f93daf24a090469eb615c56c8f2f2` | `072bbe7bda4101e89f0849ef81daf09debfb5db1` | duplicate terminal FAILED replay idempotency |
| #75 / #76 | `c8b0e178d21ca645e278cc20b9abd3429724f90e` | `52c2c335498c6bb22904f865b45ce388ee252f2f` | mismatched plan feedback rejection |
| #77 / #78 | `c3ae0539d9aa2e99ec3ff895d1b62eaf01a5ec44` | `1f60c10a7ed90308cbbac3291d8953e85487abd8` | mismatched persisted farm/asset owner feedback rejection |
| #79 / #80 | `4d8ee637d5cda507b9c66f5085304dcabc01129c` | `ae27da10fe4d555dd7dce515b789fdc66c7bf0a5` | contradictory FAILED cannot regress terminal EXECUTED |
| #81 / #82 | `ff69275576c1ce1149c574a76e9096115094da02` | `1dd1cf648eafc432943a28fa0b628acde5533cb0` | contradictory EXECUTED cannot overwrite terminal execution failure |
| #83 / #84 | `a1ce3fc1d7f2e9a524f0bc708028d2cf2ee1fe96` | `dd097da8635fb0d682a19423cd10c630c44e6690` | contradictory EXECUTED cannot overwrite terminal delivery failure |
| #85 / #86 | `ed546395d4d37ad569dacc7bf22a50e3c8c48228` | `89a46ae60d577b2a8d1c5c7a9d71554b76d53f51` | stale DELIVERED cannot regress terminal delivery failure |
| #87 / #88 | `f5f667451026eb64ca877e5169c8352c25ef7ea1` | `ff873b1a682babcec85e2b1329405daf13f92eb7` | duplicate delivery-failure replay idempotency |
| #89 / #90 | `a4f2bb8d4c4c21025ce69f4b8965465dd363d816` | `58c5ffadf181446b4f36e00dd9c2ae569d3905a3` | delayed FAILED recovery after ACK timeout |
| #91 / #92 | `0f07d9b9ebaaa0517a2303f95f333a7009dbefbd` | `6d04311caac3ea6f98a33f0347004a498c65513b` | repeated ACK-timeout scan idempotency and single timeout audit truth |
| #93 / #94 | `ed55c56fa3b4d048cc40576a2e2d48698e3ff57b` | `97d482f991e435058492949cab46bb510d0da858` | transactional-outbox publication recovery after bounded Kafka outage, preserving command identity |
| #95 / #96 | `6128196409783ef3069531d3e5a35ea34469ce36` | `ef3daf50c7c10412b7fbd120bc0410b1471ec861` | stale `PROCESSING` outbox claim recovery after Terra-Ops restart, preserving command identity |
| #97 / #98 | `1870f6cd1917df9b26e1485ac73901a4276aa9ca` | `bc04848b82e4a5d2319263a966e19cd9178d95c1` | real Kafka publication retry exhaustion → outbox `DEAD` → plan `DISPATCH_FAILED / OUTBOX_DEAD_LETTER`, with later scans preserving terminal truth |
| #99 / #100 | `45acaddd0ff70210284db2d49a8dd5ccfe370d55` | `9ffee0a63a183304a07b5f22a7ec94d16068db4e` | coherent Synthetic Farm Operations Pilot: synthetic starting state → operator-visible decision/approval → MQTT actor → correlated `EXECUTED` → chronological audit → evidence artifact/handoff |

## Milestone #24 reconciliation — outbox retry exhaustion terminal failure

### Changed

- added the dedicated retry-exhaustion executable proof and proof-only configuration for bounded `max-attempts=2` plus short backoff;
- the first run exposed that two real Kafka metadata failures could exceed the proof's 120-second polling deadline; the same-gap correction increased the dedicated proof deadline to 180 seconds without changing product defaults or acceptance semantics.

### Actually Executed / Verified

- PR #98 accepted exact head `1870f6cd1917df9b26e1485ac73901a4276aa9ca` produced **23/23 PR-triggered workflow runs with `completed / success`**, including the dedicated `Outbox Retry Exhaustion Proof` and `CI/CD Pipeline` plus the accepted regression set;
- the corrected exact head had no remaining review blocker before merge;
- PR #98 was squash-merged with expected-head guard as `bc04848b82e4a5d2319263a966e19cd9178d95c1`;
- Issue #97 closed completed;
- within the bounded synthetic Compose software boundary, one persisted command/outbox identity survived real repeated Kafka publication failures until the configured proof retry limit, the outbox became `DEAD`, its owning plan became `DISPATCH_FAILED / OUTBOX_DEAD_LETTER`, and later publisher scans did not resurrect or rewrite that terminal truth.

### Not Verified by #24

The proof-only retry limit/backoff settings do not redefine production defaults and do not establish production Kafka HA/DR, load behavior, general fault-injection maturity, or production messaging identity/TLS.

## Destination review — D1

### `DESTINATION REACHED — BOUNDED COMMAND-LIFECYCLE SOFTWARE PROOF`

The accepted progression through merge `bc04848b82e4a5d2319263a966e19cd9178d95c1`, together with the frozen v1.0 baseline, is sufficient to establish D1 as a **strong bounded software Proof** rather than a collection that still needs more isolated ACK/replay/timeout/outbox permutations.

D1 now has executable evidence for the intended invariant family:

- persisted action plans and stable command identity;
- transactional-outbox persistence, retry, stale-claim recovery, broker-outage recovery, and bounded terminal retry exhaustion;
- running Kafka → Terra-Sense → MQTT command delivery and MQTT → Terra-Sense → Kafka → Terra-Ops correlated synthetic feedback;
- a reusable independent synthetic MQTT device actor;
- terminal success/failure, timeout/recovery, stale/contradictory ordering, correlation rejection, and idempotent replay behavior;
- operator-visible chronological plan/command audit evidence and timeout audit idempotency;
- bounded broker/service restart recovery where explicitly executed;
- one-command clean-checkout software-Proof handoff with executable PASS/FAIL and failure diagnostics.

Under the anti-micro-loop rule, further isolated command-message/failure permutations are **not** useful progression unless a coherent D2 scenario exposes a concrete blocker.

## D2 reconciliation — Synthetic Farm Operations Pilot

### `DESTINATION REACHED — SYNTHETIC FARM OPERATIONS PILOT`

### Changed

- added one reusable coherent synthetic farm-operations scenario and a dedicated executable workflow;
- the first exact-head run exposed a harness-only parsing mismatch for list-shaped operator endpoints; the same-gap fix added explicit list parsing/validation without changing product semantics;
- the corrected exact head also exposed one transient clean-checkout handoff startup race where Terra-Ops attempted Flyway connection before MySQL accepted connections; rerunning the existing handoff job on the same exact head succeeded, so no product/handoff mutation was justified.

### Actually Executed / Verified

- PR #100 accepted exact head `45acaddd0ff70210284db2d49a8dd5ccfe370d55` produced **24/24 PR-triggered workflow runs with `completed / success`** after the same-head handoff rerun, including `Synthetic Farm Operations Pilot`, `Software Proof Handoff`, `CI/CD Pipeline`, and the accepted D1 regression set;
- the dedicated D2 scenario executed the bounded path `synthetic device state → operator-visible PENDING plan → explicit approval/dispatch → reusable synthetic MQTT device actor → correlated EXECUTED result → chronological plan/command audit → JSON/Markdown evidence artifact`;
- the sole prior P1 review thread addressed the list-parser mismatch, became outdated after the same-gap correction, and was resolved before merge;
- PR #100 was squash-merged with expected-head guard as `9ffee0a63a183304a07b5f22a7ec94d16068db4e`;
- Issue #99 closed completed.

### Verified D2 value

D2 establishes a coherent, reusable, buyer-demonstrable **synthetic software operations pilot** built from the accepted command lifecycle, operator boundary, synthetic MQTT actor, audit timeline, evidence artifact, and reproducible handoff. It demonstrates use/show/delivery value as one scenario rather than another isolated command-message permutation.

### Not Verified by D2

D2 does not verify or claim physical actuator truth, manufacturer/controller semantics, production MQTT identity/auth/TLS, field safety/interlocks, unattended autonomous control, production HA/DR/load maturity, certification, or that synthetic/device-reported software state equals physical equipment state.

## Not Verified / limitations

All v1.0 non-claims remain in force. The accepted baseline and progression milestones do **not** verify or claim:

- production MQTT client identity, authentication, authorization, or TLS;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, physical-equipment certification, or physical device truth;
- manufacturer/model-specific capability adapters;
- production secrets management/key rotation;
- production HA, backup/restore, DR, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that device-reported or software state equals physical equipment state.

The service/broker restart milestones are bounded synthetic software integration evidence. They do not establish production HA/fault-injection maturity, production network guarantees, or physical-equipment behavior. The audit milestone establishes software/operator trace usability only; it does not establish physical-state truth or production compliance/audit certification. The handoff milestone establishes reproducibility of the bounded synthetic software Proof only; its demo-only local secret is not production secrets-management evidence.

The synthetic device harness, D1 progression slices, and D2 pilot establish software MQTT/Kafka contract, correlation, failure propagation, ordering, idempotency, persisted ownership rejection, bounded recovery, scheduler/audit behavior, outbox retry/publication recovery, stale-claim recovery, terminal-state behavior, and a coherent synthetic operator/demo flow only. They do not establish cryptographic device identity, manufacturer fault semantics, physical-device semantics, actuator behavior, or production messaging trust.

## Remaining risks / destination gates

- D1 and D2 are accepted bounded software destinations; another isolated ACK/outbox/message-ordering proof is not justified absent a newly observed blocker;
- production security/availability boundaries remain separate from the accepted bounded software Proof;
- production and physical-world trust boundaries remain explicitly outside the accepted software Proof;
- the next meaningful expansion beyond this synthetic pilot would require a product decision about real hardware/manufacturer adapters, physical safety/interlocks, production messaging identity/TLS, production HA/DR/load, unattended control, or another explicitly chosen bounded destination.

## Next destination gate

### `HUMAN REVIEW — NEXT DESTINATION / PHYSICAL TRUST DECISION`

No further automatic progression milestone is selected. D1 and D2 have reached their bounded software destinations. Advancing toward real devices, manufacturer-specific adapters/semantics, physical safety/interlocks, production MQTT identity/TLS, production HA/DR/load, or unattended autonomous control requires separate evidence and an explicit human/product decision; those claims must not be inferred from D1/D2.

## Exact Next Action

- human/product review chooses whether TerraNeuron should remain frozen at the accepted D1+D2 bounded software-Proof/pilot boundary or open a separately scoped next destination;
- if a next destination is approved, define its explicit trust/evidence boundary before creating any new Issue/PR;
- do not reopen command-message permutation work merely to accumulate more tests.
