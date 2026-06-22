# TerraNeuron Audit Report — Retired

> **This document has been retired.**

The previous audit report (dated June 2026) described an earlier repository state and no
longer matches the current code. Several of its headline findings are now stale, for example:

- It claimed security was disabled via `anyRequest().permitAll()`. The current
  [`SecurityConfig`](services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java)
  enforces role-based access and `anyRequest().authenticated()`.
- It claimed **0% test coverage**. terra-ops now has unit tests for security, event
  validation, insight parsing, the SafetyValidator, and the approval lifecycle.
- It claimed **no CI/CD pipeline**. `.github/workflows/` now contains `ci-cd.yml` and
  `security-scan.yml`.
- It claimed the command consumer, InfluxDB writer, and MQTT gateway were absent/unwired.
  terra-sense now includes `DeviceCommandConsumer`, `InfluxDbWriterService`, and
  `MqttGatewayService`.
- It claimed the JWT secret had an insecure in-repo fallback. The config is now
  `jwt.secret=${JWT_SECRET}` with no fallback.

For the current, verified status of what is implemented, enforced, advisory, or still missing,
see **[STATUS.md](STATUS.md)** — the single source of truth.
