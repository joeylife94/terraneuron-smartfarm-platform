# 📊 TerraNeuron 프로젝트 현황 (Project Status)

> **📅 Last Updated:** 2026-02-27  
> **Version:** v2.1.0  
> **Purpose:** 프로젝트 합류 시 "이것만 읽으면 바로 일 시작 가능"한 현황 문서

---

## 📋 목차

1. [한눈에 보는 프로젝트 상태](#1-한눈에-보는-프로젝트-상태)
2. [Phase별 진행 현황](#2-phase별-진행-현황)
3. [서비스별 구현 현황](#3-서비스별-구현-현황)
4. [알려진 이슈 & 기술 부채](#4-알려진-이슈--기술-부채)
5. [우선순위 백로그](#5-우선순위-백로그)
6. [파일/디렉토리 맵](#6-파일디렉토리-맵)

---

## 1. 한눈에 보는 프로젝트 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| **E2E 파이프라인** (센서→AI→대시보드) | ✅ 동작 | HTTP 센서 수집 → Kafka → AI 분석 → MySQL 저장 |
| **Hybrid AI** (Local + LLM + RAG) | ✅ 동작 | OpenAI / Ollama 지원 |
| **Action Protocol** (CloudEvents + 승인) | ✅ 동작 | 4-Layer Safety + Audit Trail |
| **JWT 인증** | ⚠️ 구현됨/비활성 | SecurityConfig에서 `permitAll()` — RBAC 주석 처리됨 |
| **MQTT 수집** | ❌ 미구현 | 의존성만 존재, 리스너 클래스 없음 |
| **InfluxDB 저장** | ❌ 미구현 | 의존성만 존재, 서비스 클래스 없음 |
| **단위 테스트** | ❌ 없음 | 전체 서비스에 테스트 코드 0개 |
| **CI/CD** | ❌ 없음 | 파이프라인 미정의 |
| **프로덕션 배포** | ❌ 미완 | Docker Compose 로컬만 동작 |

---

## 2. Phase별 진행 현황

```
Phase 1: Genesis (인프라 + 기본 파이프라인)     ████████████████████ 100% ✅
Phase 2.A: Action Loop (CloudEvents + Safety)  ████████████████████ 100% ✅
Phase 2.B: Hybrid AI (LLM + RAG)              ████████████████████ 100% ✅
Phase 2.C: Edge Reflex (오프라인 안전장치)       ░░░░░░░░░░░░░░░░░░░░   0% ❌
Phase 3: Security (JWT + RBAC)                 ████████████████░░░░  80% ⚠️
Phase 4: Advanced Features                     ░░░░░░░░░░░░░░░░░░░░   0% ❌
```

### Phase 3 미완료 항목
- Spring Security **RBAC 규칙이 주석 처리**되어 `anyRequest().permitAll()` 상태
- AuthController가 **DB의 users 테이블을 사용하지 않고** 인메모리 하드코딩 (admin/admin123)
- JWT Secret이 application.properties에 하드코딩
- SSL/TLS 미설정
- Secrets Management (Vault 등) 미적용

---

## 3. 서비스별 구현 현황

### 3.1 terra-gateway (API Gateway)

| 항목 | 상태 | 세부 |
|------|------|------|
| Spring Cloud Gateway 라우팅 | ✅ | `/api/sense/**`, `/api/cortex/**`, `/api/ops/**` |
| Redis Rate Limiting | ✅ | sense=10/20, ops=20/50 |
| Circuit Breaker | ❌ | 미구현 |
| 인증 전파 | ❌ | Gateway 레벨 인증 없음 |
| CORS | ⚠️ | Wildcard (`*`) — 프로덕션 비안전 |

**주요 파일:** `services/terra-gateway/src/main/resources/application.properties`

---

### 3.2 terra-sense (IoT 수집 서비스)

| 항목 | 상태 | 세부 |
|------|------|------|
| HTTP REST 수집 | ✅ | `POST /api/v1/ingest/sensor-data` |
| Kafka Producer | ✅ | `raw-sensor-data` 토픽 |
| MQTT Listener | ❌ | Paho MQTT 의존성 있으나 리스너 미구현 |
| InfluxDB Writer | ❌ | 의존성 있으나 서비스 클래스 미구현 |
| 입력 값 범위 검증 | ⚠️ | `@NotBlank`/`@NotNull`만 있음, 범위 체크 없음 |
| 중복 제거 | ❌ | 미구현 |

**주요 파일:**
- `services/terra-sense/src/main/java/com/terraneuron/sense/controller/IngestController.java`
- `services/terra-sense/src/main/java/com/terraneuron/sense/model/SensorData.java`
- `services/terra-sense/src/main/java/com/terraneuron/sense/service/KafkaProducerService.java`

**데이터 모델 불일치:** `SensorData`에 `sensorId` + `farmId`가 있으나, terra-cortex는 `farmId`만 기대

---

### 3.3 terra-cortex (AI 엔진)

| 항목 | 상태 | 세부 |
|------|------|------|
| Kafka Consumer (raw-sensor-data) | ✅ | aiokafka 기반 |
| Stage 1: Local Analyzer | ✅ | 온도/습도/CO2/토양수분/조도 임계치 |
| Stage 2: Cloud LLM | ✅ | OpenAI + Ollama 지원, ANOMALY 시에만 호출 |
| Stage 3: RAG | ✅ | ChromaDB + all-MiniLM-L6-v2 |
| CloudEvents 생성 | ✅ | `processed-insights` + `action-plans` 생산 |
| Action Plan 자동 생성 | ✅ | 센서 타입→장치 매핑 (fan/heater/etc.) |
| LLM 실패 시 fallback | ✅ | Graceful degradation |
| Kafka Producer 재시도 | ❌ | 재시도 로직 없음 |

**주요 파일:**
- `services/terra-cortex/src/main.py` — Kafka 소비/생산 + 파이프라인 오케스트레이션
- `services/terra-cortex/src/local_analyzer.py` — 규칙 기반 분석
- `services/terra-cortex/src/cloud_advisor.py` — LLM 호출
- `services/terra-cortex/src/rag_advisor.py` — RAG 검색
- `services/terra-cortex/src/cloudevents_models.py` — CloudEvents 모델

**레거시 코드:** `logic.py`는 `local_analyzer.py`에 의해 대체됨 — 삭제 대상

**로컬 분석기 임계치:**
| 센서 타입 | warning | critical |
|----------|---------|----------|
| 온도 | >30°C | >35°C |
| 습도 | <40% | <30% |
| CO2 | >800ppm | >1000ppm |
| 토양수분 | <30% | <20% |
| 조도 | <200lux / >800lux | — |

---

### 3.4 terra-ops (운영 관리 서비스)

| 항목 | 상태 | 세부 |
|------|------|------|
| Dashboard API | ✅ | 인사이트 조회/필터/통계 |
| Action Plan CRUD | ✅ | 승인/거부/감사이력 |
| 4-Layer Safety Validation | ✅ | Logical/Context/Permission/DeviceState |
| Kafka Consumer | ✅ | `processed-insights` + `action-plans` |
| JWT Auth API | ✅ | login/refresh/validate |
| Spring Security RBAC | ⚠️ | 코드 존재하나 `permitAll()`로 비활성 |
| Audit Logging | ✅ | FarmOS Log 호환 |
| Plan 만료 스케줄러 | ✅ | 60초 주기 |
| Kafka → Command 발행 | ✅ | `terra.control.command` 토픽 |

**주요 파일:**
- `services/terra-ops/src/main/java/com/terraneuron/ops/controller/DashboardController.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/controller/ActionController.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/controller/AuthController.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/service/safety/SafetyValidator.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/service/AuditService.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/security/JwtTokenProvider.java`
- `services/terra-ops/src/main/java/com/terraneuron/ops/security/SecurityConfig.java`

**JPA 엔티티:** `Insight`, `ActionPlan`, `AuditLog`, `Sensor`

---

## 4. 알려진 이슈 & 기술 부채

### 🔴 Critical (보안)

| # | 이슈 | 위치 | 영향 |
|---|------|------|------|
| C-1 | **Security 비활성화** — `anyRequest().permitAll()` | `SecurityConfig.java` | 전체 API 미보호 |
| C-2 | **하드코딩 인메모리 사용자** — `admin/admin123` 평문 비교 | `AuthController.java` | DB users 테이블 미사용 |
| C-3 | **JWT Secret 하드코딩** | `terra-ops/application.properties` | 토큰 위조 가능 |
| C-4 | **CORS Wildcard** | `terra-gateway/application.properties` | 크로스 오리진 공격 |
| C-5 | **MQTT 익명 접근** | `mosquitto.conf` | 비인가 디바이스 접근 |

### 🟠 High (기능 누락)

| # | 이슈 | 위치 | 영향 |
|---|------|------|------|
| H-1 | **MQTT 리스너 미구현** | terra-sense | IoT 디바이스 MQTT 연결 불가 |
| H-2 | **InfluxDB Writer 미구현** | terra-sense | 시계열 데이터 미저장 |
| H-3 | **DB 스키마 불일치** — `init.sql`의 `sensor_id BIGINT FK` vs JPA의 `farm_id VARCHAR` | init.sql vs Insight.java | 데이터 무결성 문제 가능 |
| H-4 | **`terra.control.command` 소비자 없음** | ActionPlanService | 실행된 명령이 어디로도 전달 안 됨 |
| H-5 | **SafetyValidator Layer 4** — 디바이스 상태를 시뮬레이션 값으로 확인 | SafetyValidator.java | 안전하지 않은 명령 승인 가능성 |

### 🟡 Medium (품질)

| # | 이슈 | 위치 | 영향 |
|---|------|------|------|
| M-1 | **단위 테스트 0개** | 전체 서비스 | 회귀 테스트 안전망 없음 |
| M-2 | **레거시 코드** `logic.py` | terra-cortex | 혼란 유발 |
| M-3 | **Dashboard 페이지네이션 없음** | DashboardController | 대량 데이터 시 메모리 문제 |
| M-4 | **CI/CD 파이프라인 없음** | 프로젝트 루트 | 수동 배포만 가능 |
| M-5 | **`ddl-auto=update`** | terra-ops application.properties | 프로덕션에서 비제어 스키마 변경 |
| M-6 | **SensorData 모델 불일치** | terra-sense vs terra-cortex | `sensorId` 필드 호환성 |

---

## 5. 우선순위 백로그

### 🔥 즉시 (Sprint 1 — 보안 & 안정성)

| # | 작업 | 예상 시간 | 관련 이슈 |
|---|------|----------|----------|
| 1 | Spring Security RBAC 활성화 — SecurityConfig 주석 해제 + 테스트 | 2h | C-1 |
| 2 | AuthController DB 연동 — users 테이블 + BCrypt 검증 | 4h | C-2 |
| 3 | JWT Secret 환경변수화 | 0.5h | C-3 |
| 4 | CORS 정책 제한 (허용 도메인 설정) | 0.5h | C-4 |
| 5 | DB 스키마 통일 — init.sql과 JPA 엔티티 정합성 확보 | 3h | H-3 |
| 6 | `logic.py` 레거시 코드 삭제 | 0.5h | M-2 |

### 📌 단기 (Sprint 2 — 기능 완성)

| # | 작업 | 예상 시간 | 관련 이슈 |
|---|------|----------|----------|
| 7 | MQTT Listener 구현 (terra-sense) | 6h | H-1 |
| 8 | InfluxDB Writer 구현 (terra-sense) | 4h | H-2 |
| 9 | `terra.control.command` 소비자 구현 | 4h | H-4 |
| 10 | SafetyValidator Layer 4 실제 디바이스 상태 연동 | 6h | H-5 |
| 11 | Dashboard 페이지네이션 추가 | 2h | M-3 |

### 🗓️ 중기 (Sprint 3-4 — 품질 & 운영)

| # | 작업 | 예상 시간 | 관련 이슈 |
|---|------|----------|----------|
| 12 | 단위 테스트 작성 — SafetyValidator, KafkaConsumer, LocalAnalyzer | 16h | M-1 |
| 13 | CI/CD 파이프라인 (GitHub Actions) | 8h | M-4 |
| 14 | `ddl-auto` → Flyway/Liquibase 마이그레이션 전환 | 4h | M-5 |
| 15 | Phase 2.C: Edge Reflex 설계 + 구현 | 16h | Roadmap |
| 16 | Circuit Breaker (Gateway) | 4h | — |
| 17 | Mosquitto 인증 설정 | 2h | C-5 |

---

## 6. 파일/디렉토리 맵

```
terraneuron-smartfarm-platform/
│
├── docs/                              # 📖 문서 (현재 디렉토리)
│   ├── PROJECT_STATUS.md              # ← 이 파일 (프로젝트 현황)
│   ├── API_REFERENCE.md               # 전체 API 레퍼런스
│   ├── DEVELOPMENT_GUIDE.md           # 개발 환경 셋업 + 코딩 가이드
│   ├── ACTION_PROTOCOL.md             # CloudEvents v1.0 Action Protocol 스펙
│   ├── ANDERCORE_FIT_ARCHITECTURE.md  # 아키텍처 내러티브 (Bilingual)
│   ├── DEPLOYMENT.md                  # 배포 가이드 (로컬/클라우드/K8s)
│   └── TROUBLESHOOTING.md            # 트러블슈팅 가이드
│
├── services/
│   ├── terra-gateway/                 # API Gateway (Java/Spring Cloud Gateway)
│   │   └── src/main/java/com/terraneuron/gateway/
│   │       └── GatewayApplication.java
│   │
│   ├── terra-sense/                   # IoT 수집 (Java/Spring Boot)
│   │   └── src/main/java/com/terraneuron/sense/
│   │       ├── controller/IngestController.java
│   │       ├── model/SensorData.java
│   │       └── service/KafkaProducerService.java
│   │
│   ├── terra-cortex/                  # AI 엔진 (Python/FastAPI)
│   │   ├── src/
│   │   │   ├── main.py               # 진입점 + Kafka consumer/producer
│   │   │   ├── local_analyzer.py     # Stage 1: 규칙 기반 분석
│   │   │   ├── cloud_advisor.py      # Stage 2: LLM 호출
│   │   │   ├── rag_advisor.py        # Stage 3: RAG 검색
│   │   │   ├── cloudevents_models.py # CloudEvents 모델
│   │   │   ├── models.py             # 데이터 모델
│   │   │   ├── ingest_knowledge.py   # KB 임포트 도구
│   │   │   └── logic.py              # ⚠️ 레거시 (삭제 대상)
│   │   └── data/
│   │       ├── chroma_db/            # ChromaDB 벡터 저장소
│   │       └── knowledge_base/       # RAG 지식베이스 문서
│   │
│   └── terra-ops/                     # 운영 관리 (Java/Spring Boot + JPA)
│       └── src/main/java/com/terraneuron/ops/
│           ├── controller/
│           │   ├── DashboardController.java
│           │   ├── ActionController.java
│           │   └── AuthController.java
│           ├── entity/
│           │   ├── Insight.java
│           │   ├── ActionPlan.java
│           │   ├── AuditLog.java
│           │   └── Sensor.java
│           ├── repository/
│           ├── service/
│           │   ├── KafkaConsumerService.java
│           │   ├── ActionPlanService.java
│           │   ├── AuditService.java
│           │   └── safety/SafetyValidator.java
│           └── security/
│               ├── JwtTokenProvider.java
│               ├── JwtAuthenticationFilter.java
│               └── SecurityConfig.java
│
├── infra/                             # 인프라 설정
│   ├── mysql/init.sql                # DB 초기화 스크립트
│   ├── mosquitto/mosquitto.conf      # MQTT 브로커
│   ├── prometheus/prometheus.yml     # 메트릭 수집
│   ├── grafana/                      # 대시보드 + 데이터소스
│   ├── kafka/README.md
│   └── influxdb/README.md
│
├── tests/                             # E2E 테스트
│   ├── simulation.py                 # 메인 테스트 (HTML 리포트 생성)
│   └── neural-flow-test.py           # 간단 E2E 흐름 테스트
│
├── tools/
│   └── sensor-simulator.py           # 센서 시뮬레이터
│
├── docker-compose.yml                # 전체 스택 오케스트레이션
├── ROADMAP.md                        # 로드맵
├── README.md                         # 프로젝트 소개
├── QUICKSTART.md                     # 빠른 시작
├── PROJECT_SUMMARY.md                # 프로젝트 요약
├── CONTRIBUTING.md                   # 기여 가이드
└── OLLAMA_SETUP.md                   # 로컬 LLM 설정
```

---

## 📌 읽기 순서 (Onboarding Path)

새로 합류하는 개발자를 위한 권장 읽기 순서:

1. **이 파일** (`PROJECT_STATUS.md`) — 현황 파악
2. `DEVELOPMENT_GUIDE.md` — 로컬 환경 셋업 & 실행
3. `API_REFERENCE.md` — 전체 API 엔드포인트 참조
4. `ACTION_PROTOCOL.md` — CloudEvents 프로토콜 이해
5. `ANDERCORE_FIT_ARCHITECTURE.md` — 아키텍처 설계 철학
6. `DEPLOYMENT.md` — 배포 방법
7. `TROUBLESHOOTING.md` — 문제 해결

---

*이 문서는 프로젝트 상태가 변경될 때마다 업데이트되어야 합니다.*
