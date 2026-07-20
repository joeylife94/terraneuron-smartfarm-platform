# TerraNeuron Audit Report — Retired

> **Retired:** 2026-07-20  
> **Replacement:** [`STATUS.md`](STATUS.md)

This file is retained only to prevent old links from breaking. It is not an active audit, release gate or implementation-status document.

The former audit described an earlier repository state and included findings that are no longer true, including claims that:

- Spring Security allowed all requests;
- JWT secrets used an insecure in-repository fallback;
- Terra-Ops had no meaningful test coverage;
- CI/CD and security scanning were absent;
- Terra-Sense command, InfluxDB and MQTT runtime paths were missing;
- Device Safety layer 4 was only advisory.

The current repository now includes enforced RBAC, database-backed users, separated user/service JWT boundaries, runtime schema validation, Kafka retry/DLT handling, transactional outbox delivery, command idempotency and ACK correlation, Flyway schema ownership, CI security gates and a two-stage fail-closed Device Safety Gate.

For current verified behavior, remaining operational limits and recommended follow-up work, use [`STATUS.md`](STATUS.md). For the safety implementation specifically, use [`docs/DEVICE_SAFETY_GATE.md`](docs/DEVICE_SAFETY_GATE.md).
