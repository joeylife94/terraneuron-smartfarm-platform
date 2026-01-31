# TerraNeuron / Asgard → Andercore Fit: Technical Architecture Narrative (Bilingual)

> **📅 Last Updated: January 31, 2026**  
> **Version: 2.1.0** - Phase 2.A (Action Loop) & Phase 3 (Security) Implementation Complete

---

## 📜 Document History

| Version | Date | Changes |
|---------|------|----------|
| v2.1.0 | 2026-01-31 | Phase 2.A & 3 구현 완료: CloudEvents, 4-Layer Safety, JWT Auth, Audit Logging |
| v2.0.0 | 2025-12-09 | Initial architecture narrative with Hybrid AI design |

---

> 작성 기준 / Writing stance
>
>- 이 문서는 **기술 설계 서술(architecture narrative)** 입니다. 과장/마케팅 문구 없이, **시니어 백엔드 엔지니어/채용 매니저**에게 설명하는 톤을 유지합니다.
>- TerraNeuron 내용은 이 저장소의 구현/문서(예: Kafka 토픽 `raw-sensor-data`, `processed-insights`, `action-plans`, `CloudEvents v1.0 Action Protocol`, `trace_id`, 4-Layer Safety Validation, JWT Authentication, API Gateway rate limiting, polyglot persistence 등)에 기반합니다.
>- Asgard는 질문에 제공된 설명을 기반으로, TerraNeuron과의 **역할/책임 경계** 중심으로 비교합니다.
>
> This document is an **architecture narrative** (no marketing tone). It is written for a senior backend engineer / hiring manager.
>
---

## 1. TerraNeuron이란 무엇인가 (Project Definition)

TerraNeuron은 **이벤트 기반(event-driven) 스마트팜 운영 플랫폼**입니다. 핵심은 “센서 데이터 수집 → 이벤트 스트리밍 → 분석/의사결정 지원 → (승인 기반) 실행/운영 → 결과 피드백”의 폐루프를 **마이크로서비스 + 메시지 브로커(Kafka)**로 분리해 운영 가능한 형태로 만든 것입니다.

이 프로젝트를 시스템 관점에서 정의하면 다음과 같습니다.

- **입력(Input)**: IoT 센서 데이터(HTTP/MQTT)
- **이벤트 버스(Event Backbone)**: Kafka 토픽
  - `raw-sensor-data`: 수집된 원천 이벤트
  - `processed-insights`: 분석/판단 결과(인사이트)
- **처리(Processing)**: `terra-cortex`가 로컬 규칙/임계치 기반 분석을 항상 수행하고, 필요 시(ANOMALY) LLM/RAG를 통해 “설명 가능한 권장안”을 추가
- **저장(Storage)**:
  - InfluxDB: 시계열(raw) 센서 데이터
  - MySQL: 운영/대시보드용 인사이트/상태 데이터(조회/필터링/집계)
- **외부 진입점(Edge/API boundary)**: `terra-gateway`(Spring Cloud Gateway + Redis 기반 rate limiting)
- **운영 관찰(Observability)**: Prometheus/Grafana

즉 TerraNeuron은 “AI 데모”가 아니라, **비동기 이벤트 파이프라인을 통해 운영 상태를 축적하고, 사람이 승인 가능한 형태로 의사결정 정보를 공급하는 운영체계(operational system)**입니다.

### 1. What TerraNeuron Is (Project Definition)

TerraNeuron is an **event-driven operational platform** for smart farming. The core is an operational closed loop—“ingest sensor signals → stream events → analyze/decision support → (approval-based) operations/execution → feedback”—implemented as **microservices connected by Kafka**.

System-definition view:

- **Input**: IoT sensor data (HTTP/MQTT)
- **Event backbone**: Kafka topics
  - `raw-sensor-data`: ingested source-of-truth events
  - `processed-insights`: analysis/decision outputs (insights)
- **Processing**: `terra-cortex` always performs local rule/threshold analysis; for anomalies only, it optionally enriches outputs with LLM/RAG as explainable recommendations
- **Storage**:
  - InfluxDB: raw time-series sensor data
  - MySQL: operational/dashboard insights and status (query/filter/aggregate)
- **API boundary**: `terra-gateway` (Spring Cloud Gateway + Redis-backed rate limiting)
- **Observability**: Prometheus/Grafana

In other words, TerraNeuron is not a “toy AI demo”; it is an **operational event pipeline** that accumulates state and produces decision support in an auditable, approval-friendly form.

---

## 2. TerraNeuron End-to-End Workflow

TerraNeuron의 E2E 흐름은 “데이터 이동”과 “의사결정 경계”를 분리해 설계되어 있습니다. 아래는 구현/문서 상의 실제 구성요소를 반영한 단계별 흐름입니다.

### 2.1 단계별 흐름 (실제 서비스/토픽 기준)

```
(1) Sensor/Device
    |  MQTT/HTTP
    v
(2) terra-sense  (Java/Spring)
    - 수집(ingestion) + 최소한의 검증/타임스탬프 보강
    - raw를 Kafka로 publish
    |  produce
    v
(3) Kafka topic: raw-sensor-data
    |  consume (terra-cortex-group)
    v
(4) terra-cortex (Python/FastAPI + aiokafka)
    Stage 1: Local analyzer (항상 실행)
      - 규칙/임계치/단순 이상탐지
      - 출력: NORMAL/ANOMALY + severity + message + confidence
    Stage 2: Cloud/Local LLM advisor (ANOMALY에서만 실행)
      - 실행계획이 아니라 “권장/설명”을 생성
    Stage 3: RAG advisor (도메인 KB 기반 컨텍스트 부여)
      - 매뉴얼/케이스 기반 근거 제공
    |  produce
    v
(5) Kafka topic: processed-insights
    |  consume (terra-ops-group)
    v
(6) terra-ops (Java/Spring + JPA)
    - 인사이트를 MySQL에 영속화
    - 대시보드/조회 API 제공

(7) API Access
    - terra-gateway가 /api/sense, /api/cortex, /api/ops 라우팅
    - Redis rate limiting으로 ingress 통제
```

### 2.2 “AI가 쓰이는 지점”과 “AI가 쓰이지 않는 지점”

- AI 사용(Use):
  - `terra-cortex` 내부
    - Stage 1(로컬): 규칙/임계치 기반 분석(엄밀히 말해 ML이 아니라 **deterministic analyzer**)이지만, 시스템 관점에선 “AI 계층”으로 취급
    - Stage 2(LLM): **ANOMALY에서만** 설명/권장 생성
    - Stage 3(RAG): KB 검색을 통한 근거/컨텍스트 제공
- AI 미사용(Do NOT use):
  - 이벤트 수집(ingestion), 메시지 라우팅/버퍼링(Kafka), 저장(MySQL/InfluxDB), API Gateway 제어, 대시보드 조회 응답은 **AI 없이 동작**
  - 즉, 플랫폼의 “정합성/내결함성/보안 경계”는 AI에 의존하지 않음

### 2.3 실행(Execution)과 승인(Approval)의 분리

`docs/ACTION_PROTOCOL.md` 기준으로, TerraNeuron의 액션은 CloudEvents v1.0 스키마를 따르고 `trace_id` 전파를 강제합니다. 또한 “4단계 안전 검증(논리/컨텍스트/권한/디바이스)”을 통과해야 하며, 실패 시 기본 동작은 `ALERT_ONLY`(fail-safe)입니다.

이는 “AI가 실행을 직접 결정/발동하지 않는다”는 운영 원칙을 프로토콜 레벨에서 고정하는 장치입니다.
> **✅ Phase 2.A 구현 완료 (January 2026)**
>
> 위 설계가 실제 코드로 구현되었습니다:
> - `terra-cortex/src/cloudevents_models.py`: CloudEvents v1.0 스키마 모델
> - `terra-ops/.../SafetyValidator.java`: 4단계 안전 검증 구현
> - `terra-ops/.../AuditService.java`: FarmOS 호환 감사 로깅
> - `terra-ops/.../ActionPlanService.java`: Action Plan 라이프사이클 관리
> - Kafka Topics: `action-plans`, `terra.control.command` 추가
### 2. TerraNeuron End-to-End Workflow

TerraNeuron’s E2E flow is designed by separating **data movement** from **decision boundaries**. Below is a step-by-step workflow reflecting the actual services/topics documented in the repository.

#### 2.1 Step-by-step (services/topics)

```
(1) Sensor/Device
    |  MQTT/HTTP
    v
(2) terra-sense (Java/Spring)
    - ingestion + minimal validation/timestamp enrichment
    - publishes raw events to Kafka
    |  produce
    v
(3) Kafka topic: raw-sensor-data
    |  consume (terra-cortex-group)
    v
(4) terra-cortex (Python/FastAPI + aiokafka)
    Stage 1: Local analyzer (always)
      - rules/thresholds/simple anomaly detection
      - output: NORMAL/ANOMALY + severity + message + confidence
    Stage 2: Cloud/Local LLM advisor (ANOMALY only)
      - generates explanation/recommendations, not executable actions
    Stage 3: RAG advisor (domain KB context)
      - retrieves manual/case-based grounding
    |  produce
    v
(5) Kafka topic: processed-insights
    |  consume (terra-ops-group)
    v
(6) terra-ops (Java/Spring + JPA)
    - persists insights into MySQL
    - exposes dashboard/query APIs

(7) API Access
    - terra-gateway routes /api/sense, /api/cortex, /api/ops
    - Redis rate limiting controls ingress
```

#### 2.2 Where AI is used vs not used

- AI used:
  - Inside `terra-cortex`
    - Stage 1 (local): deterministic rule/threshold analyzer (not ML, but the “AI layer” in system terms)
    - Stage 2 (LLM): **only on anomalies**, generates explanations/recommendations
    - Stage 3 (RAG): KB-backed grounding/context
- AI NOT used:
  - ingestion, routing/buffering (Kafka), persistence (MySQL/InfluxDB), gateway control, dashboard queries all run **without AI**
  - the platform’s correctness/fault tolerance/security boundaries do not depend on AI

#### 2.3 Separating execution from approval

Per `docs/ACTION_PROTOCOL.md`, actions conform to CloudEvents v1.0 and require `trace_id` propagation. All actions must pass **4-layer safety validation** (logical/context/permission/device). On failure, the default behavior is `ALERT_ONLY` (fail-safe).

This pins the operational rule “AI does not directly trigger execution” at the protocol level.

---

## 3. Hybrid AI Architecture (Critical Section)

TerraNeuron의 Hybrid AI는 “AI를 더 많이 쓰는 것”이 목표가 아니라, **비용/지연/신뢰성/실패 위험을 제어하면서도 운영자가 판단할 수 있는 정보 밀도를 높이는 것**이 목표입니다. 그래서 Stage 1/2/3를 분리합니다.

### 3.1 Stage 분리의 이유: 비용(Cost)

- 정상 데이터는 압도적으로 많고(센서 샘플링), 이상(anomaly)은 상대적으로 희소합니다.
- LLM을 모든 이벤트에 호출하면:
  - 비용이 선형으로 증가(이벤트량 × 토큰/요금)
  - 운영 비용 예측성이 떨어짐(스파이크 시 폭증)
- 따라서:
  - Stage 1(로컬)이 **항상** “필터/게이트” 역할을 수행
  - Stage 2(LLM)는 **ANOMALY에서만** 호출

### 3.2 Stage 분리의 이유: 지연(Latency)

- Stage 1은 로컬에서 <1ms 수준(문서 기준)으로 즉시 판정 가능
- Stage 2(LLM)는 네트워크/모델 응답 시간에 의해 수백~수천 ms 지연이 발생
- 운영 시스템에서 “판단/경보”는 빠를수록 좋고, “설명/권장”은 상대적으로 늦어도 됨
- 따라서:
  - **판정(ANOMALY/NORMAL)**은 Stage 1로 즉시 결정
  - **설명/대응 권장**은 Stage 2/3로 후행 보강

### 3.3 Stage 분리의 이유: 신뢰성(Reliability)과 장애 격리

LLM API는 다음과 같은 운영 리스크를 갖습니다.

- 외부 의존성(네트워크, API rate limit, 키/권한)
- 모델/정책 변경에 따른 응답 변동
- 비결정성(nondeterminism)

TerraNeuron은 이를 “장애가 나도 코어 파이프라인이 멈추지 않도록” 격리합니다.

- Stage 1만으로도 시스템은 계속 `processed-insights`를 생성할 수 있어야 함
- Stage 2는 비활성/실패 시 graceful degradation(문서/구성에 이미 존재)

### 3.4 Stage 3(RAG)의 이유: “설명 가능성”과 “도메인 고정”

- LLM은 일반 언어 능력이 강하지만, 스마트팜 도메인(작물/환경/장비)에 대한 **정확한 근거**가 부족할 수 있음
- Stage 3(RAG)는:
  - 지식베이스(매뉴얼/가이드/과거 사례)를 벡터 DB(ChromaDB)에 저장
  - 유사도 검색으로 관련 근거를 찾아
  - 권장안의 컨텍스트/근거를 보강

결과적으로 “LLM 응답”이 단독으로 운영 결정을 주도하는 것이 아니라, **도메인 문서 기반으로 근거가 연결된 advisory output**을 제공합니다.

### 3. Hybrid AI Architecture (Critical Section)

TerraNeuron’s hybrid AI architecture is not about “using AI everywhere.” It is about **controlling cost/latency/reliability/failure risk** while increasing the information density operators can act on. That’s why the pipeline is split into Stage 1/2/3.

#### 3.1 Why split: Cost

- Normal sensor events dominate; anomalies are comparatively sparse.
- Calling an LLM for every event causes:
  - linear cost growth (event volume × tokens/pricing)
  - poor predictability (traffic spikes = cost spikes)
- Therefore:
  - Stage 1 (local) always acts as the filter/gate
  - Stage 2 (LLM) is invoked **only for ANOMALY**

#### 3.2 Why split: Latency

- Stage 1 can decide immediately (<1ms per docs)
- Stage 2 (LLM) incurs network/model latency (hundreds to thousands of ms)
- In operational systems, fast **classification/alerting** matters more than fast **explanations**
- Therefore:
  - anomaly classification is decided deterministically in Stage 1
  - explanations and recommendations are appended later via Stage 2/3

#### 3.3 Why split: Reliability and fault isolation

LLM APIs introduce operational risks:

- external dependency (network, rate limits, keys/permissions)
- output drift due to model/policy changes
- nondeterminism

TerraNeuron isolates these risks so the core pipeline continues even if the LLM fails:

- The system must still generate `processed-insights` using Stage 1 alone.
- Stage 2 is optional and can degrade gracefully when disabled/failing.

---

## 3.5 Phase 3: Security Layer Implementation (January 2026) ✅ NEW

Phase 3에서는 프로덕션 환경을 위한 보안 계층이 구현되었습니다.

### JWT 기반 인증/인가 시스템

```
┌─────────────────────────────────────────────────────────┐
│                    API Request Flow                      │
├─────────────────────────────────────────────────────────┤
│  Client                                                  │
│    │                                                     │
│    │ POST /api/auth/login (credentials)                  │
│    ▼                                                     │
│  AuthController                                          │
│    │ ─── validate credentials ───►                       │
│    │ ◄── generate JWT tokens ────                        │
│    │                                                     │
│    │ { access_token, refresh_token }                     │
│    ▼                                                     │
│  Client (stores tokens)                                  │
│    │                                                     │
│    │ Authorization: Bearer <access_token>                │
│    ▼                                                     │
│  JwtAuthenticationFilter                                 │
│    │ ─── validate token ───►                             │
│    │ ─── extract roles ───►                              │
│    │ ─── set SecurityContext ───►                        │
│    ▼                                                     │
│  Protected API Endpoint                                  │
└─────────────────────────────────────────────────────────┘
```

### Role-based Access Control (RBAC)

| Role | Permissions | Use Case |
|------|-------------|----------|
| `ROLE_ADMIN` | Full access, user management | System administrators |
| `ROLE_OPERATOR` | Action approval/rejection, dashboard | Farm operators |
| `ROLE_VIEWER` | Read-only access | Dashboard viewers |

### Security Components

- `JwtTokenProvider`: 토큰 생성/검증 (HS256 알고리즘)
- `JwtAuthenticationFilter`: 요청별 토큰 검증
- `SecurityConfig`: Spring Security 설정, CORS, 엔드포인트 보호

이 보안 계층은 Action Protocol과 통합되어, **승인 권한이 있는 사용자만** Action Plan을 승인/거부할 수 있습니다.

#### 3.4 Why Stage 3 (RAG): explainability and domain grounding

- LLMs are strong at language but may lack grounded, domain-specific correctness.
- Stage 3 (RAG):
  - stores manuals/guides/historical cases in a vector DB (ChromaDB)
  - retrieves relevant context via similarity search
  - grounds/enriches recommendations with domain evidence

This keeps outputs in an **advisory, grounded** space rather than letting LLM text drive operations directly.

---

## 4. TerraNeuron이 의도적으로 하지 않는 것 (Exclusions)

TerraNeuron 설계에서 중요한 점은 “할 수 있는 것”보다 “안 하기로 한 것”이 명확하다는 것입니다. 특히 실패 비용이 큰 운영 시스템에서는 제외 항목이 곧 안전성 요구사항입니다.

### 4.1 자율 에이전트(Autonomous agents) 금지

- 제외 내용: LLM이 목표를 세우고 하위 작업을 자동 실행하는 형태의 agent loop
- 이유:
  - 실행 단계에서의 비결정성 증가
  - 재현/감사(audit) 난이도 증가
  - 오동작 시 피해 규모가 커짐(장비/농작물)

### 4.2 End-to-end LLM 실행 금지(LLM as executor)

- 제외 내용: “센서 이벤트 → LLM 프롬프트 → LLM이 바로 액션 호출” 같은 end-to-end 패턴
- 이유:
  - 안전 검증/권한 검증을 우회하기 쉬움
  - LLM 응답은 계약(contract) 기반 인터페이스가 아니며, 스키마 안정성이 낮음
  - 실패 시 fail-safe 설계를 적용하기가 어려움

대신 TerraNeuron은 `CloudEvents v1.0` 기반 Action Protocol과 `trace_id`를 통해 **실행을 프로토콜/검증 계층으로 끌어내려(downshift)**, LLM은 advisory output만 생성하도록 역할을 고정합니다.

### 4.3 프로덕션 온라인 러닝(Online learning) 금지

- 제외 내용: 운영 중 모델 파라미터/정책을 자동 업데이트하여 즉시 반영하는 패턴
- 이유:
  - 버전/행동 추적이 어렵고, 사고 발생 시 원인 규명이 늦어짐
  - 데이터 드리프트/오염에 취약
  - 검증되지 않은 모델 변화가 운영에 곧바로 영향을 미침

### 4.4 “AI를 everywhere” 쓰지 않음

- 제외 내용: 정상 이벤트까지 LLM 호출, 데이터 저장/라우팅에 AI 개입
- 이유:
  - 비용/지연/장애 도메인이 확대
  - 운영 시스템의 핵심은 **정합성과 가용성**인데, AI는 이를 강화하기보다 흔들 수 있음

### 4. What TerraNeuron Intentionally Does NOT Do

A key architectural strength is that TerraNeuron has explicit exclusions—critical for high-cost-of-failure operational systems.

#### 4.1 No autonomous agent loops

- Excluded: agentic loops where an LLM sets goals and executes sub-tasks autonomously
- Why:
  - increases nondeterminism at execution time
  - weakens reproducibility and auditability
  - amplifies blast radius when things go wrong

#### 4.2 No end-to-end LLM execution (LLM as executor)

- Excluded: “event → prompt → LLM directly triggers actions” patterns
- Why:
  - easy to bypass safety/permission validation
  - LLM output is not a stable, contract-driven interface
  - fail-safe behavior is harder to guarantee

Instead, TerraNeuron “downshifts” execution into a **protocol + validation** layer (CloudEvents v1.0 + `trace_id`), keeping LLM output strictly advisory.

#### 4.3 No online learning in production

- Excluded: automatically updating model behavior in production without controlled release
- Why:
  - hard to trace behavior/version when incidents occur
  - vulnerable to drift/poisoning
  - unverified changes can directly impact operations

#### 4.4 Not using AI everywhere

- Excluded: calling LLM on normal events; letting AI touch routing/persistence boundaries
- Why:
  - expands cost/latency/failure domains
  - operational correctness/availability should not hinge on AI

---

## 5. Asgard vs TerraNeuron (Comparison)

두 프로젝트의 차이는 “AI 기술”이 아니라, **시스템이 책임지는 결과의 종류**에 있습니다.

### 5.1 TerraNeuron = 운영(Operational) 의사결정 시스템

- 입력: 실시간 센서 이벤트
- 출력: 운영 가능한 인사이트(그리고 향후 Action Protocol 기반 plan/command 이벤트)
- 후속: 사람 승인/안전 검증/감사 추적이 전제
- 실패 비용: 장비/농작물/현장 안전

### 5.2 Asgard = 관찰/분석(Observability/Analysis) 시스템

(질문에서 제공된 정의 기반)

- Heimdall: ingress/control/policy/routing
- Bifrost: AI 분석 계층(local vs cloud LLM routing)
- 입력: 로그/이벤트/트레이스
- 출력: “시스템이 왜 이렇게 동작했는지”에 대한 해석/설명
- 특징: 분석 결과가 운영 액션을 직접 수행하지 않음(비즈니스 액션 executor가 아님)

### 5.3 공통점(의미 있는 부분)

- 둘 다 “AI를 경계 밖으로 밀어내고(운영 경계에 붙이지 않고)”, **해석/권장/설명** 역할에 제한
- local vs cloud 경로 분리로 비용/지연/가용성을 제어

### 5. Asgard vs TerraNeuron (Comparison)

The difference is not “AI technique” but **what outcomes the system is responsible for**.

#### 5.1 TerraNeuron = operational decision system

- Input: real-time sensor events
- Output: operational insights (and eventually plan/command events under the Action Protocol)
- Follow-up: requires human approval/safety validation/audit trail
- Failure cost: physical devices/crops/on-site safety

#### 5.2 Asgard = observability/analysis system

(based on your provided description)

- Heimdall: ingress/control/policy/routing
- Bifrost: AI analysis layer (routes to local vs cloud LLM)
- Input: logs/events/traces
- Output: interpretation/explanation of system behavior
- Property: does not directly execute business actions

#### 5.3 Meaningful overlap

- Both constrain AI to **interpretation/recommendation** rather than execution.
- Both split local vs cloud routes to control cost/latency/availability.

---

## 6. TerraNeuron을 Andercore에 매핑하기 (1:1 Structural Mapping)

Andercore의 RFQ 기반 거래 워크플로우(수집 → 정규화 → 가격/공급사 판단 → 실행 → 결과 피드백)는 TerraNeuron의 구조와 거의 동일한 형태의 “운영 이벤트 루프”로 볼 수 있습니다.

아래는 요구하신 1:1 매핑입니다.

### 6.1 이벤트/서비스 매핑

| TerraNeuron | Andercore (Trading) | 구조적 의미 |
|---|---|---|
| Sensor event | RFQ (request-for-quote) ingestion | 입력 이벤트의 대량/연속 유입 |
| `terra-sense` (ingestion) | RFQ ingestion + 최소 검증 | 유입 경계에서의 스키마 검증/수용 |
| Kafka `raw-sensor-data` | RFQ raw topic (예: `rfq.raw`) | 원천 이벤트 저장/리플레이 가능한 이벤트 로그 |
| `terra-cortex` Stage 1 (local analyzer) | deterministic normalization + rule checks | 즉시 판정 가능한 규칙/정합성 검사 |
| `terra-cortex` Stage 2 (LLM, anomaly-only) | LLM-based decision support only on “exception” | 정상 케이스는 자동 처리, 예외만 LLM 자문 |
| `terra-cortex` Stage 3 (RAG) | RAG over pricing policy / supplier history / contract terms | 회사 도메인 지식에 근거한 설명/근거 첨부 |
| Kafka `processed-insights` | decision topic (예: `rfq.decision`) | 판단 결과의 이벤트 스트림 |
| `terra-ops` (MySQL + APIs) | execution orchestration + state store + audit | 실행/상태/감사/조회 중심 서비스 |
| Action Protocol (CloudEvents + 4-layer validation) | trading workflow commands with safety gates | 실행 단계의 표준화/감사 가능성/Fail-safe |

### 6.2 “워크플로우가 구조적으로 동일”하다는 의미

둘 다 다음 형태의 패턴을 공유합니다.

1) **High-volume intake**: 입력 이벤트가 많고(센서/RFQ), 정상 케이스가 대부분
2) **Event log + replay**: Kafka 토픽을 통해 리플레이/재처리 가능
3) **Decision support with safety boundary**:
   - 판단은 빠르고 결정적으로
   - 예외만 느리지만 풍부한 설명/근거(LLM/RAG)
4) **Execution as deterministic workflow**:
   - 실행은 검증/권한/감사 체계를 통과해야 함
5) **Feedback**:
   - 결과(성공/실패/효과)를 이벤트로 다시 적재하여 시스템 품질을 측정/개선

Andercore에 적용하면, RFQ 처리의 “결정(가격/공급사)”은 TerraNeuron의 “이상 판정/권장”에 대응하고, 실제 발주/계약/정산은 TerraNeuron의 “운영/실행”에 대응합니다.

### 6. Mapping TerraNeuron to Andercore (1:1 Structural Mapping)

Andercore’s RFQ-driven trading workflow (ingest → normalize → pricing/supplier decision → execute → feedback) is structurally the same kind of **operational event loop** as TerraNeuron.

#### 6.1 Service/event mapping

| TerraNeuron | Andercore (Trading) | Structural meaning |
|---|---|---|
| Sensor event | RFQ ingestion | high-volume inbound events |
| `terra-sense` (ingestion) | RFQ ingestion + minimal validation | boundary validation/admission control |
| Kafka `raw-sensor-data` | RFQ raw topic (e.g., `rfq.raw`) | source-of-truth event log with replay |
| `terra-cortex` Stage 1 | deterministic normalization + rule checks | fast deterministic classification/validation |
| `terra-cortex` Stage 2 (anomaly-only) | LLM decision support only for exceptions | LLM used only when needed |
| `terra-cortex` Stage 3 (RAG) | RAG over pricing policy / supplier history / contract terms | grounded reasoning with domain knowledge |
| Kafka `processed-insights` | decision topic (e.g., `rfq.decision`) | decision output stream |
| `terra-ops` (MySQL + APIs) | execution orchestration + state store + audit | execution/state/audit/query |
| Action Protocol (CloudEvents + safety) | trading commands with safety gates | standardized auditable execution boundary |

#### 6.2 What “structurally identical” means

Both share these characteristics:

1) **High-volume intake** where normal cases dominate
2) **Event log + replay** through Kafka topics
3) **Decision support with a safety boundary**
   - fast deterministic classification
   - slow-but-rich explanation only on exceptions (LLM/RAG)
4) **Deterministic execution workflows** gated by validation/permissions/audit
5) **Feedback loop** to measure and improve system quality

Applied to Andercore: RFQ decisioning (pricing/supplier) maps to TerraNeuron’s anomaly decisioning/recommendation; actual ordering/contracting/settlement maps to TerraNeuron’s operations/execution.

---

## 7. 왜 이것이 Andercore에 강한 핏이 되는가 (System-Level Fit)

이 섹션은 “기술 스택” 나열이 아니라, Andercore가 필요로 하는 **프로덕션 의사결정 시스템 설계 역량**과 TerraNeuron/Asgard가 증명하는 역량의 대응 관계를 설명합니다.

### 7.1 이벤트 기반 트랜잭션 워크플로우 설계 감각

TerraNeuron은 Kafka를 중심으로 **수집/분석/운영을 느슨하게 결합**합니다.

- ingestion(`terra-sense`)와 decisioning(`terra-cortex`)과 operations(`terra-ops`)가 분리되어 독립적으로 스케일/장애 격리 가능
- Andercore의 RFQ 파이프라인에서도 동일하게:
  - ingestion, normalization, pricing decision, execution, post-trade feedback를 서비스/토픽 단위로 분해하여 독립 배포/확장 가능

### 7.2 “AI를 운영 경계에 붙이지 않는” 리스크 인지형 설계

TerraNeuron은 다음을 이미 구조에 반영합니다.

- LLM은 anomaly-only로 제한(비용/지연/가용성 제어)
- 실행은 CloudEvents + 안전 검증 계층으로 격리(`trace_id`, 4-layer validation, fail-safe)
- 결과적으로 AI는 “설명/권장”이고, **결정적 실행은 프로토콜/정책 기반**

B2B 거래는 실패 비용이 크므로(금전/신뢰/법적 리스크), Andercore에서 필요한 것은 “LLM이 잘 말한다”가 아니라 “LLM이 **잘 못 말할 때**도 시스템이 안전하게 동작한다”입니다.

### 7.3 감사 가능성(Auditability)과 추적성(Traceability)

- Action Protocol은 CloudEvents 스키마와 `trace_id`를 강제하여 분산 추적/감사를 전제로 함
- 거래 시스템도 동일하게:
  - RFQ → decision → order/contract → fulfillment → exception의 전체 체인을 추적해야 함
  - 어떤 판단이 어떤 실행으로 이어졌는지, 책임소재/재현 가능성이 중요

### 7.4 폴리글랏 저장소/관찰 가능성/운영 준비도

- InfluxDB(시계열) + MySQL(관계형) + Redis(rate limiting) + ChromaDB(RAG) + Prometheus/Grafana
- 이는 “데이터 성격에 맞는 저장/관측 스택”을 선택하고 운영 가능한 형태로 통합한 경험을 의미

Andercore에서도:
- 이벤트 로그(Kafka), 상태 저장(OLTP), 분석/집계(warehouse/OLAP), 캐시/레이트리밋, 관측(메트릭/로그/트레이스)을 일관되게 설계/운영할 역량이 요구됨

### 7.5 Asgard가 보강하는 역량: 분석 시스템과 운영 시스템의 경계 설정

Asgard는 “관찰/설명” 시스템으로서 운영 액션과 분리되어 있습니다. 이는 Andercore가 AI를 도입할 때 흔히 생기는 위험(관찰계 AI가 운영계를 침범)을 방지하는 설계 관점을 제공합니다.

### 7. Why This Makes You a Strong Fit for Andercore

This section maps demonstrated capabilities to what Andercore needs: **production decision systems**, not AI demos.

#### 7.1 Event-driven transaction workflow design

TerraNeuron decouples ingestion/decisioning/operations via Kafka:

- `terra-sense`, `terra-cortex`, and `terra-ops` can scale and fail independently
- The same decomposition applies to an RFQ pipeline:
  - ingestion, normalization, pricing decision, execution, post-trade feedback as separate services/topics

#### 7.2 Risk-aware AI: not attaching AI to execution boundaries

TerraNeuron already encodes these safety constraints:

- LLM is anomaly-only (controls cost/latency/availability)
- execution is isolated behind a protocol/validation layer (CloudEvents, `trace_id`, 4-layer validation, fail-safe)
- AI remains “explain/recommend,” while execution stays deterministic and policy-driven

In B2B trading, failure costs are high (money/trust/legal exposure). The key is not “LLM speaks well,” but “the system remains safe when the LLM is wrong/unavailable.”

#### 7.3 Auditability and traceability

- The Action Protocol enforces CloudEvents schema and `trace_id`, enabling distributed tracing and audit
- Trading systems need the same:
  - trace RFQ → decision → contract/order → fulfillment → exceptions
  - reproduce why a decision led to a specific execution

#### 7.4 Polyglot storage, observability, operational readiness

- InfluxDB (time-series) + MySQL (OLTP) + Redis (rate limiting) + ChromaDB (RAG) + Prometheus/Grafana
- This demonstrates selecting the right storage/observability stack per data shape and integrating it operationally

Andercore similarly requires coherent design across event logs, OLTP state, analytics/aggregation, caching/rate limiting, and telemetry.

#### 7.5 Asgard reinforces boundary-setting between analysis and operations

Asgard is an observability/explanation system separated from business execution. This helps avoid a common failure mode in AI adoption: analysis AI leaking into operational execution boundaries.

---

## 8. 최종 요약 (Short but Strong)

TerraNeuron은 Kafka 기반 이벤트 루프에 **결정적 실행(ops)**과 **비결정적 조언(AI)**를 분리해 붙인 운영 시스템입니다. CloudEvents + `trace_id` + 안전 검증 계층을 통해 “실행”을 프로토콜로 고정하고, LLM/RAG는 anomaly-only advisory로 제한하여 비용/지연/장애 도메인을 통제합니다.

Andercore의 RFQ 거래 파이프라인은 동일한 구조(유입 이벤트 → 정규화/판정 → 실행 → 피드백)이며, 실패 비용이 큰 도메인에서 요구되는 것은 **정확한 시스템 경계, 감사 가능성, 그리고 리스크 인지형 AI 설계**입니다. TerraNeuron/Asgard는 이 요구사항을 시스템적으로 충족시키는 설계/구현 경험을 보여줍니다.

### 8. Final Summary (Short but Strong)

TerraNeuron is an operational event loop built on Kafka, with a deliberate separation between **deterministic execution (ops)** and **non-deterministic advisory (AI)**. By enforcing CloudEvents + `trace_id` + safety validation, execution is pinned to a protocol boundary, while LLM/RAG stays anomaly-only and advisory—controlling cost, latency, and failure domains.

Andercore’s RFQ trading workflow is structurally the same (ingest → normalize/decide → execute → feedback), and the high-cost-of-failure nature demands **clear system boundaries, auditability, and risk-aware AI design**. TerraNeuron/Asgard demonstrate those capabilities at a system level.
