# TerraNeuron Deployment Guide

> **Last updated:** 2026-07-20  
> **Validated target:** local Docker Compose integration stack  
> **Production status:** not production-ready

This document describes the repository-supported local deployment path and the controls required before a real production rollout. It does not claim that the included Compose topology, credentials or example infrastructure are suitable for unattended physical control.

Current implementation status and known gaps are maintained in [`../STATUS.md`](../STATUS.md).

## 1. Local integration deployment

### Requirements

- Docker Engine 24+
- Docker Compose v2
- Git
- approximately 8 GB RAM for the full stack

### Clone and configure

```bash
git clone https://github.com/joeylife94/terraneuron-smartfarm-platform.git
cd terraneuron-smartfarm-platform
cp .env.example .env
```

Replace all local placeholders before starting a shared environment:

```dotenv
JWT_SECRET=<random-user-jwt-secret-at-least-32-bytes>
SERVICE_AUTH_JWT_SECRET=<independent-cortex-ops-secret-at-least-32-bytes>
DEVICE_SAFETY_JWT_SECRET=<independent-ops-sense-secret-at-least-32-bytes>
REDIS_PASSWORD=<random-redis-password>
```

Do not reuse one key for multiple trust boundaries.

The default Compose load includes `docker-compose.yml` and `docker-compose.override.yml`. The override wires:

- Redis-backed command and device-state registries;
- Device Safety freshness and TTL settings;
- Cortex → Ops service authentication;
- Ops → Sense Device Safety authentication;
- Cortex transactional and deduplication settings.

### Start and inspect

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=200
```

Stop the stack with:

```bash
docker compose down
```

Use `docker compose down -v` only when intentionally deleting local state.

## 2. Service endpoints

| Component | URL | Purpose |
|---|---|---|
| Terra-Gateway | `http://localhost:8000` | gateway and rate limiting |
| Terra-Sense | `http://localhost:8081` | ingestion, device status and command dispatch |
| Terra-Cortex | `http://localhost:8082` | analysis API and health |
| Terra-Ops | `http://localhost:8080` | authentication and action-plan APIs |
| Terra-Dashboard | `http://localhost:3001` | operator interface |
| Grafana | `http://localhost:3000` | provisioned dashboards |
| Prometheus | `http://localhost:9090` | metrics and alert rules |
| InfluxDB | `http://localhost:8086` | time-series storage |

Swagger/OpenAPI exposure depends on the active service profile. Prefer service health endpoints and the repository E2E flow for deployment validation rather than treating an open port as proof of readiness.

## 3. Device Safety configuration

Default local values:

```dotenv
DEVICE_STATE_FRESHNESS_SECONDS=120
DEVICE_STATE_TTL_SECONDS=600
```

Requirements:

- TTL must be greater than the freshness window.
- Freshness must be tuned to actual heartbeat cadence and network behavior.
- Redis unavailability intentionally blocks physical device commands.
- The exact non-actuating `alert` / `alert_only` path does not require Redis device state.

See [`DEVICE_SAFETY_GATE.md`](DEVICE_SAFETY_GATE.md).

## 4. Authentication boundaries

TerraNeuron currently uses three independent JWT boundaries:

| Boundary | Secret | Purpose |
|---|---|---|
| interactive user → Terra-Ops | `JWT_SECRET` | access/refresh tokens and RBAC |
| Terra-Cortex → Terra-Ops | `SERVICE_AUTH_JWT_SECRET` | internal crop-read service calls |
| Terra-Ops → Terra-Sense | `DEVICE_SAFETY_JWT_SECRET` | internal Device Safety evaluation |

Production deployments must provide secrets externally. Repository-local placeholders are for development only.

Refresh tokens are currently stateless: they are not persisted, rotated or individually revoked. This is a known production gap, not a deployment feature.

## 5. Container images

The main workflow publishes both repository-scoped and legacy-compatible GHCR tags for Java services:

```text
ghcr.io/joeylife94/terraneuron-smartfarm-platform/terra-sense:<tag>
ghcr.io/joeylife94/terraneuron-smartfarm-platform/terra-ops:<tag>

ghcr.io/joeylife94/terraneuron-terra-sense:<tag>
ghcr.io/joeylife94/terraneuron-terra-ops:<tag>
```

Prefer immutable commit-SHA tags for controlled deployments. `latest` is convenient for local evaluation but does not provide a rollback identity.

## 6. Pre-production requirements

The following controls are required before exposing TerraNeuron to real equipment or public networks.

### Network and broker security

- MQTT client certificates or another strong client-identity mechanism;
- per-device topic authorization;
- MQTT TLS and certificate rotation;
- encrypted Kafka, database and Redis connections where traffic crosses trust boundaries;
- firewall and private-network policies that expose only required entry points.

### Physical safety

- manufacturer/model-specific capability adapters;
- electrical and controller-level interlocks;
- emergency stops and safe local fallback behavior;
- verified heartbeat and clock-skew contracts;
- tests proving that invalid or forged state cannot authorize physical actuation.

The application Device Safety Gate is defense in depth. It does not replace certified physical controls.

### Identity and secrets

- managed secrets storage and automated rotation;
- refresh-token persistence, rotation and revocation;
- account administration, MFA and password reset;
- auditable operator/device provisioning and removal.

### Availability and recovery

- highly available Kafka, Redis, MySQL, InfluxDB, MQTT and monitoring services;
- backup and restore procedures tested against actual recovery objectives;
- rolling-upgrade and schema-migration runbooks;
- alert routing and on-call ownership;
- load, soak and fault-injection evidence.

## 7. Deployment verification

A deployment is not considered healthy solely because containers are running. Verify at least:

1. all service readiness/health endpoints;
2. Prometheus target health and rule loading;
3. Grafana dashboard provisioning;
4. authenticated operator login and RBAC behavior;
5. sensor ingestion through Kafka and persistence;
6. action-plan creation and human approval;
7. approval-time Device Safety blocking with no outbox row;
8. successful safety revalidation after device-state recovery;
9. pre-dispatch safety failure with zero MQTT publication;
10. normal MQTT publication, terminal ACK correlation and duplicate suppression;
11. dependency-security and service test pipelines for the deployed commit.

The repository GitHub Actions pipeline exercises the local Compose integration path. A production environment still requires deployment-specific verification and evidence.

## 8. Rollback policy

Use immutable image tags and forward database migrations.

- Application rollback must remain compatible with the already-applied schema.
- MySQL DDL may auto-commit; do not assume transactional rollback of migrations.
- Back up production data before migrations that may rebuild or lock populated tables.
- Never restore a local Compose volume as a substitute for a tested production recovery procedure.

See [`TERRA_OPS_SCHEMA_MIGRATIONS.md`](TERRA_OPS_SCHEMA_MIGRATIONS.md).

## 9. Related documentation

- [`../STATUS.md`](../STATUS.md) — implementation status and known gaps
- [`DEVICE_SAFETY_GATE.md`](DEVICE_SAFETY_GATE.md) — safety guarantees and limitations
- [`SERVICE_AUTH.md`](SERVICE_AUTH.md) — internal service authentication
- [`TERRA_OPS_SCHEMA_MIGRATIONS.md`](TERRA_OPS_SCHEMA_MIGRATIONS.md) — database migration behavior
- [`SECURITY_SCANNING.md`](SECURITY_SCANNING.md) — dependency-security enforcement
