# 🗺️ TerraNeuron Strategic Roadmap

## 🎯 Strategic Direction: "From Reflex to Brain"
- **Current Objective:** Build the **"Action Loop"** with strict Safety Guards, Standardization, and Accountability.
- **Core Philosophy:** "Safety First", "FarmOS Compatibility", and "Traceability".

---

## ✅ Phase 1: The Spine (Infrastructure & Reflex) - COMPLETED
- [x] **Microservices Core:** `terra-gateway`, `terra-sense`, `terra-cortex`, `terra-ops` setup.
- [x] **Event Backbone:** Kafka configuration verified (`raw-sensor-data`, `processed-insights`).
- [x] **Data Persistence:** MySQL + InfluxDB verified (100% success rate).
- [x] **Observability:** Prometheus + Grafana + HTML Test Reporter.
- [x] **MVP AI:** Rule-based anomaly detection (Threshold logic).

---

## ✅ Phase 2: The Cortex (Cognition & Action) - COMPLETED

### ✅ Phase 2.A: Action Loop Foundation - COMPLETED (January 2026)
> *Goal: Establish a SAFE, STANDARD, and AUDITABLE protocol for AI actions.*

- [x] **Protocol Design:** `docs/ACTION_PROTOCOL.md` - CloudEvents v1.0 compliant
    - ✅ CloudEvents v1.0 JSON Schema implemented
    - ✅ Naming convention: `terra.<service>.<category>.<action>`
    - ✅ `trace_id` header propagation for distributed tracing
- [x] **CloudEvents Models (Python):** `terra-cortex/src/cloudevents_models.py`
    - ✅ InsightDetectedEvent, ActionPlanGeneratedEvent
    - ✅ PlanApprovalEvent, CommandExecutedEvent, AlertTriggeredEvent
    - ✅ Factory functions for event creation
- [x] **Ops Backend (Safety & Audit Layer):**
    - ✅ `ActionPlan` Entity (FarmOS `Plan` compatible)
    - ✅ **4-Layer Safety Validators** (Logical, Context, Permission, DeviceState)
    - ✅ **Audit Logging** - Full lifecycle tracking (Create/Validate/Approve/Execute/Reject)
    - ✅ FarmOS `Log (type: activity)` compatible `AuditLog` entity
- [x] **REST API Implementation:**
    - ✅ `GET /api/actions/pending` - List pending plans
    - ✅ `GET /api/actions/{id}` - Get plan details
    - ✅ `POST /api/actions/{id}/approve` - Approve with safety validation
    - ✅ `POST /api/actions/{id}/reject` - Reject with reason
    - ✅ `GET /api/actions/{id}/audit` - Get audit trail
    - ✅ `GET /api/actions/statistics` - Dashboard statistics
- [x] **Kafka Loop:**
    - ✅ `terra-cortex`: Produces CloudEvents-compliant action plans with `trace_id`
    - ✅ `terra-ops`: Consumes → Validates (4-layer) → Pending State → Publish `terra.control.command`
    - ✅ Automatic plan expiration scheduler

### ✅ Phase 2.B: Hybrid Orchestrator - COMPLETED (December 2025)
> *Goal: Smart Context & RAG with a Unified Brain.*

- [x] **Hybrid AI Pipeline:** Local Edge + Cloud LLM + RAG
- [x] **RAG Setup:** ChromaDB integration with agricultural knowledge base
- [x] **Failure Handling:** `SAFE_MODE` (Alert Only) when AI logic fails

### 📍 Phase 2.C: Edge Reflex Design - IN PROGRESS
> *Goal: Local fail-safe mechanism.*
- [ ] **Design:** Create `docs/EDGE_REFLEX.md` for local fallback logic (Internet outage safety)
- [ ] **Implementation:** Local relay controller with cached rules

---

## ✅ Phase 3: Production Readiness - COMPLETED (January 2026)

### ✅ Security Implementation
- [x] **JWT Authentication:**
    - ✅ `JwtTokenProvider` - Token generation and validation
    - ✅ `JwtAuthenticationFilter` - Request authentication
    - ✅ `SecurityConfig` - Spring Security configuration
    - ✅ Role-based access: ADMIN, OPERATOR, VIEWER
- [x] **Auth API:**
    - ✅ `POST /api/auth/login` - Login with JWT tokens
    - ✅ `POST /api/auth/refresh` - Token refresh
    - ✅ `GET /api/auth/validate` - Token validation
- [x] **Database Schema:** Users table with BCrypt password hashing

### 📍 Remaining Tasks
- [ ] **SSL/TLS:** HTTPS configuration for all services
- [ ] **Secrets Management:** HashiCorp Vault or AWS Secrets Manager
- [ ] **Deployment:**
    - [ ] Docker Swarm configuration
    - [ ] K3s setup (lightweight Kubernetes)
    - [ ] CI/CD pipeline updates

---

## 🔮 Phase 4: Advanced Features (Future)

### 📍 Phase 4.A: FarmOS Full Integration
- [ ] Complete FarmOS API compatibility
- [ ] Asset/Log/Plan unified model
- [ ] Industry compliance reporting

### 📍 Phase 4.B: Multi-Tenant Architecture
- [ ] Organization/Farm hierarchy
- [ ] Tenant isolation
- [ ] Usage metering and billing

### 📍 Phase 4.C: Advanced AI
- [ ] Predictive maintenance
- [ ] Yield optimization models
- [ ] Weather integration

---

## 📊 Implementation Summary (January 2026)

| Component | Status | Files Created/Modified |
|-----------|--------|----------------------|
| CloudEvents Models | ✅ | `cloudevents_models.py` |
| trace_id Propagation | ✅ | `main.py` (terra-cortex) |
| ActionPlan Entity | ✅ | `ActionPlan.java` |
| 4-Layer Safety | ✅ | `SafetyValidator.java` |
| Audit Logging | ✅ | `AuditLog.java`, `AuditService.java` |
| Action API | ✅ | `ActionController.java`, `ActionPlanService.java` |
| JWT Security | ✅ | `JwtTokenProvider.java`, `SecurityConfig.java` |
| Auth API | ✅ | `AuthController.java` |
| DB Schema | ✅ | `init.sql` |

**Total New Files:** 12  
**Modified Files:** 5
