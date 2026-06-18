# Terraneuron Repository Audit Report

**Audit Date:** June 18, 2026  
**Project Version:** v2.1.0  
**Audit Focus:** Documentation vs Implementation Alignment, Security, Event Contracts, Runtime Configuration, Test Coverage  
**Status:** ⚠️ **SIGNIFICANT GAPS IDENTIFIED** — Not Production-Ready Despite Claims

---

## Executive Summary

The TerraNeuron platform has a well-designed MSA architecture with comprehensive documentation. However, there is a **critical mismatch between documented capabilities and actual implementation**:

- ✅ **Core E2E pipeline works:** HTTP → Kafka → terra-cortex → MySQL (sensor data → insights)
- ✅ **Hybrid AI infrastructure present:** CloudEvents, trace_id, 4-layer safety validation, audit logging
- ❌ **Security disabled:** JWT implemented but RBAC bypassed via `permitAll()`, hardcoded users/secrets
- ❌ **MQTT integration incomplete:** Files exist but not wired; `terra.control.command` published but not consumed
- ❌ **Test coverage at 0%:** No unit tests, no integration test suites
- ❌ **Multiple infrastructure features non-functional:** InfluxDB, MQTT listener, command feedback loop

### Production-Readiness Assessment

| Category | Claimed | Actual | Gap |
|----------|---------|--------|-----|
| E2E Pipeline | ✅ Complete | ✅ Functional | None |
| Security/Auth | ✅ Phase 3 Complete | ⚠️ Disabled | **Critical** |
| Data Persistence | ✅ Multi-store | ⚠️ MySQL only | **High** |
| MQTT Integration | ✅ Implemented | ❌ Scaffolded | **Critical** |
| Test Coverage | ✅ Validated | ❌ 0% | **Critical** |
| Device Control Loop | ✅ Complete | ❌ Incomplete | **Critical** |

**Verdict:** ⛔ **NOT production-ready**. Current state is a **functional prototype** suitable for portfolio demo, not deployment.

---

## 1. Documentation vs Implementation Mismatch

### Documentation Truth Table

| Claim (from README/PROJECT_STATUS) | Evidence | Actual Status | Recommended Wording |
|---|---|---|---|
| "✅ Production-Ready (January 31, 2026)" | README.md | Partially; Core demo works, security/tests missing | "Demonstration-Ready; requires security hardening and test coverage for production" |
| "✅ JWT Authentication implemented" | docs/PROJECT_STATUS.md says Phase 3 Complete | Implemented but disabled; RBAC commented out | "JWT infrastructure implemented; authorization rules disabled for development" |
| "✅ Role-based Access Control" | docs/PROJECT_STATUS.md Phase 3 | Code exists but commented; using `permitAll()` | "RBAC code drafted; currently disabled (uses `permitAll()`)" |
| "✅ MQTT integration complete" | ROADMAP.md lists as completed | Code scaffolded; not actually consuming messages | "MQTT broker configured; device listener not yet operational" |
| "✅ InfluxDB data persistence" | ROADMAP.md lists as completed | Dependency only; no actual writes | "InfluxDB configured in infrastructure; writer service not implemented" |
| "✅ E2E pipeline verified 100% success" | PROJECT_SUMMARY.md test metrics | Tests exist but manual/custom only | "Manual E2E tests pass; no automated test suite" |
| "✅ `terra.control.command` consumer working" | docs/API_REFERENCE.md | Topic published by terra-ops; not consumed anywhere | "Topic defined and produced; no active consumer" |
| "✅ 4-Layer Safety Validation implemented" | SafetyValidator.java, docs/ACTION_PROTOCOL.md | Implemented in code | ✅ Correct |
| "✅ CloudEvents v1.0 standard" | cloudevents_models.py | Implemented in code | ✅ Correct |
| "✅ Hybrid AI (Local + LLM + RAG)" | terra-cortex implementation | Implemented in code | ✅ Correct |

### Root Causes

1. **Documentation written for target state, not current state** — PROJECT_STATUS.md was updated Feb 2026 but several items marked ✅ without implementation verification
2. **Roadmap conflated with actual delivery** — Items listed as "COMPLETED" in ROADMAP.md but scaffolding only exists (MQTT, InfluxDB)
3. **Development shortcuts not documented** — Security disabled for "easy testing" but not flagged as blocking issue

---

## 2. Security Findings

### 🔴 CRITICAL: Authentication/Authorization Disabled

**File:** `services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java`

```java
// Line 54: All requests allowed regardless of token
.anyRequest().permitAll()
```

**Impact:** 
- All API endpoints accessible without JWT token
- RBAC rules (lines 51-52) are commented out
- Any unauthenticated client can: approve action plans, trigger farm commands, access sensitive data

**Evidence:**
```java
// Commented out (lines 51-52):
// .requestMatchers("/api/actions/**").hasAnyRole("ADMIN", "OPERATOR")
// .requestMatchers("/api/insights/**").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")
```

**Fix:** Enable RBAC by uncommenting and testing role-based access.

---

### 🔴 CRITICAL: Hardcoded Users (Development Only)

**File:** `services/terra-ops/src/main/java/com/terraneuron/ops/controller/AuthController.java` (lines 25-29)

```java
private static final Map<String, UserInfo> USERS = Map.of(
    "admin", new UserInfo("admin", "admin123", "ROLE_ADMIN,ROLE_OPERATOR"),
    "operator", new UserInfo("operator", "operator123", "ROLE_OPERATOR"),
    "viewer", new UserInfo("viewer", "viewer123", "ROLE_VIEWER")
);
```

**Impact:**
- No database lookup for credentials
- Comment says "replace with database in production" but code is unchanged
- Credentials visible in repository

**Fix:** 
- Integrate with users table (schema exists in MySQL)
- Use BCryptPasswordEncoder for hashing
- Externalize credentials

---

### 🔴 CRITICAL: JWT Secret Hardcoded

**File:** `services/terra-ops/src/main/resources/application.properties` (line 36)

```properties
jwt.secret=${JWT_SECRET:<redacted-insecure-demo-fallback>}
```

**Impact:**
- Default fallback uses weak, repository-visible key
- Environment variable `JWT_SECRET` not set in docker-compose
- Anyone with code access can forge tokens

**Fix:**
- Require `JWT_SECRET` environment variable (no fallback)
- Store in HashiCorp Vault or AWS Secrets Manager
- Update docker-compose to inject from `.env.prod` (gitignored)

---

### 🟡 HIGH: CORS Wildcard Origin

**Files:**
- `services/terra-gateway/src/main/resources/application.properties`
- `services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java`

```properties
# terra-gateway
spring.cloud.gateway.globalcors.cors-configurations.[/**].allowed-origins=*
```

```java
// terra-ops
configuration.setAllowedOrigins(List.of("*"));
```

**Impact:**
- Any domain can make requests to APIs
- Vulnerable to CSRF/clickjacking from malicious sites

**Fix:**
- Whitelist specific origins: `List.of("https://farm.terraneuron.io", "https://admin.terraneuron.io")`
- Use environment variable for deployment flexibility

---

### 🟡 HIGH: Weak Default Credentials in Docker Compose

**File:** `docker-compose.yml`

```yaml
# Line ~160
environment:
  MYSQL_ROOT_PASSWORD: root
  MYSQL_PASSWORD: terra2025
  
# Line ~175
DOCKER_INFLUXDB_INIT_PASSWORD: terra2025

# Line ~100
command: redis-server --requirepass terra2025

# Line ~192
GF_SECURITY_ADMIN_PASSWORD: terra2025
```

**Impact:**
- All default passwords visible in repository
- Easy to guess ("terra2025" pattern)
- If docker-compose.yml committed with actual credentials, entire infrastructure compromised

**Fix:**
- Create `.env` file (gitignored) with strong random passwords
- Update docker-compose to reference `.env` instead of hardcoding
- Add `.env` to `.gitignore` with `.env.example` template

---

### 🟡 HIGH: No HTTPS/TLS Configuration

**Finding:** 
- No SSL certificates configured in any service
- API Gateway (port 8000) accepts unencrypted HTTP
- Kafka uses PLAINTEXT listener (no encryption)

**Impact:**
- Credentials transmitted in cleartext
- Man-in-the-middle attacks possible
- Not compliant with agricultural data privacy requirements

**Fix:**
- Enable HTTPS in Spring Boot services
- Configure Kafka with SSL/TLS
- Add certificate management (Let's Encrypt for dev, enterprise PKI for prod)

---

### 🟡 MEDIUM: No Input Validation on Sensor Data

**File:** `services/terra-sense/src/main/java/com/terraneuron/sense/model/SensorData.java`

```java
private String sensorId;
private String sensorType;
private Double value;         // ← No range validation
private String unit;
private String farmId;
```

**Impact:**
- Negative temperatures accepted
- Negative humidity accepted
- No max/min bounds checked
- Could cause downstream AI analysis anomalies

**Fix:**
- Add `@Min`, `@Max`, `@Pattern` annotations
- Example:
```java
@Min(-40) @Max(60) private Double value;  // temperature in °C
@Min(0) @Max(100) private Double humidity;
```

---

## 3. Kafka / Event Contract Findings

### 🔴 CRITICAL: Event Naming Mismatch

**Issue:** ActionPlanService publishes different event type than CloudEvents spec defines

**File:** `services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java` (line 276)

```java
"type", "terra.ops.command.execute"  // Published by terra-ops
```

**But CloudEvents models define:**
`terra.ops.command.executed` (in `cloudevents_models.py`)

**Impact:**
- Event consumers looking for `terra.ops.command.executed` won't find `terra.ops.command.execute`
- terra-sense DeviceCommandConsumer expects different schema

---

### 🟡 HIGH: SensorData Schema Mismatch

**terra-sense produces (SensorData.java):**
```java
private String sensorId;
private String sensorType;
private Double value;
private String farmId;  // Terra-cortex expects this
private String unit;
```

**terra-cortex expects (models.py):**
```python
class SensorData(BaseModel):
    farmId: str
    sensorType: str
    value: float
    timestamp: Optional[datetime] = None
```

**Issue:** `sensorId` is sent but not used by terra-cortex. InfluxDB insertion would require it, but InfluxDB writer not implemented.

**Impact:**
- Wasted bandwidth transmitting sensorId
- Inconsistent metadata across pipeline
- If InfluxDB integration completed later, may conflict

**Fix:** Align schemas:
```python
class SensorData(BaseModel):
    sensor_id: str          # Add missing field
    farm_id: str
    sensor_type: str
    value: float
    unit: str               # Add unit for consistency
    timestamp: datetime
```

---

### 🟡 HIGH: Parameters Field Serialization

**File:** `services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java` (line 70-75)

```java
String parametersJson = null;
Object params = data.get("parameters");
if (params != null) {
    parametersJson = objectMapper.writeValueAsString(params);
}
// ... later stored as String in ActionPlan entity
```

**And in executePlan (line 274-280):**

```java
"parameters", plan.getParameters() != null ? plan.getParameters() : "{}",
```

**Issue:**
- Storing JSON as string; should be typed
- Parameters object loses structure
- DeviceCommandConsumer must parse string back to Map (fragile)

**Fix:**
- Use `@Convert` JPA annotation or embedded JSON type
- Preserve type safety with `@Type` or `@Lob` + `@Convert`

---

### 🟡 HIGH: Timestamp Format Inconsistency

**terra-cortex sends (cloudevents_models.py):**
```python
"detected_at": str  # RFC3339 ISO format from datetime.now(timezone.utc).isoformat()
```

**terra-ops receives (ActionPlanService.java):**
```java
Instant generatedAt = parseInstant(data.get("generated_at"));
```

**Issue:**
- Field named `generated_at` in code but `detected_at` in events
- Instant parsing assumes RFC3339; may fail on non-UTC offsets

**Fix:**
- Standardize field name to `generated_at` across all events
- Validate timestamp format: `@NotNull @Pattern(regexp="^\\d{4}-\\d{2}-\\d{2}T.*Z$")`

---

### 🔴 CRITICAL: `terra.control.command` No Consumer

**Issue:** Topic is created, produced to, but **never consumed in running system**

**File:** `services/terra-sense/src/main/java/com/terraneuron/sense/service/DeviceCommandConsumer.java`

**Evidence:**
- File exists and is complete
- BUT it's **NOT wired into the service**
- No `@EnableKafkaListeners` annotation
- No Kafka listener container factory configured for this consumer
- docker-compose doesn't show terra-sense consuming from Kafka

**Impact:**
- Action plans approved in terra-ops → published to `terra.control.command`
- **Nobody listening** → commands never reach MQTT gateway
- Entire execution feedback loop broken
- Devices never receive commands

**Fix:**
1. Ensure DeviceCommandConsumer is a `@Service` (it is)
2. Verify listener container factory is registered in `KafkaConfig`
3. Test with `kafka-console-consumer --topic terra.control.command`
4. Add integration test: approve plan → verify message on topic

---

### Proposed Canonical Event Schema

**Unified across all services:**

```json
{
  "specversion": "1.0",
  "type": "terra.<service>.<category>.<action>",
  "source": "//terraneuron/<service>",
  "id": "<UUID>",
  "time": "<RFC3339 ISO format, UTC>",
  "datacontenttype": "application/json",
  "tracecontext": {
    "trace_id": "<UUID>",
    "span_id": "<base64>"
  },
  "data": {
    "trace_id": "<UUID>",
    "farm_id": "string",
    "sensor_id": "string (if applicable)",
    "timestamp": "<RFC3339>",
    "... service-specific fields"
  }
}
```

---

## 4. Runtime / Build Findings

### 🔴 CRITICAL: Incomplete MQTT Integration

**Claimed:** "MQTT 양방향 제어 루프" (bidirectional MQTT control loop) - Phase 4 in ROADMAP.md

**Actual:**
- Mosquitto broker in docker-compose ✅
- MQTT dependencies in terra-sense build.gradle ✅
- Files exist:
  - `MqttConfig.java` - MQTT client bean configuration
  - `MqttGatewayService.java` - MQTT bridge (claimed to be 양방향 bidirectional)
  - `DeviceCommandConsumer.java` - Kafka → MQTT bridge
- **BUT:** No actual MQTT listener in terra-sense consuming sensor data from IoT devices

**Impact:**
- IoT sensors cannot publish to MQTT broker
- MQTT→Kafka ingestion non-functional
- Only HTTP ingestion works (via IngestionController)
- Roadmap claims this is COMPLETED; it is NOT

**Fix:**
1. Implement `MqttSensorListener` to subscribe to `terra/devices/{farmId}/{sensorId}/data`
2. Parse MQTT payload into SensorData
3. Forward to terra-sense HTTP ingest or directly to Kafka producer
4. Add unit tests for MQTT message parsing

---

### 🔴 CRITICAL: InfluxDB Not Integrated

**Claimed:** Phase 1 Complete - "Data Persistence: MySQL + InfluxDB verified (100% success rate)"

**Actual:**
- InfluxDB container runs in docker-compose ✅
- InfluxDB Java client dependency in terra-sense build.gradle ✅
- Environment variables configured ✅
- **BUT:** No code writes to InfluxDB

**Evidence:**
- `services/terra-sense/src/main/java/com/terraneuron/sense/service/InfluxDBWriterService.java` does NOT exist
- No @Service writing sensor_data measurements
- Kafka messages not persisted to time-series store
- All data goes to MySQL only

**Impact:**
- Time-series queries fail
- InfluxDB dashboards in Grafana show no data
- Cannot perform sliding-window analysis (trend detection) in terra-cortex
- terra-cortex mentions "Trend Analyzer" consuming InfluxDB but data never written

**Fix:**
1. Create `InfluxDBWriterService` 
2. Write every insight to InfluxDB as measurement:
   ```
   measurement: "insights"
   tags: {farm_id, sensor_type, status}
   fields: {value, confidence, severity}
   timestamp: insight.detectedAt
   ```
3. Add InfluxDB integration test

---

### 🟡 HIGH: Port Mapping Conflict

**File:** `docker-compose.yml`

```yaml
terra-ops:
  ports:
    - "8080:8080"
  # Dockerfile also runs on port 8080 (application.properties: server.port=8080)
```

**Issue:**
- If multiple terra-ops containers start, second one fails (port already bound)
- docker-compose doesn't prevent this

**Impact:**
- Horizontal scaling blocked
- Health check failures in orchestration

**Fix:**
- Document single-instance requirement OR
- Use dynamic port mapping: `- "8080"` (docker assigns random host port)
- Better: move terra-ops to 8084 to avoid conflicts with gateway (8000), sense (8081), cortex (8082)

---

### 🟡 HIGH: Missing Redis Authentication in terra-gateway

**File:** `docker-compose.yml`

```yaml
redis:
  command: redis-server --requirepass terra2025
```

**But terra-gateway config doesn't specify password:**

**File:** `services/terra-gateway/src/main/resources/application.properties`

```properties
spring.data.redis.host=${REDIS_HOST:localhost}
spring.data.redis.port=${REDIS_PORT:6379}
# No password configuration!
```

**Impact:**
- Rate limiting fails to initialize if Redis requires password
- terra-gateway startup fails silently or rate limiting disabled

**Fix:**
```properties
spring.data.redis.host=${REDIS_HOST:localhost}
spring.data.redis.port=${REDIS_PORT:6379}
spring.data.redis.password=${REDIS_PASSWORD:terra2025}
```

---

### 🟡 HIGH: Kafka Bootstrap Configuration Issue

**File:** `docker-compose.yml` (terra-cortex)

```yaml
KAFKA_BOOTSTRAP_SERVERS: kafka:9092
```

**But Kafka configuration:**

```yaml
kafka:
  environment:
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092  # Internal network
    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092           # Listen on all interfaces
```

**Issue:**
- Works within Docker network (kafka:9092 resolves)
- Fails if external client tries to connect (e.g., local Kafka CLI tools)
- External advertised listener needed for out-of-container access

**Fix:**
```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
```

---

### 🟡 MEDIUM: Dependency Startup Order Risk

**docker-compose.yml** has `depends_on` but **no health checks**

```yaml
terra-sense:
  depends_on:
    - kafka      # ← No check if Kafka is READY, just started
    - influxdb
```

**Issue:**
- terra-sense starts before Kafka broker is fully initialized
- Kafka consumer may fail with "cannot find broker"
- Docker Compose only waits for container to exist, not be healthy

**Impact:**
- Intermittent "broker unavailable" errors in logs
- Requires manual service restart

**Fix:** Add health checks:
```yaml
kafka:
  healthcheck:
    test: ["CMD", "kafka-broker-api-versions.sh", "--bootstrap-server", "localhost:9092"]
    interval: 5s
    timeout: 5s
    retries: 5

terra-sense:
  depends_on:
    kafka:
      condition: service_healthy
```

---

## 5. Test Findings

### 🔴 CRITICAL: Zero Unit Test Coverage

**Finding:** 
- No `src/test/` directories in any Java service
- No JUnit tests
- No Mockito mocks
- No Spring @WebMvcTest or @DataJpaTest

**Evidence:**
```
services/terra-sense/src/
  └─ main/
      ├─ java/
      ├─ resources/
  (NO test/ directory)
```

**Impact:**
- No verification of:
  - Sensor data validation rules
  - Kafka producer error handling
  - JWT token generation/validation
  - Safety validation logic
  - ActionPlan state transitions
- Regressions undetected
- Refactoring risk high

**Metrics:**
- **Test Coverage: 0%**
- **Critical logic paths untested:** Safety validator, approval workflow, event creation

---

### 🟡 HIGH: E2E Tests Are Manual/Ad-Hoc

**Files:**
- `tests/neural-flow-test.py` - Manual test script
- `tests/simulation.py` - Data generator (not test)

**Evidence (neural-flow-test.py):**
```python
def send_sensor_data(data: Dict) -> bool:
    """terra-sense API로 센서 데이터 전송"""
    try:
        response = requests.post(TERRA_SENSE_URL, json=data, timeout=5)
        # ... manual assertion checks
```

**Issue:**
- Not automated (requires manual execution)
- No CI/CD integration
- No pytest/unittest framework
- Results printed to console (not parseable)

**Impact:**
- Cannot run in CI pipeline
- No regression detection on commit
- "E2E Validated 100% Success" claim unverifiable

---

### 🟡 HIGH: Missing Test Scenarios

**Critical flows NOT tested:**

1. **Sensor ingestion pipeline:**
   - Invalid sensor data (negative values, missing fields)
   - Duplicate events
   - Out-of-order timestamps

2. **Kafka contracts:**
   - CloudEvents format validation
   - trace_id propagation
   - Event schema compliance
   - Consumer lag monitoring

3. **Safety validation:**
   - All 4 layers (logical, context, permission, device)
   - Plan expiration logic
   - Rejection workflow

4. **Authorization:**
   - RBAC enforcement (currently disabled, so even when enabled, untested)
   - Role-based endpoint access
   - Cross-tenant isolation (n/a currently, but should be tested)

5. **Error handling:**
   - Kafka producer failure → fallback behavior
   - Database connection loss → graceful degradation
   - LLM API timeout → SAFE_MODE activation

---

### Test Coverage Assessment

| Component | Unit Tests | Integration Tests | E2E Tests | Status |
|-----------|-----------|-----------------|-----------|--------|
| terra-sense | ❌ None | ❌ None | ✅ Manual script | **No coverage** |
| terra-cortex | ❌ None | ❌ None | ✅ Manual script | **No coverage** |
| terra-ops | ❌ None | ❌ None | ✅ Manual script | **No coverage** |
| terra-gateway | ❌ None | ❌ None | ❌ None | **No coverage** |
| Kafka contracts | ❌ None | ❌ None | ⚠️ Implicit | **No coverage** |
| Safety validation | ❌ None | ❌ None | ❌ None | **No coverage** |

---

## 6. Infrastructure / DevOps Audit

### 🟡 MEDIUM: No CI/CD Pipeline

**Finding:** 
- `.github/workflows/` directory exists but is empty/non-functional
- No automated tests on commit
- No build validation
- No deployment pipeline

**Impact:**
- Manual testing required for every change
- Breaking changes not caught before merge
- Deployment requires manual steps

---

### 🟡 MEDIUM: No Deployment Configuration

**Finding:**
- `docker-compose.yml` for local only
- No Kubernetes manifests
- No AWS/Azure CloudFormation
- No Terraform IaC

**ROADMAP claims:** "Phase 4.A: Deployment" but lists only as planned

**Impact:**
- Cannot deploy to production
- Documentation claims "production-ready" but no deployment pipeline

---

### 🟡 MEDIUM: Secret Management Inadequate

| Secret | Storage | Exposure Risk |
|--------|---------|---|
| JWT Secret | application.properties (fallback) | Visible in repo ❌ |
| MySQL Password | application.properties | Visible in repo ❌ |
| Database credentials | docker-compose.yml | Visible in repo ❌ |
| OpenAI API Key | docker-compose (env var) | If .env committed ❌ |
| Redis password | docker-compose | Visible in repo ❌ |

---

## 7. Data Model & Schema Findings

### 🟡 MEDIUM: MySQL Schema Not Versioned

**File:** `infra/mysql/init.sql`

**Issue:**
- One-time initialization script
- No versioning/migration strategy
- Schema changes require manual scripts
- Difficult to reproduce in new environment

**Fix:**
- Implement Flyway or Liquibase for schema versioning
- Each schema change gets a numbered migration file
- Automatic application at startup

---

### 🟡 MEDIUM: ActionPlan Entity Parameters Field

**File:** `services/terra-ops/src/main/java/.../entity/ActionPlan.java`

```java
@Column(columnDefinition = "LONGTEXT")
private String parameters;  // Storing JSON as string
```

**Issue:**
- Should use JSON type for queryability
- Current approach: must parse string in code every access
- Cannot query "plans with temperature > 30" in parameters

**Fix:**
- Use MySQL 5.7+ JSON type:
```java
@Column(columnDefinition = "JSON")
@Convert(converter = JsonConverter.class)
private Map<String, Object> parameters;
```

---

## Recommended Upgrade Plan

### Sprint 0: Documentation & Truth Alignment (P0 - BLOCKING)

**Duration:** 3 days  
**Blockers:** Must complete before claiming any production readiness

1. **Update PROJECT_STATUS.md**
   - Mark JWT/RBAC as "Implemented but disabled"
   - Mark MQTT as "Scaffolded, not operational"
   - Mark InfluxDB as "Configured, not integrated"
   - Mark test coverage as "0%"

2. **Create IMPLEMENTATION_GAPS.md**
   - List all unimplemented features
   - Prioritize by impact

3. **Audit checklist**
   - README claims vs code reality
   - Feature flags for incomplete features

---

### Sprint 1: Security Hardening (P0 - BLOCKING for production)

**Duration:** 5 days

**Tasks:**

1. **Enable RBAC** (1 day)
   - Uncomment role-based matchers in SecurityConfig
   - Enable `/api/actions/**` for ROLE_ADMIN, ROLE_OPERATOR
   - Enable `/api/insights/**` for all authenticated roles
   - Test with unauthorized requests (should get 403)

2. **Database-backed authentication** (1.5 days)
   - Create UserService consuming `users` table
   - Replace hardcoded users in AuthController
   - Implement password verification against BCrypt hash
   - Add user creation/management endpoints

3. **Secrets management** (1.5 days)
   - Remove hardcoded JWT secret
   - Require `JWT_SECRET` environment variable (no fallback)
   - Move database passwords to `.env` (gitignore)
   - Update docker-compose to load from `.env`
   - Add `.env.example` template

4. **CORS hardening** (0.5 day)
   - Replace `*` with whitelisted origins
   - Use environment variable: `ALLOWED_ORIGINS=https://farm.terraneuron.io`

5. **Input validation** (1 day)
   - Add `@Min/@Max` constraints to SensorData.value
   - Add validation tests

---

### Sprint 2: Event Contract Stabilization (P1)

**Duration:** 4 days

1. **Fix event naming** (0.5 day)
   - Align ActionPlanService to publish `terra.ops.plan.executed` (not `terra.ops.command.execute`)
   - Update DeviceCommandConsumer listener

2. **Align SensorData schema** (1 day)
   - terra-sense produces: `{sensor_id, farm_id, sensor_type, value, unit, timestamp}`
   - terra-cortex consumes same fields
   - Add schema validation

3. **Fix timestamp consistency** (0.5 day)
   - All timestamps in RFC3339 UTC format
   - Validation: `@Pattern(regexp="...Z$")`

4. **Verify terra.control.command consumer** (1.5 days)
   - Confirm DeviceCommandConsumer is wired
   - Add integration test: produce → consume
   - Validate message deserialization

---

### Sprint 3: Demo Loop Completion (P1)

**Duration:** 6 days

1. **Implement terra.control.command consumer in terra-sense** (2 days)
   - Ensure DeviceCommandConsumer is running
   - Add logging for every message received/sent
   - Implement MqttGatewayService.publishCommand() to actually publish to MQTT

2. **Test MQTT feedback loop** (1.5 days)
   - Send command via REST API
   - Verify it arrives on MQTT topic
   - Simulate device response

3. **Integrate InfluxDB writer** (1.5 days)
   - Create InfluxDBWriterService
   - Write insights to time-series store
   - Verify Grafana dashboards show data

4. **Add Redis password to terra-gateway** (0.5 day)

---

### Sprint 4: Test Coverage Foundation (P0 - MUST HAVE for "production-ready")

**Duration:** 8 days

1. **Unit tests for critical components** (4 days)
   - SafetyValidator: all 4 validation layers
   - JwtTokenProvider: token creation, validation, expiration
   - SensorData model: constraint validation
   - ActionPlan state machine: transitions, expiration
   - Use JUnit 5 + Mockito

2. **Integration tests** (2 days)
   - Kafka consumer/producer round-trip
   - MySQL persistence
   - SecurityConfig authorization checks

3. **E2E automated test suite** (2 days)
   - Adapt `tests/neural-flow-test.py` to pytest framework
   - Add assertions for:
     - HTTP → Kafka → MySQL flow
     - AI anomaly detection trigger
     - Action plan approval workflow
   - CI/CD ready (exit code on failure)

---

### Sprint 5: Operational Readiness (P1)

**Duration:** 5 days

1. **Kubernetes manifests** (2 days)
   - Deployment YAML for all 4 services
   - ConfigMap for non-secret config
   - Secret for JWT_SECRET, DB passwords
   - Service discovery

2. **Monitoring & observability** (1.5 days)
   - Prometheus metrics on all services
   - Grafana dashboards: pipeline latency, error rates, queue depth
   - Log aggregation setup (ELK or CloudWatch)

3. **Runbook documentation** (1.5 days)
   - Deployment procedures
   - Scaling guidelines
   - Troubleshooting common issues

---

### Priority Backlog

| Priority | Item | Effort | Blocker |
|----------|------|--------|---------|
| **P0** | Enable RBAC security | 1d | Production deployment |
| **P0** | Database-backed auth (remove hardcoded users) | 1.5d | Security audit |
| **P0** | Secrets management (remove hardcoded JWT key) | 1.5d | Security audit |
| **P0** | Unit test coverage (SafetyValidator, auth) | 4d | Production deployment |
| **P1** | Fix event naming contract | 0.5d | Integration testing |
| **P1** | Verify terra.control.command consumer | 1.5d | Demo loop |
| **P1** | Integrate InfluxDB writer | 1.5d | Data persistence |
| **P1** | MQTT integration complete | 2d | Full pipeline |
| **P1** | Kubernetes manifests | 2d | Cloud deployment |
| **P2** | Input validation on sensor data | 1d | Data quality |
| **P2** | Redis password in terra-gateway | 0.5d | Config |
| **P2** | Schema versioning (Flyway/Liquibase) | 1d | DB management |
| **P2** | CI/CD pipeline | 2d | Automation |
| **P3** | SSL/TLS certificates | 1d | Production ops |
| **P3** | Multi-tenant support | 5d | Enterprise features |

---

## Key Recommendations

### Immediate (Before Demo)
1. ✅ Fix permitAll() - Enable RBAC
2. ✅ Remove hardcoded users
3. ✅ Externalize JWT secret
4. ✅ Verify terra.control.command consumer is wired

### Before Production
5. ✅ Add unit tests (min: SafetyValidator, Auth, Action state machine)
6. ✅ Create automated E2E test suite
7. ✅ Integrate InfluxDB writer
8. ✅ Fix MQTT listener (or remove from architecture)

### Before Enterprise
9. ✅ Kubernetes deployment manifests
10. ✅ Monitoring/observability stack
11. ✅ Secrets management (Vault)
12. ✅ SSL/TLS everywhere

---

## Conclusion

**TerraNeuron's current state: Functional Prototype**

The platform has solid architectural foundations (microservices, Kafka, CloudEvents, AI integration). However, significant work is required to reach production-grade:

- ⛔ **Security disabled** (RBAC, hardcoded secrets)
- ⛔ **Test coverage at 0%** (no unit/integration tests)
- ⛔ **Device control loop incomplete** (MQTT scaffolded, command consumer not wired)
- ⛔ **Data persistence incomplete** (InfluxDB not integrated)

**Claim vs Reality Gap:**
- Documentation claims "Production-Ready" with Phase 3 complete
- Actual state: Core demo works, but many features are scaffolded/disabled for convenience
- Suitable for **portfolio demonstration**, not **deployment**

**Path Forward:**
- Sprint 1 (Security): 5 days to fix critical vulnerabilities
- Sprint 4 (Tests): 8 days to establish minimum coverage
- Sprint 5 (Ops): 5 days for production deployment readiness

**Estimated effort to portfolio-grade hardened demo: 2-3 weeks**
**Estimated effort to production-grade architecture prototype: 4-6 weeks**
**Estimated effort to real production-ready deployment: 2-3+ months** (assuming team of 2 engineers)

