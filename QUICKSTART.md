# TerraNeuron — Bounded Software Proof Quickstart

> **Current authority:** [`STATUS.md`](STATUS.md)  
> **Accepted baseline:** `PROOF v1.0 FREEZE / HUMAN REVIEW PASSED — PROGRESSION ACTIVE`

This guide is a reproducible handoff path for the **current synthetic Compose software Proof**. It intentionally does not describe TerraNeuron as production-validated and does not carry forward historical fixed success-rate, data-loss, latency, throughput, or load-test claims as current acceptance evidence.

## What this proves

The handoff smoke executes the repository's current bounded command-lifecycle software Proof across the Compose integration path:

`synthetic device state → action plan → human approval → software safety gates → transactional outbox → command transport → synthetic terminal ACK → terminal Terra-Ops plan state`

A successful run means that this bounded software path executed successfully in the environment where the script ran. It does **not** establish physical equipment behavior or production readiness.

## Prerequisites

- Docker with Docker Compose v2 (`docker compose`)
- Python 3.10+
- Python package `requests`
- `curl`
- sufficient local resources to build and run the required Compose services

Install the Python dependency if needed:

```bash
python3 -m pip install requests
```

## One-command handoff Proof

From the repository root:

```bash
bash tests/software-proof-handoff.sh
```

The script:

1. validates the current Compose configuration;
2. builds and starts the bounded infrastructure/application services required by the proof;
3. waits for MySQL, Terra-Sense, and Terra-Ops readiness;
4. executes `tests/command-lifecycle-test.py`;
5. exits non-zero on failure and prints an explicit bounded software-Proof PASS on success;
6. tears down the Compose stack and volumes by default.

To keep the stack running for inspection after the proof:

```bash
TERRANEURON_HANDOFF_KEEP_STACK=1 bash tests/software-proof-handoff.sh
```

Then inspect state/logs with:

```bash
docker compose ps
docker compose logs --tail=100 terra-sense terra-ops kafka mosquitto
```

Stop and remove the retained stack when finished:

```bash
docker compose down -v
```

## Manual readiness checks

If you start the stack manually, the software services used by this handoff expose these local readiness endpoints:

```bash
curl --fail http://localhost:8081/actuator/health  # terra-sense
curl --fail http://localhost:8080/actuator/health  # terra-ops
```

Other repository services and broader E2E scenarios remain available in the main CI pipeline and test suite, but they are not required to interpret this one-command handoff Proof.

## Evidence rule

Do not treat documentation, container startup, code existence, or an agent report as PASS. For a given revision, use the actual script exit status and exact-head CI/workflow results as executable evidence. The authoritative accepted state and limitations are recorded in [`STATUS.md`](STATUS.md).

## Explicit non-claims

This quickstart and the handoff smoke do **not** verify or claim:

- production MQTT client identity, authentication, authorization, or TLS;
- physical actuator interlocks, emergency-stop behavior, manufacturer controller limits, certification, or physical device truth;
- manufacturer/model-specific capability adapters;
- production secrets management or key rotation;
- production HA, backup/restore, disaster recovery, load testing, or general fault-injection maturity;
- unattended autonomous control;
- that software/device-reported state equals physical equipment state.

For the complete accepted evidence ledger, progression milestones, remaining risks, and exact next action, read [`STATUS.md`](STATUS.md) before making any product or deployment claim.
