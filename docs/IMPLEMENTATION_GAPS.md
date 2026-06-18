# 📋 TerraNeuron Implementation Gaps

> **Last Updated:** 2026-06-18  
> **Status:** Architecture Prototype — Demonstration-Ready  
> **Reference:** See [../AUDIT_REPORT.md](../AUDIT_REPORT.md) for detailed audit findings

This document catalogs the gap between documented/claimed features and actual implementation. It complements PROJECT_STATUS.md by explaining WHY each gap exists and what's needed to close it.

---

## Status Category Definitions

- **Implemented** — Feature works end-to-end; code is in place and connected
- **Partially implemented** — Core code exists; some functionality missing or disabled
- **Scaffolded** — File/class structure exists; not wired into service or not functional
- **Configured** — Infrastructure/settings present; application code not written
- **Demo-only** — Works in test scenario; not production-ready
- **Not implemented** — No code; planned only

---

## Critical Gaps (Must Fix Before Production)

### 1. Security: RBAC Not Enforced

**Status:** Partially implemented (disabled)

**What exists:**
- ✅ `services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java`
- ✅ `services/terra-ops/src/main/java/com/terraneuron/ops/security/JwtTokenProvider.java`
- ✅ `services/terra-ops/src/main/java/com/terraneuron/ops/security/JwtAuthenticationFilter.java`
- ✅ Role definitions (ADMIN, OPERATOR, VIEWER) in code

**What's missing:**
- ❌ **Lines 50-52 commented out** — RBAC rules disabled
- ❌ **Line 54 active** — `.anyRequest().permitAll()` allows all unauthenticated access
- ❌ **No JWT validation** — Requests bypass `JwtAuthenticationFilter` due to `permitAll()`

**Why disabled:**
- Development convenience — easier testing without authentication

**What breaks:**
- All APIs accessible without token
- Roles never enforced
- Anyone can approve/reject action plans

**How to fix:**
```java
// SecurityConfig.java line 42-54
.authorizeHttpRequests(auth -> auth
    .requestMatchers("/").permitAll()
    .requestMatchers("/health", "/actuator/**").permitAll()
    .requestMatchers("/swagger-ui/**", "/api-docs/**", "/v3/api-docs/**").permitAll()
    .requestMatchers("/api/auth/**").permitAll()
    
    // ENABLE these (currently commented):
    .requestMatchers("/api/actions/**").hasAnyRole("ADMIN", "OPERATOR")
    .requestMatchers("/api/insights/**").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")
    
    // Remove this line:
    // .anyRequest().permitAll()
    
    // Replace with:
    .anyRequest().authenticated()
)
```

**Effort:** 1 day

---

### 2. Security: Hardcoded Demo Users

**Status:** Partially implemented (development-only)

**What exists:**
- ✅ `services/terra-ops/src/main/java/com/terraneuron/ops/controller/AuthController.java` lines 25-29
- ✅ BCryptPasswordEncoder configured
- ✅ `users` table exists in MySQL schema (`infra/mysql/init.sql`)

**What's missing:**
- ❌ **No database lookup** — AuthController uses hardcoded in-memory Map
- ❌ **Passwords not hashed** — Plain-text comparison: `user.password.equals(request.getPassword())`
- ❌ **Users table unused** — Database schema prepared but code ignores it

**Hardcoded credentials:**
```java
private static final Map<String, UserInfo> USERS = Map.of(
    "admin", new UserInfo("admin", "admin123", "ROLE_ADMIN,ROLE_OPERATOR"),
    "operator", new UserInfo("operator", "operator123", "ROLE_OPERATOR"),
    "viewer", new UserInfo("viewer", "viewer123", "ROLE_VIEWER")
);
```

**Why this way:**
- Rapid development; no database lookup overhead

**What breaks:**
- Production cannot manage users
- Credentials visible in repository
- No password security (BCrypt never used)

**How to fix:**
1. Create `UserService` class to query `users` table
2. Use `BCryptPasswordEncoder` to verify passwords
3. Replace `AuthController` hardcoded Map with DB lookup

**Effort:** 1.5 days

---

### 3. Security: JWT Secret Hardcoded

**Status:** Partially implemented (exposed)

**What exists:**
- ✅ `services/terra-ops/src/main/resources/application.properties` line 36
- ✅ Environment variable support: `${JWT_SECRET:...}`

**What's missing:**
- ❌ **Fallback secret exposed** — `terraneuron-secret-key-2025-phase3-production-ready-256bit-key`
- ❌ **Not in .env** — Secret must be passed via environment; defaults to hardcoded value
- ❌ **Visible in repository** — Anyone cloning repo can see the "production" key

**Why this way:**
- Convenience; developers don't need to set environment variables locally

**What breaks:**
- Anyone with repo access can forge JWT tokens
- Production key publicly known if committed

**How to fix:**
```properties
# Remove fallback, require env var:
jwt.secret=${JWT_SECRET}  # No :... fallback

# In docker-compose.yml and .env.prod:
JWT_SECRET=<strong-random-256-bit-key>
```

**Effort:** 0.5 day

---

### 4. Device Control Loop: Command Consumer Not Wired

**Status:** Scaffolded (file exists, not connected)

**What exists:**
- ✅ `services/terra-sense/src/main/java/com/terraneuron/sense/service/DeviceCommandConsumer.java` — complete implementation
- ✅ `@KafkaListener(topics = "terra.control.command")` annotation present
- ✅ `MqttGatewayService.publishCommand()` method exists
- ✅ Kafka topic `terra.control.command` created and published to by terra-ops

**What's missing:**
- ❌ **DeviceCommandConsumer not wired as @Service** — Consumer file exists but is not instantiated by Spring
- ❌ **No listener container factory** — Kafka listener container not configured for command topic
- ❌ **No test** — No verification that messages are consumed

**Why incomplete:**
- Implementation started but not completed
- terra-sense focuses on ingestion, not on device control

**What breaks:**
- terra-ops approves action plans → publishes to `terra.control.command`
- **Nobody consuming the messages**
- Devices never receive commands
- Entire action loop broken

**Evidence:**
```bash
kafka-console-consumer --topic terra.control.command --bootstrap-server localhost:9092
# Messages appear here after approval, but nothing processes them
```

**How to fix:**
1. Ensure `DeviceCommandConsumer.java` is annotated `@Service`
2. Verify `KafkaConfig` registers listener container factory
3. Add integration test: approve plan → consume from topic
4. Wire `MqttGatewayService` to actually publish commands to MQTT

**Effort:** 2 days

---

### 5. Test Coverage: Zero Automated Tests

**Status:** Not implemented

**What exists:**
- ✅ `tests/neural-flow-test.py` — manual E2E test script
- ✅ `tests/simulation.py` — data generator
- ❌ **No unit tests** — No `src/test/` directories in any service
- ❌ **No integration tests** — No container-based tests
- ❌ **No pytest suite** — Manual tests not CI/CD-ready

**What's missing:**
- ❌ JUnit 5 tests for critical logic (SafetyValidator, JwtTokenProvider, ActionPlan state machine)
- ❌ Mockito mocks for dependencies
- ❌ Automated E2E suite (pytest)
- ❌ CI/CD pipeline

**Current test flow:**
1. Developer manually runs `tests/neural-flow-test.py`
2. Logs printed to console
3. No assertion checking or failure detection
4. No regression baseline

**Why missing:**
- Fast prototyping; tests deferred
- Manual testing sufficient for demonstration

**What breaks:**
- No regression detection on commits
- Refactoring risk high
- Cannot deploy with confidence
- Cannot run in CI/CD

**How to fix:**
1. Create `src/test/java/com/terraneuron/ops/service/SafetyValidatorTest.java` (4h)
2. Create JWT auth tests (2h)
3. Create Kafka consumer/producer integration tests (3h)
4. Adapt `tests/neural-flow-test.py` to pytest framework (2h)
5. Set up GitHub Actions pipeline (4h)

**Effort:** 8 days

---

## High-Priority Gaps

### 6. MQTT Device Integration: Listener Not Implemented

**Status:** Scaffolded

**What exists:**
- ✅ `services/terra-sense/build.gradle` includes `org.eclipse.paho:org.eclipse.paho.client.mqttv3`
- ✅ `services/terra-sense/src/main/java/com/terraneuron/sense/config/MqttConfig.java` — MQTT client bean
- ✅ `services/terra-sense/src/main/java/com/terraneuron/sense/service/MqttGatewayService.java` — gateway for outbound commands
- ✅ `docker-compose.yml` includes Mosquitto broker

**What's missing:**
- ❌ **No MQTT listener** — No class consuming MQTT topics from IoT devices
- ❌ **No device subscription** — `MqttCallback` implementation incomplete
- ❌ **HTTP-only ingestion** — Only `POST /api/v1/ingest/sensor-data` works

**Current flow:**
- IoT devices → **MQTT Mosquitto broker (listening, no consumers)**
- Devices can also send HTTP → terra-sense (works)

**Why incomplete:**
- Architecture prioritized HTTP ingestion
- MQTT design drafted but not implemented

**What breaks:**
- MQTT devices cannot connect via `mqtt://mosquitto:1883`
- Must use HTTP instead
- Cannot bid-direction communicate (no MQTT status feedback)

**How to fix:**
1. Implement `MqttSensorListener` service
2. Subscribe to `terra/devices/+/+/data` MQTT topic
3. Parse MQTT payload → SensorData
4. Convert to Kafka message
5. Add integration test with test MQTT client

**Effort:** 6 days

---

### 7. InfluxDB Not Integrated

**Status:** Configured but not integrated

**What exists:**
- ✅ `services/terra-sense/build.gradle` includes `com.influxdb:influxdb-client-java`
- ✅ `docker-compose.yml` runs InfluxDB service
- ✅ Environment variables configured in docker-compose:
  ```yaml
  INFLUXDB_URL: http://influxdb:8086
  INFLUXDB_TOKEN: terra-token-2025
  ```
- ✅ `services/terra-cortex/requirements.txt` includes InfluxDB SDK

**What's missing:**
- ❌ **No InfluxDB writer** — No service class writing measurements
- ❌ **No data in InfluxDB** — All data goes to MySQL only
- ❌ **Grafana dashboards empty** — InfluxDB metrics queries return no results

**Current data flow:**
- Sensor → terra-sense → Kafka (raw-sensor-data)
- Kafka → terra-cortex → Kafka (processed-insights)
- Kafka → terra-ops → MySQL (persisted)
- **InfluxDB (untouched)**

**Why not implemented:**
- Time-series analysis deferred (Roadmap Phase 4)
- MySQL sufficient for prototype

**What breaks:**
- Time-series queries fail
- Trend analysis in terra-cortex missing
- Cannot track sensor history efficiently
- Grafana dashboards non-functional

**How to fix:**
1. Create `services/terra-sense/src/main/java/.../InfluxDBWriterService.java`
2. Subscribe to Kafka `raw-sensor-data` topic
3. Write to InfluxDB:
   ```
   measurement: "insights"
   tags: {farm_id, sensor_type, status}
   fields: {value, confidence}
   timestamp: insight.detectedAt
   ```
4. Add integration test

**Effort:** 4 days

---

### 8. Event Schema Mismatches

**Status:** Partially implemented (inconsistent)

**Issue 1: Event Type Naming**

ActionPlanService publishes:
```java
"type", "terra.ops.command.execute"
```

But CloudEvents spec defines:
```python
type: str = "terra.ops.command.executed"  # in cloudevents_models.py
```

**Result:** Event consumers looking for `terra.ops.command.executed` won't find `terra.ops.command.execute`

**How to fix:** Standardize event type naming across all services

**Effort:** 0.5 day

---

**Issue 2: SensorData Schema Mismatch**

terra-sense (SensorData.java):
```java
private String sensorId;        // ← Sent but not used
private String sensorType;
private Double value;
private String farmId;
private String unit;
```

terra-cortex expects (models.py):
```python
farmId: str
sensorType: str
value: float
timestamp: Optional[datetime] = None
```

**Result:** `sensorId` wasted bandwidth; inconsistent metadata

**How to fix:** Align schemas — both include: `sensor_id`, `farm_id`, `sensor_type`, `value`, `unit`, `timestamp`

**Effort:** 1 day

---

## Medium-Priority Gaps

### 9. Input Validation Missing

**Status:** Partially implemented

**What exists:**
- ✅ Basic validation in SensorData.java: `@NotNull`, `@NotBlank`

**What's missing:**
- ❌ Range checks: negative temperatures, humidity >100% accepted
- ❌ Enum validation: invalid sensorType values pass through
- ❌ Sensor ID format validation

**How to fix:**
```java
@Min(-40) @Max(60) private Double value;  // temperature
@Min(0) @Max(100) private Double humidity;
@Pattern(regexp = "^(temperature|humidity|co2|soil|light)$") 
private String sensorType;
```

**Effort:** 1 day

---

### 10. CI/CD Pipeline Not Defined

**Status:** Not implemented

**What exists:**
- ✅ `.github/workflows/` directory
- ❌ No workflow files

**What's missing:**
- ❌ Build pipeline (Gradle, Maven, npm)
- ❌ Test automation (JUnit, pytest)
- ❌ Docker image building
- ❌ Deployment automation

**How to fix:**
1. Create `.github/workflows/build.yml` — Gradle/npm build + test
2. Create `.github/workflows/test.yml` — Run test suites
3. Create `.github/workflows/docker.yml` — Build and push images
4. Add to `docker-compose.yml` health checks for startup ordering

**Effort:** 4 days

---

### 11. CORS Wildcard (Security Risk)

**Status:** Partially implemented (insecure)

**What exists:**
- ✅ CORS configuration in place
- ❌ Allows `*` (all origins)

**What's missing:**
- ❌ Whitelist of allowed origins
- ❌ Environment-based configuration

**How to fix:**
```properties
# terra-gateway/application.properties
spring.cloud.gateway.globalcors.cors-configurations.[/**].allowed-origins=https://farm.terraneuron.io,https://admin.terraneuron.io

# terra-ops/SecurityConfig.java
configuration.setAllowedOrigins(List.of(
    System.getenv("ALLOWED_ORIGINS").split(",")
));
```

**Effort:** 0.5 day

---

## Low-Priority Gaps

### 12. Schema Versioning Not Implemented

**Status:** Not implemented

**What exists:**
- ✅ `infra/mysql/init.sql` — one-time schema

**What's missing:**
- ❌ Flyway/Liquibase migrations
- ❌ Version control for schema changes

**How to fix:**
1. Add Flyway dependency to terra-ops `build.gradle`
2. Create `src/main/resources/db/migration/V1__Initial_Schema.sql`
3. Configure `spring.flyway.baseline-on-migrate=true`

**Effort:** 2 days

---

### 13. Production Secrets Not Managed

**Status:** Not implemented

**What exists:**
- ✅ `docker-compose.yml` with hardcoded passwords
- ❌ No `.env` file
- ❌ No Vault/AWS Secrets integration

**Exposed secrets:**
```yaml
MYSQL_PASSWORD: terra2025
INFLUXDB_PASSWORD: terra2025
REDIS_PASSWORD: terra2025
GF_SECURITY_ADMIN_PASSWORD: terra2025
```

**How to fix:**
1. Create `.env.example` with placeholders
2. Add `.env` to `.gitignore`
3. Generate strong random passwords in `.env` (not committed)
4. Update docker-compose to use `.env`

**Effort:** 1 day

---

### 14. Kubernetes Manifests Not Created

**Status:** Not implemented

**What exists:**
- ✅ Docker images for all services
- ❌ No K8s deployment manifests

**What's missing:**
- ❌ Deployment YAML
- ❌ Service definitions
- ❌ ConfigMaps for settings
- ❌ Secrets for credentials
- ❌ Ingress configuration

**How to fix:**
1. Create `k8s/deployment/terra-ops.yaml` — Deployment, Service, ConfigMap, Secret
2. Repeat for terra-sense, terra-cortex, terra-gateway
3. Create `k8s/stateful/kafka.yaml` — StatefulSet
4. Create `k8s/ingress.yaml` — Ingress controller

**Effort:** 6 days

---

## Summary Table

| Gap | Category | Status | Effort | Priority |
|-----|----------|--------|--------|----------|
| RBAC Not Enforced | Security | Partially implemented | 1d | P0 |
| Hardcoded Users | Security | Partially implemented | 1.5d | P0 |
| JWT Secret Exposed | Security | Partially implemented | 0.5d | P0 |
| Command Consumer Not Wired | Architecture | Scaffolded | 2d | P0 |
| Zero Test Coverage | Quality | Not implemented | 8d | P0 |
| MQTT Listener | Integration | Scaffolded | 6d | P1 |
| InfluxDB Writer | Integration | Scaffolded | 4d | P1 |
| Event Schema Mismatches | Data | Partially implemented | 1.5d | P1 |
| Input Validation | Quality | Partial | 1d | P2 |
| CI/CD Pipeline | DevOps | Not implemented | 4d | P2 |
| CORS Wildcard | Security | Partial | 0.5d | P2 |
| Schema Versioning | Ops | Not implemented | 2d | P3 |
| Secrets Management | Ops | Not implemented | 1d | P3 |
| Kubernetes Manifests | Ops | Not implemented | 6d | P3 |

---

## Effort Estimate for Production-Readiness

| Sprint | Focus | Effort | Cumulative |
|--------|-------|--------|-----------|
| **Sprint 1** | Security | 3.5d | 3.5d |
| **Sprint 2** | Integrations | 7d | 10.5d |
| **Sprint 3** | Testing | 8d | 18.5d |
| **Sprint 4** | Operations | 9d | 27.5d |

**Total: ~2-3 weeks** for a team of 2 engineers

---

## Notes

- This is an **architecture prototype** demonstrating production-grade design patterns, not a production system
- Core E2E pipeline (HTTP → Kafka → AI → MySQL) is functional
- Most gaps are about security hardening, test coverage, and integration completion — not fundamental design issues
- The codebase is well-structured and could reach production-grade with focused execution on this backlog

