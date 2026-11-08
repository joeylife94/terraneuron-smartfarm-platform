# TerraNeuron — Implementation Status

> **Last updated:** 2026-11-08  
> **Status:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — D1+D2+D3+D4 SOFTWARE DESTINATIONS REACHED / P0 ACCEPTED / HUMAN REVIEW — PHYSICAL TRUST DECISION`  
> **Authority:** authoritative implementation status / execution contract for this repository  
> **Proof v1.0 implementation baseline SHA:** `7ef9315890f1e2c06345bce94fb3334c2cff1c0e`  
> **Accepted progression through D2:** `9ffee0a63a183304a07b5f22a7ec94d16068db4e`  
> **Accepted P0 truthfulness reconciliation:** `b24a245e12cb02a58e68fab486413b097d6241de`  
> **Accepted D3 authenticated messaging pilot:** `df63cd688d1ef1856ab8bd1a82bf95ea9e648d61`  
> **Accepted D4 device integration conformance pilot:** `7eb6f433e9c1158002da6bf1c090a68fca1b95f1`  
> **Accepted security maintenance (bounded dependency gate):** PR #107 exact head `6660c614d137022dfab691d37e1921ab1701a1de`, squash-merged `3a630984f0bd25bdcd8c0e4ae108cea97fd6e886` on 2026-11-08; no runtime deployment  
> **Security maintenance follow-up (candidate, pending Human Acceptance):** sentence-transformers 6.x, PR #109

When documents disagree, use:

`current main code / executable evidence → STATUS.md → README.md / historical audits / PR descriptions / previous agent reports`

Proof v1.0 remains an accepted bounded software checkpoint. `FREEZE` freezes that accepted version; it does not prevent later bounded progression. Progression must preserve all explicit non-claims and must not retroactively broaden the v1.0 acceptance boundary.

## Accepted v1.0 baseline

Human Review completed on 2026-08-22 with result:

`PASS — FREEZE APPROVED`

The accepted v1.0 buyer-facing boundary remains unchanged: a production-oriented event-driven smart-farm architecture prototype with executable neural-flow and command-lifecycle software Proof, Dashboard BFF authentication propagation under the verified boundary, persisted security/session controls, service-JWT boundaries, rate limiting, transactional outbox, retry/DLQ, schema validation, observability, dependency scanning, and software safety-gate behavior under the implemented policy boundary.

## Accepted progression evidence ledger

The following bounded progression slices were accepted by exact-head executable evidence and merged. Git history, linked Issues/PRs, and workflow runs remain the detailed evidence source; this ledger preserves the accepted heads/merges and the invariant each slice established.

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
| #97 / #98 | `1870f6cd1917df9b26e1485ac73901a4276aa9ca` | `bc04848b82e4a5d2319263a966e19cd9178d95c1` | Kafka publication retry exhaustion → outbox `DEAD` → plan `DISPATCH_FAILED / OUTBOX_DEAD_LETTER`, with later scans preserving terminal truth |
| #99 / #100 | `45acaddd0ff70210284db2d49a8dd5ccfe370d55` | `9ffee0a63a183304a07b5f22a7ec94d16068db4e` | coherent Synthetic Farm Operations Pilot: synthetic starting state → operator-visible decision/approval → MQTT actor → correlated `EXECUTED` → chronological audit → evidence artifact/handoff |
| #101 / #102 | `5a2cebc59d739dd686cfbd4742f3ff92a18ab4ad` | `b24a245e12cb02a58e68fab486413b097d6241de` | buyer-facing truthfulness reconciliation without new capability claims |
| #103 / #104 | `a727720be5c21f3a02d1ed727820d4ec79f9da08` | `df63cd688d1ef1856ab8bd1a82bf95ea9e648d61` | bounded authenticated+encrypted synthetic MQTT boundary with own-topic success, anonymous/cross-device denial, identity protection, approval/safety/ACK/audit journey |
| #105 / #106 | `688e596f64d3a966e8293368f1cc2bc50fc0d99a` | `7eb6f433e9c1158002da6bf1c090a68fca1b95f1` | reusable synthetic adapter/model conformance contract: declared capability admission, unsupported/unknown fail-closed, authenticated MQTT metadata path, stable command identity, correlated terminal ACK/audit |

## Destination review — D1

### `DESTINATION REACHED — BOUNDED COMMAND-LIFECYCLE SOFTWARE PROOF`

The accepted D1 progression plus the frozen v1.0 baseline is sufficient to establish a strong bounded command-lifecycle software Proof. It includes persisted plans/command identity, transactional outbox, bounded retry/recovery and terminal exhaustion, Kafka/MQTT software integration, reusable synthetic MQTT actor, terminal success/failure/idempotency/ordering, audit evidence, bounded restart recovery where explicitly executed, and reproducible software handoff.

Under the anti-micro-loop rule, further isolated ACK/replay/timeout/outbox permutations are not useful progression unless a coherent later destination exposes a concrete blocker.

## D2 reconciliation — Synthetic Farm Operations Pilot

### `DESTINATION REACHED — SYNTHETIC FARM OPERATIONS PILOT`

PR #100 accepted exact head `45acaddd0ff70210284db2d49a8dd5ccfe370d55` with 24/24 PR-triggered workflow runs successful after the same-head handoff rerun. The bounded scenario executed:

`synthetic device state → operator-visible PENDING plan → explicit approval/dispatch → reusable synthetic MQTT device actor → correlated EXECUTED result → chronological plan/command audit → JSON/Markdown evidence artifact`

D2 establishes a coherent, reusable, buyer-demonstrable synthetic software operations pilot. It does not establish physical actuator truth, manufacturer/controller semantics, production MQTT identity/auth/TLS, field safety/interlocks, unattended autonomous control, production HA/DR/load maturity, certification, or that software/device-reported state equals physical equipment state.

## P0 reconciliation — Buyer-facing Truthfulness Reconciliation

### `P0 ACCEPTED — BUYER-FACING CLAIMS RECONCILED TO BOUNDED SOFTWARE-PROOF TRUTH`

PR #102 accepted exact head `5a2cebc59d739dd686cfbd4742f3ff92a18ab4ad` with 24/24 PR-triggered workflows successful and no unresolved review thread. `PROJECT_SUMMARY.md` was reconciled so historical local/synthetic measurements and planning estimates are not presented as production validation, throughput proof, field readiness, or physical truth. P0 changed documentation truthfulness only and created no new product capability claim.

## D3 reconciliation — Bounded Authenticated Device Messaging Pilot

### `DESTINATION REACHED — BOUNDED AUTHENTICATED DEVICE MESSAGING PILOT`

PR #104 accepted exact head `a727720be5c21f3a02d1ed727820d4ec79f9da08` with 25/25 PR-triggered workflow runs successful after same-head reruns of transient regression failures. It established a proof-only authenticated/encrypted synthetic MQTT boundary with explicit repository-owned synthetic identities, bounded topic authorization, anonymous denial, cross-device impersonation denial, topic/payload identity protection, and preservation of operator approval, two-stage software safety, command delivery, correlated terminal ACK, and audit evidence.

D3 is synthetic/local/CI software evidence only. It does not verify or claim production PKI/CA operations, certificate rotation/revocation, manufacturing or field provisioning, TPM/HSM, physical-device identity, field-network security, production MQTT infrastructure or secrets lifecycle, physical actuator truth, electrical interlocks/E-stop, manufacturer semantics, unattended autonomous control, HA/DR/load maturity, public production deployment, or certification.

## D4 reconciliation — Device Integration Conformance Pilot

### `DESTINATION REACHED — DEVICE INTEGRATION CONFORMANCE PILOT`

### Changed

- added one repository-owned clearly synthetic adapter/model capability resolver using the existing `DeviceCapabilityResolver` extension point;
- known synthetic model `tn-synth-climate-01` exposes only its declared schema-valid `heating` capability/action contract;
- unknown model under the explicit synthetic adapter is claimed with an empty capability set so it cannot fall through into generic device-type capabilities;
- extended the existing synthetic MQTT actor with optional synthetic adapter/model metadata without changing ordinary callers;
- added deterministic safety-policy conformance tests and one coherent D4 authenticated integration harness/workflow;
- reused the accepted D3 TLS/authentication/ACL profile and existing approval/safety/command/ACK/audit assets rather than adding a parallel device platform;
- same-gap fixes were limited to actual acceptance blockers: schema-valid category alignment, executing adapter/model metadata through MQTT rather than unit tests only, reusing the accepted D3 farm/ACL scope, D4-specific heater-state observation instead of the older fan-only D1 helper, and preserving proof-only TLS runtime material across the intentionally chained D3→D4 workflow step.

### Actually Executed / Verified

- PR #106 accepted exact head `688e596f64d3a966e8293368f1cc2bc50fc0d99a` produced **26/26 PR-triggered workflow runs with `completed / success`**;
- the exact-head gate includes successful `D4 Device Integration Conformance Pilot`, `D3 Authenticated Device Messaging Pilot`, `Synthetic Farm Operations Pilot`, `Software Proof Handoff`, `CI/CD Pipeline`, and all applicable accepted D1 regression workflows;
- both P1 review threads were resolved before merge after the schema-valid action category and full authenticated MQTT conformance path were implemented;
- PR #106 was squash-merged with expected-head protection as `7eb6f433e9c1158002da6bf1c090a68fca1b95f1`;
- Issue #105 closed completed;
- the bounded synthetic proof established explicit adapter/model identity and declared capabilities, supported-action admission only when declared capabilities permit it, unsupported/unknown fail-closed behavior before MQTT actuation, preservation of D3 authenticated messaging, stable command identity, correlated terminal `EXECUTED` ACK/audit, and one deterministic public-safe conformance result.

### Not Verified by D4

D4 does **not** validate or claim any real Samsung/LG/other manufacturer semantics, real hardware/device integration, physical actuator truth, manufacturer protocol/controller correctness, physical safety or electrical interlocks/E-stop, production provisioning/PKI/secrets lifecycle, unattended autonomous control, production HA/DR/load/public deployment, or certification/compliance.

The D4 fixture is intentionally repository-owned and synthetic. Its purpose is to define the software conformance contract a future real adapter would have to satisfy; it is not evidence that any real adapter or physical device satisfies that contract.

## Security maintenance — dependency gate recovery

### `SECURITY MAINTENANCE ACCEPTED — BOUNDED DEPENDENCY GATE RECOVERY`

Human-accepted bounded security maintenance. PR #107 was squash-merged into `main` as `3a630984f0bd25bdcd8c0e4ae108cea97fd6e886` on 2026-11-08, after exact-head CI and independent code review. It is **not** a D5 destination, adds no product capability, and does not change the security-scan policy or any accepted Proof boundary. Runtime deployment and broad security assurance remain **NOT VERIFIED**.

### Trigger

The scheduled `Security Scan` on `main` @ `d197cc03d9e0798390754b2d16490def0110a96e` turned red on 2026-10-05 (run `37260618503`) and stayed red through run `41383009070` (2026-11-02) with no code change: newly published advisories flagged **26 fixable HIGH/CRITICAL findings** (24 HIGH, 2 CRITICAL) against three direct pins in `services/terra-cortex/requirements.txt`: PyJWT 2.13.0 (7), pypdf 6.15.0 (18), sentence-transformers 2.2.2 (1 CRITICAL, CVE-2026-68770).

### Changed (PR #107; accepted PR head `6660c614d137022dfab691d37e1921ab1701a1de`, squash merge `3a630984f0bd25bdcd8c0e4ae108cea97fd6e886`)

- dependency commit `19064fe135538969ebd441ad498305c0e8afc6d9`: `PyJWT 2.13.0 → 2.15.1`, `pypdf 6.15.0 → 6.21.4`, `sentence-transformers 2.2.2 → 5.6.1`; `huggingface-hub==0.25.2` kept;
- resolved graph otherwise identical on Python 3.11 (CI) and 3.10 (Docker): torch, transformers 4.48.3, tokenizers, numpy, langchain*, chromadb unchanged; torchvision, nltk, sentencepiece, pillow, defusedxml no longer installed (only sentence-transformers 2.2.2 required them; no repository code imports them);
- offline regression tests (`tests/test_service_auth.py`, `tests/test_knowledge_dependency_contract.py`): golden HS256 service-token wire format for fixed inputs (the bytes Terra-Ops/jjwt verifies), PyJWT fail-closed verification semantics, PDF extraction and malformed-PDF skipping, the repository embedding configuration on a deterministic local model in the all-MiniLM-L6-v2 module layout, bare-name resolution to the cached `sentence-transformers/all-MiniLM-L6-v2` Hub snapshot, and no execution of a custom module planted in that Hub snapshot without `trust_remote_code` (mutation-checked);
- review-driven commit `16c9962…` replaced overstated sentence-transformers checks with those behavioral tests and corrected the requirements comment (5.6.1 clears the scanner finding; see residual risks);
- `RAG_QUICKSTART.md` dependency checklist corrected to the actual pins.

### Actually Executed / Verified

- local Trivy 0.70.0 (same version the CI action installs) with the exact enforced gate command and same-day DB: `main` exit 1 / 26 findings (reproduces CI); candidate exit 0 / 0 findings. All-severity report: every PyJWT and pypdf finding cleared;
- differential baseline-vs-candidate probe over repository code paths: service JWT byte-identical; 12/12 verify/reject cases identical (`alg=none`, disallowed alg, wrong secret/audience/issuer, expiry, tampering, PEM public key as HMAC secret); embeddings bit-identical on the same weights (max abs diff 0.0); synthetic PDF extraction and malformed-PDF errors identical; on the repository knowledge-base PDF (80 pages) metadata is identical and 2 pages differ only in whitespace/line joining (e.g. `CO\n2e` → `CO2e`);
- independent review (separate reviewer, read-only): no blocking findings; should-fix items (overstated CVE-2026-68770 claim and tests, real-PDF wording) addressed in `16c9962…`;
- exact-head PR CI on `16c9962…`: **26/26 workflow runs `completed / success`** on first attempt, including `CI/CD Pipeline` run `42481811115` (dependency gate on a same-day DB: 0 findings; terra-cortex 75 passed / 0 skipped on Python 3.11; Java 17 terra-sense/terra-ops build+test; dashboard build; E2E neural-flow and command-lifecycle golden path with the terra-cortex Python 3.10 image built from the new pins), `D3 Authenticated Device Messaging Pilot` run `42481811324`, `D4 Device Integration Conformance Pilot` run `42481811183`, `Synthetic Farm Operations Pilot` run `42481811145`, `Software Proof Handoff` run `42481811231`, and all 21 D1 regression proof workflows. The dependency commit `19064fe…` also produced 26/26 successful runs (CI/CD run `42480234885`).

- final exact PR head `6660c614d137022dfab691d37e1921ab1701a1de` produced **26/26 `completed / success`** pull-request workflow runs, including [CI/CD Pipeline run 42482657415](https://github.com/joeylife94/terraneuron-smartfarm-platform/actions/runs/42482657415), [D3 run 42482657340](https://github.com/joeylife94/terraneuron-smartfarm-platform/actions/runs/42482657340), [D4 run 42482657338](https://github.com/joeylife94/terraneuron-smartfarm-platform/actions/runs/42482657338), and [Software Proof Handoff run 42482657375](https://github.com/joeylife94/terraneuron-smartfarm-platform/actions/runs/42482657375). GitHub Codex review on that head completed with no findings; there were no unresolved review threads. The 33 check-run conclusions were 31 success, one neutral Trivy report and one expected skipped image-push job (no blocking failures).

Only the CI/CD Python and E2E jobs build and run terra-cortex. The D1–D4, D2 pilot and handoff workflows start infrastructure, terra-sense and terra-ops only; they show those accepted invariants still hold on the PR head, not that they exercise the changed dependencies.

### Not Verified

- real `sentence-transformers/all-MiniLM-L6-v2` weights were not loaded in evidence available to this review (Hugging Face Hub unreachable from the verification environment; CI container logs are retained only as artifacts). Equivalence was shown bit-exact on a local model with the same module pipeline;
- local Java build was infrastructure-blocked (Maven Central HTTP 429); Java evidence is the CI runs above. Java code is unchanged.

### Known limitations and residual risks (outside the enforced gate)

- sentence-transformers 5.6.x only deprecates (FutureWarning) the local-directory implicit code trust described in CVE-2026-68770; removal is in 6.x, which requires transformers 5 and huggingface-hub ≥1.3. Repository loads by bare Hub name do not execute repo-local code, but a same-named model directory in the process working directory (`/app`) would; exploiting that requires write access to the application directory;
- `chromadb 0.4.22`: CRITICAL CVE-2026-45833 and HIGH CVE-2026-45830 with **no fixed version**; visible in SARIF, excluded from blocking by the documented `ignore-unfixed` policy (pre-existing);
- `chromadb 0.4.22` cannot run on the resolved `numpy 2.x`, so the Chroma vector-store half of the RAG path already fails on `main` and is caught as "RAG disabled"; embedding-model loading still occurs at startup before that failure (pre-existing);
- the repository gate scans direct pins only (no lockfile). The resolved transitive graph carries fixable HIGH findings in `starlette 0.35.1` (via `fastapi 0.109.0`), `transformers 4.48.3` (fixes only in 5.x) and `langchain-core 0.3.86` (fix in 1.2.22); remediation needs separate major-version decisions (pre-existing);
- the embedding model revision is not pinned (bare name resolves to the latest `sentence-transformers/all-MiniLM-L6-v2`) (pre-existing);
- `langchain 0.3.30` MEDIUM CVE-2026-55443 (fix in 1.3.9) is below the gate threshold (pre-existing).

### Follow-up candidate — sentence-transformers 6.x (PR #109, pending Human Acceptance)

Same bounded security-maintenance scope; no product capability, no security-scan policy change, no production or real-model claim. If accepted, it supersedes the `sentence-transformers 5.6.1` / `huggingface-hub 0.25.2` pins above and the 5.6.x local-directory code-trust and `transformers 4.48.3` residuals.

- **Why:** sentence-transformers 5.6.x only *deprecates* implicit trust of a local model directory's own `modeling_*.py` (`import_module_class`: `trust_remote_code or os.path.exists(path)`). 6.0 removes it: any module class outside `sentence_transformers.*` now requires `trust_remote_code=True`, and the repository never sets it. For terra-cortex the residual was a directory named `all-MiniLM-L6-v2` in the process working directory (`/app` in Docker), which the bare model name resolves to before the Hub.
- **Changed:** `sentence-transformers 5.6.1 → 6.2.0`, `huggingface-hub 0.25.2 → 2.4.0`. Resolved graph otherwise unchanged except `transformers 4.48.3 → 5.20.2` (Python 3.10 / Docker) or `5.22.2` (Python 3.11 / CI; newer 5.x require Python ≥3.11), `tokenizers 0.21.4 → 0.23.3`, and new `hf-xet 1.8.0`. torch, numpy, langchain*, chromadb are identical to PR #107.
- **Tests (`tests/test_knowledge_dependency_contract.py`):** new same-named working-directory test (planted custom module, exact repository `HuggingFaceEmbeddings` arguments, bare name) must raise the `trust_remote_code` error and must not import the module. The Hub-cache test now also requires that explicit error instead of tolerating an incidental `ImportError`. A new reference test checks the embedding pipeline against BERT forward + masked mean pooling + L2 normalization on the same weights. The fixture now carries the public repository's legacy `config_sentence_transformers.json`. Both trust tests fail on 5.6.1 (the working-directory module is executed) and pass on 6.2.0.
- **Locally verified (2026-11-08, Python 3.10 and 3.11, accepted PR #107 baseline vs candidate):** terra-cortex suite 77 passed on the candidate; flake8 CI gate 0; `pip check` clean; pip on Python 3.10 resolves the same Hugging Face stack as `uv pip compile`. A cross-environment probe that loaded one MiniLM-shaped model (6 layers, hidden 384, legacy repository layout, random weights) through the repository `HuggingFaceEmbeddings` configuration gave **bit-identical** embeddings and identical token ids across all four stacks, including 256-token truncation, empty input and non-ASCII text. Bare-name resolution through the default `HF_HOME` Hub cache gave the same vectors as the explicit path. The app imports and `RAGAdvisor` behave the same as baseline, including the pre-existing chromadb/NumPy 2 failure. PyPI's advisory data lists 0 advisories for every new version; for `transformers 4.48.3` it lists 36.
- **Pre-rebase exact-head CI** (`765009e…`, stacked on PR #107 code head `16c9962…`; non-STATUS files identical to this rebased candidate): **26/26** pull-request workflow runs `completed / success` on first attempt. [CI/CD Pipeline run 42483324480](https://github.com/joeylife94/terraneuron-smartfarm-platform/actions/runs/42483324480) passed the enforced Trivy gate with `services/terra-cortex/requirements.txt → 0`, and terra-cortex ran 77 passed on Python 3.11, installing transformers 5.22.2 and torch 2.15.0. The Docker build on `python:3.10-slim` installed sentence-transformers 6.2.0, transformers 5.20.2, huggingface-hub 2.4.0, tokenizers 0.23.3, hf-xet 1.8.0 and torch 2.14.1, and E2E neural-flow plus the command-lifecycle golden path passed. The E2E terra-cortex container ran about 53 s, so it never reached the 120 s knowledge-collector delay, and with no `chroma_db` the RAG advisor skips model loading: **E2E did not load the embedding model**. Exact-head CI for the rebased head is recorded on PR #109.
- **Not verified:** real `sentence-transformers/all-MiniLM-L6-v2` weights and live Hub downloads through `huggingface-hub` 2.x (Hub unreachable from the verification environment); a local Trivy run (binary download not permitted there), so the enforced gate result is the exact-head CI recorded on PR #109; a local Docker build (no daemon), so the Python 3.10 image evidence is CI E2E.
- **Residuals:** the bare name still resolves to a same-named working-directory model before the Hub (model substitution, not code execution); the model revision is not pinned; transformers is resolved, not pinned, so CI (3.11) and the Docker image (3.10) run different 5.x minors.

## Not Verified / limitations

All v1.0 non-claims remain in force. The accepted baseline and progression milestones do **not** verify or claim:

- production MQTT client identity, production-grade authentication/authorization/TLS operations, PKI lifecycle, or real provisioning;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, physical-equipment certification, or physical device truth;
- real manufacturer/model-specific adapters or semantics;
- production secrets management/key rotation;
- production HA, backup/restore, DR, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that device-reported or software state equals physical equipment state.

## Remaining risks / destination gates

- D1, D2, D3, and D4 are accepted bounded software destinations; additional isolated ACK/outbox/restart/security/conformance permutations are not authorized without a newly approved destination-level blocker;
- P0 removed buyer-facing claim drift but created no capability claim;
- D3 establishes a bounded authenticated/encrypted synthetic MQTT boundary, not production PKI/provisioning or physical-device trust;
- D4 establishes a reusable synthetic software conformance contract, not real manufacturer/device validation;
- production security/availability and all physical-world trust boundaries remain explicitly outside the accepted software Proof.

## Current destination gate

### `HUMAN REVIEW — PHYSICAL TRUST DECISION`

The pre-authorized software-only progression envelope is complete through D4.

No D5 milestone may be selected automatically. Any next destination involving real hardware, manufacturer-specific semantics, real provisioning, physical actuator truth, electrical interlocks/emergency stop, field safety, unattended control, production HA/DR/load, public production deployment, or certification requires explicit Human Review and a newly approved acceptance boundary.

## Exact Next Action

`HUMAN REVIEW — PHYSICAL TRUST DECISION`

Do not open another bounded development Issue/PR and do not continue scheduled software progression until a human explicitly authorizes the next destination and its trust boundary.

Separately, the bounded dependency-gate security maintenance (PR #107) is **ACCEPTED / MERGED**; this records a software dependency-scanning gate recovery only. It does not open D5, change the physical-trust Human Review gate, or establish deployed runtime or production security readiness.