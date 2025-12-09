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

## 🚧 Phase 2: The Cortex (Cognition & Action) - CURRENT PRIORITY

### 📍 Phase 2.A: Action Loop Foundation (Priority: High)
> *Goal: Establish a SAFE, STANDARD, and AUDITABLE protocol for AI actions.*

- [ ] **Protocol Design:** Create `docs/ACTION_PROTOCOL.md`.
    - MUST implement **CloudEvents v1.0** JSON Schema.
    - MUST follow naming convention: `terra.<service>.<category>.<action>`.
    - MUST include `trace_id` in headers for distributed tracing.
- [ ] **Ops Backend (Safety & Audit Layer):**
    - Create `ActionPlan` Entity (mapped to FarmOS `Plan` structure).
    - Implement **4 Safety Validators** (Logical, Context, Permission, DeviceState).
    - **Audit Logging (CRITICAL):**
        - Record all lifecycle events (Create/Validate/Approve/Execute/Reject).
        - MUST map to FarmOS `Log (type: activity)` entity to meet industrial regulations.
    - API Implementation: `GET /actions/pending` & `POST /actions/{id}/approve`.
- [ ] **Kafka Loop:**
    - `terra-cortex`: Produce dummy action suggestions with proper headers.
    - `terra-ops`: Consume -> Validate -> Pending State -> Publish `terra.control.command`.

### 📍 Phase 2.B: Hybrid Orchestrator
> *Goal: Smart Context & RAG with a Unified Brain.*

- [ ] **Unified Context Model:**
    - Define shared data structures based on FarmOS (`Asset`, `Log`, `Plan`).
    - Ensure RAG and Orchestrator use the same context model (e.g., "Fan_1 is linked to Zone A").
- [ ] **Module Split:** Refactor `terra-cortex` into `local_reflector` (Rules) vs `cloud_advisor` (RAG).
- [ ] **RAG Setup:** ChromaDB integration with basic agronomy PDF manuals.
- [ ] **Failure Handling:** Implement `SAFE_MODE` (Alert Only) when AI logic fails.

### 📍 Phase 2.C: Edge Reflex Design
> *Goal: Local fail-safe mechanism.*
- [ ] **Design:** Create `docs/EDGE_REFLEX.md` for local fallback logic (Internet outage safety).

---

## 🔮 Phase 3: Production Readiness (Future)
- [ ] **Security:** Implement JWT Authentication & SSL/TLS.
- [ ] **Standardization:** Refine APIs to match strictly with FarmOS specifications.
- [ ] **Deployment:** Docker Swarm or K3s setup (Avoid heavy K8s like Kubeflow).
