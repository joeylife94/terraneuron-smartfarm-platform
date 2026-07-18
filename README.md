# 🌿 TerraNeuron Smart Farm Platform

![Java](https://img.shields.io/badge/Java-17+-ED8B00?style=flat&logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2-6DB33F?style=flat&logo=spring-boot&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat&logo=fastapi&logoColor=white)
![Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5-231F20?style=flat&logo=apache-kafka&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Validation](https://img.shields.io/badge/E2E%20Validated-100%25%20Success-28a745?style=flat&logo=checkmarx&logoColor=white)
![Security](https://img.shields.io/badge/JWT%20Auth-Implemented-blueviolet?style=flat&logo=jsonwebtokens&logoColor=white)
![CloudEvents](https://img.shields.io/badge/CloudEvents-v1.0-orange?style=flat&logo=cloudfoundry&logoColor=white)

**신경망처럼 연결된 지능형 스마트팜 MSA 플랫폼**

> **🎯 Architecture Prototype — Demonstration-Ready**
>
> An **event-driven microservices platform** demonstrating production-grade architecture patterns: Kafka event streaming, Spring Boot/FastAPI polyglot stack, Hybrid AI with RAG, CloudEvents v1.0 protocol, 4-layer safety validation, and human-approved action planning.
>
> **Current State:** Core E2E pipeline is functional (HTTP → Kafka → AI → MySQL). Architecture and design are production-grade. Security enforcement, comprehensive test coverage, and cloud deployment infrastructure are planned for Phase 4.
>
> **For detailed status:** See [AUDIT_REPORT.md](AUDIT_REPORT.md) for implementation gaps, verified features, and upgrade roadmap.

---

## 📜 Version History

| Version | Date | Milestone |
|---------|------|----------|
| v2.1.0 | 2026-01-31 | Phase 2.A & 3 Complete: CloudEvents, Safety Validation, JWT Auth |
| v2.0.0 | 2025-12-09 | Phase 1 Complete: E2E Pipeline, Hybrid AI, RAG System |
| v1.0.0 | 2025-11-15 | Initial MSA Architecture with Kafka Event Backbone |

---

## 🧠 아키텍처 개요

TerraNeuron은 인간의 신경계를 모방한 3개의 마이크로서비스로 구성됩니다:

```mermaid
graph TD
    subgraph Edge["IoT Edge Layer"]
        Sensor[🌱 IoT Sensor] -->|MQTT/HTTP| Mosquitto[Mosquitto Broker]
    end

    subgraph Core["TerraNeuron Microservices"]
        Mosquitto -->|Raw Data| Sense[📡 terra-sense]
        Sense -->|Push| Kafka1[(Kafka: raw-sensor-data)]
        Kafka1 -->|Consume| Cortex[🧠 terra-cortex]
        Cortex -->|AI Inference| Kafka2[(Kafka: processed-insights)]
        Kafka2 -->|Consume| Ops[🎮 terra-ops]
    end

    subgraph Data["Data Layer - Persistence"]
        Sense -->|Write| Influx[(InfluxDB)]
        Ops -->|Read/Write| MySQL[(MySQL)]
    end

    Ops -->|API| Dash[📊 User Dashboard]
```

### 🔬 서비스 구성

#### 1. **terra-sense** (감각 신경 - IoT Ingestion)
- **기술**: Java 17+, Spring Boot 3
- **역할**: IoT 센서 데이터 수집 (MQTT/HTTP)
- **출력**: Kafka Topic `raw-sensor-data`

#### 2. **terra-cortex** (대뇌 피질 - AI Brain)
- **기술**: Python 3.10+, FastAPI, Hybrid AI (Local Edge + Cloud LLM) + RAG
- **역할**: 3단계 지능형 분석 시스템
  - **Stage 1**: Local Edge Analyzer (규칙 기반, <1ms, 무료)
  - **Stage 2**: Cloud LLM Advisor (ANOMALY 전용, 상세 권장사항)
  - **Stage 3**: RAG Knowledge Base (농업 지식 기반 조언 제공)
- **입력**: Kafka Topic `raw-sensor-data`
- **출력**: Kafka Topic `processed-insights`
- **AI 엔진**: OpenAI API 또는 Ollama (Local LLM) 지원
- **RAG**: ChromaDB 벡터 DB + 농업 전문 지식베이스

#### 3. **terra-ops** (운영 통제 - Farm Management)
- **기술**: Java 17+, Spring Boot 3, MySQL JPA, Spring Security
- **역할**: 비즈니스 로직 처리, Action Plan 관리, Dashboard API 제공
- **입력**: Kafka Topic `processed-insights`, `action-plans`
- **출력**: Kafka Topic `terra.control.command`
- **Phase 2.A 신규 기능**:
  - Action Plan 관리 (생성/승인/거부/실행)
  - 4단계 Safety Validation (논리/컨텍스트/권한/디바이스)
  - Audit Logging (FarmOS Log 호환)
  - JWT 인증 시스템

## 🚀 빠른 시작

### 전체 시스템 실행
```bash
docker-compose up -d
```

### 개별 서비스 개발
```bash
# terra-sense (Java)
cd services/terra-sense
./gradlew bootRun

# terra-cortex (Python)
cd services/terra-cortex
pip install -r requirements.txt
uvicorn src.main:app --reload

# terra-ops (Java)
cd services/terra-ops
./gradlew bootRun
```

## 📚 API Documentation

시스템 실행 후 아래 주소에서 대화형 API 문서를 확인할 수 있습니다:

| 서비스 | Swagger/Docs URL | 설명 |
|--------|------------------|------|
| **terra-gateway** | http://localhost:8000 | API Gateway with Rate Limiting |
| **terra-sense** | http://localhost:8081/actuator/health | IoT Ingestion API |
| **terra-cortex** | http://localhost:8082/docs | AI Engine & RAG API |
| **terra-ops** | http://localhost:8083/swagger-ui.html | Business & Dashboard API |

### API 예시

**센서 데이터 전송:**
```bash
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "sensor-001",
    "sensorType": "temperature",
    "value": 25.5,
    "unit": "°C",
    "farmId": "farm-A",
    "timestamp": "2025-12-08T10:30:00Z"
  }'
```

**Dashboard 조회:**
```bash
curl http://localhost:8080/api/v1/dashboard/summary
```

## 📦 인프라 구성

- **Kafka + Zookeeper**: 비동기 메시지 브로커
- **MySQL**: terra-ops 관계형 데이터
- **InfluxDB**: terra-sense 시계열 센서 데이터
- **Mosquitto**: MQTT 브로커 (IoT 디바이스 연동)
- **Prometheus + Grafana**: 모니터링 및 메트릭 수집
- **Redis**: API Gateway Rate Limiting
- **API Gateway (terra-gateway)**: 통합 엔드포인트 & 보안

## 🎯 주요 기능

### 🛡️ Action Protocol (Phase 2.A) ✅ IMPLEMENTED
- **CloudEvents v1.0**: 표준 이벤트 형식 (`terra.<service>.<category>.<action>`)
- **Safety Validators**: 4층 검증 (Logical, Context, Permission, Device)
- **Distributed Tracing**: 필수 `trace_id` 전파 (Kafka 헤더 포함)
- **Audit Logging**: 모든 액션 라이프사이클 기록 (FarmOS Log 호환)
- **FarmOS Compatible**: Asset/Log/Plan 표준 매핑
- **Action Plan API**:
  - `GET /api/actions/pending` - 대기중인 액션 조회
  - `POST /api/actions/{id}/approve` - 액션 승인 (Safety Validation 후 실행)
  - `POST /api/actions/{id}/reject` - 액션 거부
  - `GET /api/actions/{id}/audit` - 감사 이력 조회

### 🔐 보안 (Phase 3) ✅ IMPLEMENTED
- **JWT Authentication**: 토큰 기반 인증 시스템
  - Access Token (24시간) + Refresh Token (7일)
  - `POST /api/auth/login` - 로그인
  - `POST /api/auth/refresh` - 토큰 갱신
  - `GET /api/auth/validate` - 토큰 검증
- **Role-based Access Control**: ADMIN, OPERATOR, VIEWER 역할
- **API Gateway**: 모든 요청을 단일 진입점으로 통합
- **Rate Limiting**: Redis 기반 요청 제한
- **CORS 설정**: 크로스 오리진 요청 관리

### 📊 모니터링
- **Prometheus**: 실시간 메트릭 수집
- **Grafana**: 시각화 대시보드
  - 서비스 헬스 상태
  - Kafka 메시지 처리율
  - API 응답 시간
  - AI 추론 성능

### 🔄 CI/CD
- **GitHub Actions**: 자동 빌드 & 테스트
- **Docker 이미지**: 자동 빌드 & 레지스트리 푸시
- **보안 스캔**: Trivy 전체 SARIF 보고 + 수정 가능한 HIGH/CRITICAL 취약점 CI 차단
  - 운영 정책과 한계: [`docs/SECURITY_SCANNING.md`](docs/SECURITY_SCANNING.md)

### 🧪 테스트 도구
- **E2E 테스트**: 전체 파이프라인 검증
- **센서 시뮬레이터**: 다양한 시나리오 테스트
  - 정상 모드
  - 이상 탐지 시나리오
- **HTML Test Reporter**: 전문가급 테스트 보고서 생성
  - AI 권장사항 추적 (LLM 응답 하이라이트)
  - 성능 메트릭 (지연시간, 성공률)
  - 색상 코딩 (녹색=정상, 빨강=이상, 보라=AI 권장)
  - 7가지 핵심 지표 대시보드
  - 부하 테스트

## 🔗 서비스 엔드포인트

| 서비스 | 포트 | 설명 | URL |
|--------|------|------|-----|
| **API Gateway** | 8000 | 통합 진입점 | http://localhost:8000 |
| **Terra-Sense** | 8081 | IoT 데이터 수집 | http://localhost:8081 |
| **Terra-Cortex** | 8082 | AI 분석 엔진 | http://localhost:8082 |
| **Terra-Ops** | 8080 | 비즈니스 API | http://localhost:8080 |
| **Grafana** | 3000 | 모니터링 대시보드 | http://localhost:3000 |
| **Prometheus** | 9090 | 메트릭 수집기 | http://localhost:9090 |

## 🧪 테스트

### E2E 통합 테스트
```bash
cd tests
python neural-flow-test.py
```

### 센서 데이터 시뮬레이터
```bash
# 정상 데이터 생성
python tools/sensor-simulator.py --mode normal --duration 60

# 이상 시나리오 (폭염)
python tools/sensor-simulator.py --mode anomaly --scenario heat_wave

# 혼합 모드 (현실적)
python tools/sensor-simulator.py --mode mixed --duration 300

# 부하 테스트
python tools/sensor-simulator.py --mode stress --rate 1000
```


## 📁 프로젝트 구조

```
terraneuron-smartfarm/
├── .github/
│   └── workflows/          # CI/CD 파이프라인
├── services/               # 4대 마이크로서비스
│   ├── terra-gateway/      # API Gateway
│   ├── terra-sense/        # IoT 수집
│   ├── terra-cortex/       # AI 분석
│   └── terra-ops/          # 비즈니스 로직
├── infra/                  # 인프라 설정
│   ├── kafka/
│   ├── mysql/
│   ├── prometheus/
│   └── grafana/
├── tools/                  # 개발/테스트 도구
│   └── sensor-simulator.py
├── tests/                  # E2E 통합 테스트
└── docs/                   # 상세 문서
    ├── DEPLOYMENT.md
    └── TROUBLESHOOTING.md
```

## 📚 문서

- **[빠른 시작 가이드](QUICKSTART.md)** - 1분 안에 실행하기
- **[기여 가이드](CONTRIBUTING.md)** - 프로젝트 기여 방법
- **[배포 가이드](docs/DEPLOYMENT.md)** - 프로덕션 배포
- **[트러블슈팅](docs/TROUBLESHOOTING.md)** - 문제 해결
- **[API 문서](http://localhost:8080/swagger-ui.html)** - Swagger UI

## 🗺️ Roadmap

### ✅ Completed Phases
- [x] **Phase 1: Genesis** - 모노레포 구조 및 MSA 기본 통신 구축 (Kafka)
- [x] **Phase 1.5: Infrastructure** - 모니터링, CI/CD, API Gateway 추가
- [x] **Phase 2.A: Action Loop** - CloudEvents v1.0, 4-Layer Safety Validation, trace_id 전파 ✨ NEW
- [x] **Phase 2.B: Hybrid AI** - Local Edge + Cloud LLM + RAG Knowledge Base
- [x] **Phase 3: Security** - JWT Authentication, Role-based Access Control ✨ NEW

### 🚧 In Progress
- [ ] **Phase 2.C: Edge Reflex** - Local fail-safe mechanism (Internet outage safety)

### 🔮 Future Phases
- [ ] **Phase 4: Expansion** - 실제 IoT 하드웨어(Raspberry Pi + Soil Sensor) 연동
- [ ] **Phase 5: Evolution** - K3s/Docker Swarm 배포 및 모바일 앱 연동

> 📋 상세 로드맵은 [ROADMAP.md](ROADMAP.md) 참조

## 🤝 기여하기

기여를 환영합니다! [CONTRIBUTING.md](CONTRIBUTING.md)를 참고해주세요.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

MIT License

## 👥 팀

- **Architecture**: Microservices Architecture (MSA)
- **IoT Integration**: MQTT, HTTP REST API
- **AI/ML**: Anomaly Detection, PyTorch
- **Infrastructure**: Docker, Kafka, Prometheus/Grafana

## 🌟 Star History

이 프로젝트가 도움이 되셨다면 ⭐️ 를 눌러주세요!

---

**Built with ❤️ by TerraNeuron Team**
