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
- [x] Weather integration *(Step 1 완료)*

### ✅ Phase 4.D: Weather API + InfluxDB 완성 - COMPLETED
> *Goal: 실시간 기상 데이터 연동 + 시계열 DB 저장 파이프라인 완성*

**InfluxDB 시계열 저장 (terra-sense)**
- [x] `InfluxDbConfig.java` — InfluxDB 클라이언트 빈 설정
- [x] `InfluxDbWriterService.java` — 센서 데이터 → InfluxDB Point 변환 & 저장
- [x] `IngestionController.java` 수정 — Kafka + InfluxDB 이중 저장 (InfluxDB 실패해도 Kafka 정상 동작)

**Weather API 연동 (terra-cortex)**
- [x] `weather_provider.py` — OpenWeatherMap 비동기 연동 + TTL 캐시 (10분)
- [x] `models.py` — `WeatherContext` 모델 추가, `Insight`에 `weatherContext` 필드 추가
- [x] `local_analyzer.py` — 날씨 기반 동적 임계값 조정 (폭염→온도 완화, 강수→습도 완화)
- [x] `cloud_advisor.py` — LLM 프롬프트에 날씨 컨텍스트 주입 (RAG + Simple 모두)
- [x] `main.py` — 파이프라인에 Weather Provider 통합 (Step 0: fetch → Step 1: analyze → Step 2: LLM)
- [x] `docker-compose.yml` — `WEATHER_API_KEY`, `WEATHER_LAT`, `WEATHER_LON` 환경변수 추가

### ✅ Phase 4.E: 작물 모델링 (Step 2) - COMPLETED
> *Goal: 작물별 생장 단계 모델링 + 작물 인식 분석 파이프라인 완성*

**MySQL 스키마 (terra-ops)**
- [x] `crop_profiles` 테이블 — 작물 프로필 (5종: 토마토, 딸기, 상추, 오이, 파프리카)
- [x] `growth_stages` 테이블 — 생장 단계별 환경 조건 (4-point 범위: min/optimalLow/optimalHigh/max)
- [x] `farm_crops` 테이블 — 농장-작물 매핑 + 현재 생장 단계 추적
- [x] 시드 데이터: 5개 작물 × 5 단계 = 25개 생장단계 + 3개 데모 farm_crops

**JPA 엔티티 & Repository (terra-ops)**
- [x] `CropProfile.java` — 작물 프로필 엔티티 (@OneToMany → GrowthStage)
- [x] `GrowthStage.java` — 생장 단계 엔티티 (온도/습도/CO2/광/토양수분 범위)
- [x] `FarmCrop.java` — 농장-작물 매핑 (@ManyToOne → CropProfile, @Transient getCurrentGrowthStage)
- [x] `CropProfileRepository.java` — findByCropCode, findByIsActiveTrue
- [x] `GrowthStageRepository.java` — findByCropCode (JPQL), findByCropProfileIdAndStageOrder
- [x] `FarmCropRepository.java` — findActiveCropsByFarmId (FETCH JOIN), findActiveCropByFarmIdAndZone

**작물 관리 서비스 & API (terra-ops)**
- [x] `CropService.java` — 작물 CRUD, 생장단계 자동 진행, 최적 환경 조건 조회 (파종일 기반 자동 단계 계산)
- [x] `CropController.java` — REST API:
    - `GET /api/crops` — 전체 작물 목록
    - `GET /api/crops/{code}` — 작물 상세 (생장단계 포함)
    - `GET /api/crops/{code}/stages` — 생장 단계 목록
    - `GET /api/farms/{farmId}/crops` — 농장 재배 작물 목록
    - `POST /api/farms/{farmId}/crops` — 작물 배정
    - `PUT /api/farms/{farmId}/crops/{id}/advance-stage` — 생장 단계 수동 진행
    - `GET /api/farms/{farmId}/optimal-conditions` — **핵심: 현재 최적 환경 조건 조회 (terra-cortex 연동)**

**작물 인식 분석 (terra-cortex)**
- [x] `crop_profile.py` — terra-ops HTTP 연동 + TTL 캐시 (30분), CropContext/CropCondition/SensorRange 모델
- [x] `local_analyzer.py` — 작물 생장단계별 동적 임계값 (온도/습도/CO2/광/토양수분 모두)
- [x] `cloud_advisor.py` — LLM 프롬프트에 작물 컨텍스트 주입 (RAG + Simple 모두)
- [x] `main.py` — 파이프라인 Step 0.5: crop context fetch → analyze → LLM
- [x] `models.py` — `Insight`에 `cropContext` 필드 추가
- [x] `docker-compose.yml` — `TERRA_OPS_URL`, `CROP_CACHE_TTL` 환경변수, terra-ops 의존성 추가

### ✅ Phase 4.F: 시계열 분석 (Step 3) - COMPLETED
> *Goal: InfluxDB Flux 쿼리 기반 시계열 데이터 추세 분석 + 예측 경고 파이프라인*

**시계열 분석 엔진 (terra-cortex)**
- [x] `timeseries.py` — InfluxDB Flux HTTP 쿼리 엔진 (httpx 기반, 라이브러리 무의존)
    - 이동 평균 (Moving Average) 계산 + 편차 분석
    - 추세 방향 감지 (rising / falling / stable) — 전반/후반 평균 비교
    - 급변 감지 (Spike Detection) — 2σ 초과 시 경보
    - 선형 회귀 예측 (10분 ahead) — 최근 30 포인트 기반
    - 변화율 (Rate of Change) 계산 — /h 단위
    - 일간 통계 (Daily Stats) — Flux aggregateWindow 1d mean
    - 시간대별 패턴 (Hourly Pattern) — 7일 평균 시간별 min/avg/max
    - TTL 캐시 (2분) — (farmId, sensorType) 키 기반 중복 조회 방지
    - `/info` 엔드포인트용 `get_config()` 통계 API

**모델 확장 (terra-cortex)**
- [x] `models.py` — `Insight`에 `trendContext` 필드 추가

**로컬 분석기 추세 통합 (terra-cortex)**
- [x] `local_analyzer.py` — 3가지 추세 기반 분석 강화:
    1. **스파이크 감지**: 2σ 초과 시 NORMAL → ANOMALY 승격 + "📈 급변 감지" 메시지
    2. **스파이크 보강**: 기존 ANOMALY에 이동평균 편차 정보 추가
    3. **예측 경고**: rising 추세 + 10분 예측값이 임계치 초과 시 ANOMALY 승격 + "📊 예측 경고"

**클라우드 어드바이저 추세 통합 (terra-cortex)**
- [x] `cloud_advisor.py` — LLM 프롬프트에 시계열 추세 컨텍스트 주입:
    - RAG 프롬프트: 방향/변화율/이동평균/편차/범위/스파이크/예측값 섹션
    - Simple 프롬프트: 추세 요약 1문장 추가

**파이프라인 통합 (terra-cortex)**
- [x] `main.py` — 분석 파이프라인 확장:
    - Step 0.75: 시계열 추세 컨텍스트 조회 (캐시, 논블로킹)
    - `trend_ctx`를 `local_analyzer` + `cloud_advisor` 양쪽에 전달
    - Lifespan에 `TimeSeriesAnalyzer` 초기화
    - `/info` 엔드포인트에 Trend Analyzer 섹션 추가
    - REST API 추가:
        - `GET /api/trends/{farmId}/{sensorType}` — 실시간 추세 분석
        - `GET /api/trends/{farmId}/{sensorType}/daily?days=7` — 일간 통계
        - `GET /api/trends/{farmId}/{sensorType}/hourly?days=7` — 시간대별 패턴

**인프라 (docker-compose)**
- [x] `docker-compose.yml` — terra-cortex에 InfluxDB 연동 설정:
    - `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` 환경변수
    - `TREND_CACHE_TTL`, `TREND_WINDOW` 설정값
    - `influxdb` 서비스 의존성 추가

### ✅ Phase 4.G: 제어 루프 완성 (Step 4) - COMPLETED
> *Goal: MQTT 양방향 제어 루프 + Kafka↔MQTT 브릿지 + 디바이스 상태 모니터링*

**MQTT 설정 & 클라이언트 (terra-sense)**
- [x] `MqttConfig.java` — Eclipse Paho MQTT 클라이언트 빈 (auto-reconnect, MemoryPersistence)
- [x] `DeviceCommand.java` — 명령 모델 (commandId, traceId, planId, targetAssetId, actionType 등)
- [x] `DeviceStatus.java` — 디바이스 상태 모델 (assetId, state: online/offline/running/idle/error)

**양방향 MQTT 게이트웨이 (terra-sense)**
- [x] `MqttGatewayService.java` — 양방향 MQTT 브릿지 (MqttCallback 구현)
    - 아웃바운드: `terra/devices/{farmId}/{assetId}/command` → IoT 디바이스
    - 인바운드: `terra/devices/+/+/status` → 인메모리 디바이스 상태 캐시
    - 인바운드: `terra/sensors/+/+/data` → Kafka `raw-sensor-data` 포워딩
    - 송신/수신 카운터, 디바이스 상태 조회, MQTT 통계 API

**Kafka → MQTT 브릿지 (terra-sense)**
- [x] `DeviceCommandConsumer.java` — Kafka `terra.control.command` 소비 → MQTT 발행
    - CloudEvents 파싱 → DeviceCommand 변환 → MQTT 발행
    - 실행 결과를 `terra.control.feedback` 토픽으로 피드백 (DELIVERED / FAILED)
- [x] `KafkaConfig.java` 수정 — 명령 소비자 팩토리 + 피드백 생산자 팩토리 + 토픽 선언
- [x] `application.properties` 수정 — MQTT 설정값 (broker, QoS, timeout, keepalive 등)

**디바이스 상태 REST API (terra-sense)**
- [x] `DeviceController.java` — REST API:
    - `GET /api/v1/devices/status` — 전체 디바이스 상태 조회
    - `GET /api/v1/devices/status/{farmId}/{assetId}` — 개별 디바이스 상태
    - `GET /api/v1/devices/mqtt/stats` — MQTT 게이트웨이 통계

**피드백 루프 (terra-ops)**
- [x] `CommandFeedbackConsumer.java` — Kafka `terra.control.feedback` 소비
    - DELIVERED → ActionPlan execution_result 업데이트
    - EXECUTED → ActionPlan status=EXECUTED
    - FAILED → ActionPlan status=FAILED
    - `auditService.logCommandFeedback()` 감사 로그 저장
- [x] `AuditService.java` 수정 — `logCommandFeedback()` 메서드 추가
- [x] `application.properties` 수정 — `kafka.topic.control-feedback` 설정

### ✅ Phase 4.H: 농업인 UI (Step 5) - COMPLETED
> *Goal: Next.js 14 + React 18 + Tailwind CSS 기반 실시간 대시보드*

**프로젝트 설정 (terra-dashboard)**
- [x] `package.json` — Next.js 14.2, React 18.3, Recharts 2.12, Lucide icons, Tailwind CSS 3.4
- [x] `tsconfig.json` — TypeScript 5.6 + `@/*` 경로 별칭
- [x] `next.config.js` — API 프록시 (cortex:8082, ops:8080, sense:8081) + standalone 빌드
- [x] `tailwind.config.js` — 커스텀 terra green 팔레트 (50-900)
- [x] `postcss.config.js` — Tailwind PostCSS 설정
- [x] `globals.css` — Tailwind 베이스 + card/badge 유틸리티 클래스

**레이아웃 & 라이브러리**
- [x] `layout.tsx` — 루트 레이아웃, 스티키 헤더 네비게이션 (대시보드/센서/작물/제어/알림)
- [x] `src/lib/api.ts` — API 클라이언트 (cortex, ops, sense 서비스 호출)
- [x] `src/lib/utils.ts` — 유틸리티 함수 (cn, sensorLabel, sensorUnit, statusColor, trendIcon)

**대시보드 페이지 (5개)**
- [x] `page.tsx` — 메인 대시보드: 센서 추세 카드 3종 + AI 파이프라인/액션 통계/MQTT 통계
- [x] `sensors/page.tsx` — 센서 상세: 8개 지표 카드 + 최근 데이터 테이블 + 일간/시간대별 패턴
- [x] `crops/page.tsx` — 작물 관리: 농장 작물 그리드 + 최적 조건 + 전체 프로필 테이블
- [x] `actions/page.tsx` — 제어 액션: 승인 대기 목록 + 승인/거부 버튼 + 통계 뱃지
- [x] `alerts/page.tsx` — 알림 센터: 알림 탭 (심각도별 색상) + AI 인사이트 탭

**배포 설정**
- [x] `Dockerfile` — Multi-stage 빌드 (node:20-alpine → standalone 실행)
- [x] `.dockerignore` — node_modules, .next, .git 제외
- [x] `docker-compose.yml` — terra-dashboard 서비스 추가 (포트 3001:3000, depends_on: cortex/ops/sense)

### ✅ Phase 4.I: 지식 축적 (Step 6) - COMPLETED
> *Goal: 운영 데이터 기반 자동 지식 수집 + RAG 자동 강화 파이프라인*

**지식 축적 파이프라인 (terra-cortex)**
- [x] `knowledge_collector.py` — 자동 지식 수집 엔진:
    - **인사이트 패턴 축적**: 반복 이상 패턴 감지 (3회 이상 발생 시 자동 추출)
    - **액션 결과 학습**: terra-ops 액션 통계 수집 → 성공률 분석 → 개선 지식 생성
    - **기상-센서 상관관계**: 계절별 센서 추세 상관 분석 → 지역 특화 패턴 기록
    - **자동 ChromaDB 임베딩**: 수집된 지식을 RAG 벡터 DB에 자동 추가
    - **백업 파일 저장**: Markdown 파일로 `data/knowledge_base/generated/`에 저장
    - **주기적 자동 수집**: 설정 가능한 주기 (기본 60분마다)
    - `KnowledgeEntry` 데이터 모델 (source, category, title, content, metadata)
    - `InsightAccumulator` — 인사이트 라이브 축적기

**파이프라인 통합 (terra-cortex)**
- [x] `main.py` — 분석 파이프라인 Step 5: 인사이트 자동 축적
    - Lifespan: `KnowledgeCollector` 초기화 + 자동 수집 시작
    - Consumer Loop: 처리된 인사이트를 자동 축적 (`accumulate_insight()`)
    - `/` 엔드포인트에 지식 수집기 통계 추가
    - `/info` 엔드포인트에 Knowledge Pipeline 섹션 추가
    - REST API 추가:
        - `GET /api/knowledge/stats` — 지식 수집기 통계
        - `GET /api/knowledge/entries` — 수집된 지식 목록
        - `POST /api/knowledge/collect` — 수동 수집 트리거
        - `POST /api/knowledge/ingest` — 수동 지식 추가 + 즉시 임베딩

**인프라 (docker-compose)**
- [x] `docker-compose.yml` — terra-cortex에 지식 축적 설정:
    - `KNOWLEDGE_COLLECT_INTERVAL` — 자동 수집 주기 (기본 60분)
    - `KNOWLEDGE_BASE_PATH`, `CHROMA_DB_PATH` 환경변수

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
| InfluxDB 시계열 저장 | ✅ | `InfluxDbConfig.java`, `InfluxDbWriterService.java` |
| Weather API 연동 | ✅ | `weather_provider.py` |
| 작물 프로필 (DB) | ✅ | `CropProfile.java`, `GrowthStage.java`, `FarmCrop.java` |
| 작물 관리 API | ✅ | `CropService.java`, `CropController.java` |
| 작물 인식 분석 | ✅ | `crop_profile.py`, `local_analyzer.py`, `cloud_advisor.py` |
| 시계열 분석 엔진 | ✅ | `timeseries.py` |
| 추세 기반 이상탐지 | ✅ | `local_analyzer.py` (spike detection, predictive warning) |
| 추세 LLM 프롬프트 | ✅ | `cloud_advisor.py` (RAG + Simple trend injection) |
| 추세 REST API | ✅ | `main.py` (`/api/trends/` 3개 엔드포인트) |
| MQTT 제어 루프 | ✅ | `MqttConfig.java`, `MqttGatewayService.java`, `DeviceCommandConsumer.java` |
| 디바이스 모델 | ✅ | `DeviceCommand.java`, `DeviceStatus.java` |
| 디바이스 REST API | ✅ | `DeviceController.java` |
| 피드백 루프 | ✅ | `CommandFeedbackConsumer.java`, `AuditService.java` |
| React 대시보드 구조 | ✅ | `package.json`, `next.config.js`, `tailwind.config.js`, `layout.tsx` |
| 대시보드 API 클라이언트 | ✅ | `api.ts`, `utils.ts` |
| 대시보드 페이지 (5종) | ✅ | `page.tsx`, `sensors/`, `crops/`, `actions/`, `alerts/` |
| 대시보드 배포 | ✅ | `Dockerfile`, `.dockerignore`, `docker-compose.yml` |
| 지식 축적 파이프라인 | ✅ | `knowledge_collector.py` |
| 지식 REST API | ✅ | `main.py` (`/api/knowledge/` 4개 엔드포인트) |

**Total New Files:** 42+
**Modified Files:** 18+
