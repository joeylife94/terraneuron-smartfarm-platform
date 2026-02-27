# 🛠️ TerraNeuron 개발 가이드 (Development Guide)

> **📅 Last Updated:** 2026-02-27  
> **Version:** v2.1.0  
> **Purpose:** 로컬 개발 환경 세팅부터 코드 수정, 테스트, 디버깅까지 — 이 문서 하나로 바로 개발 시작

---

## 📋 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [환경 세팅](#2-환경-세팅)
3. [서비스별 로컬 실행](#3-서비스별-로컬-실행)
4. [E2E 테스트 실행](#4-e2e-테스트-실행)
5. [개발 워크플로우](#5-개발-워크플로우)
6. [코드 구조 & 컨벤션](#6-코드-구조--컨벤션)
7. [디버깅 가이드](#7-디버깅-가이드)
8. [자주 묻는 질문](#8-자주-묻는-질문)

---

## 1. 사전 요구사항

### 필수 소프트웨어

| 소프트웨어 | 최소 버전 | 용도 |
|-----------|----------|------|
| **Docker Desktop** | 24.0+ | 전체 인프라 실행 |
| **Docker Compose** | 2.0+ | 멀티 컨테이너 오케스트레이션 |
| **Java JDK** | 17 | terra-gateway, terra-sense, terra-ops |
| **Python** | 3.10+ | terra-cortex |
| **Git** | 최신 | 소스 관리 |

### 선택 소프트웨어

| 소프트웨어 | 용도 |
|-----------|------|
| **IntelliJ IDEA / VS Code** | IDE |
| **Postman / Insomnia** | API 테스트 |
| **Ollama** | 로컬 LLM (OpenAI 대체) |
| **DBeaver** | MySQL GUI 클라이언트 |

### 시스템 요구사항

- **CPU:** 4 cores 이상
- **RAM:** 8GB 이상 (Docker 전체 스택 실행 시)
- **Disk:** 10GB+ 여유 공간

---

## 2. 환경 세팅

### 2.1 저장소 클론

```bash
git clone https://github.com/joeylife94/terraneuron-smartfarm-platform.git
cd terraneuron-smartfarm-platform
```

### 2.2 전체 스택 실행 (Docker Compose)

가장 빠른 시작 방법. 모든 서비스 + 인프라를 한 번에 실행합니다.

```bash
# .env 파일 생성 (최초 1회)
cat > .env << 'EOF'
# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092

# MySQL
MYSQL_ROOT_PASSWORD=terra2025
MYSQL_DATABASE=terra_ops
MYSQL_USER=terra
MYSQL_PASSWORD=terra2025

# InfluxDB
INFLUXDB_ADMIN_USER=admin
INFLUXDB_ADMIN_PASSWORD=terra2025
INFLUXDB_ADMIN_TOKEN=terra-token-2025

# Grafana
GF_SECURITY_ADMIN_PASSWORD=terra2025

# AI (OpenAI 사용 시)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo

# AI (Ollama 사용 시 — OpenAI 대신)
# OPENAI_API_BASE=http://host.docker.internal:11434/v1
# OPENAI_API_KEY=ollama
# OPENAI_MODEL=llama3.1
EOF
```

```bash
# 전체 스택 실행
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 실시간 보기
docker-compose logs -f
```

### 2.3 헬스 체크

```bash
# terra-sense
curl http://localhost:8081/api/v1/ingest/health

# terra-cortex
curl http://localhost:8082/health

# terra-ops
curl http://localhost:8083/api/v1/health

# Gateway
curl http://localhost:8000/api/ops/api/v1/health
```

### 2.4 주요 웹 UI

| 서비스 | URL | 계정 |
|--------|-----|------|
| **Grafana** | http://localhost:3000 | admin / terra2025 |
| **Prometheus** | http://localhost:9090 | — |
| **Swagger (terra-ops)** | http://localhost:8083/swagger-ui.html | — |

---

## 3. 서비스별 로컬 실행

> Docker Compose 전체 실행 대신, 특정 서비스만 로컬에서 개발/디버깅할 때 사용합니다.

### 3.1 인프라만 실행 (공통)

특정 서비스를 IDE에서 직접 실행할 경우, 인프라(Kafka, MySQL 등)는 Docker로 띄워야 합니다.

```bash
# 인프라만 실행 (서비스 제외)
docker-compose up -d kafka zookeeper mysql redis prometheus grafana
```

### 3.2 terra-sense (Java)

```bash
cd services/terra-sense

# Gradle 빌드
./gradlew build -x test

# 실행 (로컬 Kafka 연결)
./gradlew bootRun --args='--spring.kafka.bootstrap-servers=localhost:9092'
```

**또는 IntelliJ에서:**
1. `services/terra-sense` 디렉토리를 프로젝트로 열기
2. `application.properties`에서 `kafka.bootstrap-servers=localhost:9092`로 변경
3. Run `TerraSenseApplication.main()`

### 3.3 terra-cortex (Python)

```bash
cd services/terra-cortex

# 가상환경 생성
python -m venv venv

# 활성화 (Windows)
.\venv\Scripts\activate

# 활성화 (Linux/Mac)
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
$env:OPENAI_API_KEY="sk-your-key-here"
$env:OPENAI_MODEL="gpt-3.5-turbo"

# 실행
uvicorn src.main:app --host 0.0.0.0 --port 8082 --reload
```

**RAG 지식베이스 구축 (최초 1회):**
```bash
python src/ingest_knowledge.py
```

### 3.4 terra-ops (Java)

```bash
cd services/terra-ops

# Gradle 빌드
./gradlew build -x test

# 실행 (로컬 MySQL + Kafka)
./gradlew bootRun --args='--spring.datasource.url=jdbc:mysql://localhost:3306/terra_ops --spring.kafka.bootstrap-servers=localhost:9092'
```

### 3.5 terra-gateway (Java)

```bash
cd services/terra-gateway

# 빌드 & 실행
./gradlew bootRun --args='--spring.data.redis.host=localhost'
```

---

## 4. E2E 테스트 실행

### 4.1 전제 조건

- Docker Compose 전체 스택이 실행 중이어야 함
- 모든 서비스 헬스 체크 통과

### 4.2 시뮬레이션 테스트 (HTML 리포트 생성)

```bash
cd tests

# 기본 실행 (normal + anomaly 시뮬레이션)
python simulation.py

# 특정 모드
python simulation.py --mode normal     # 정상 데이터만
python simulation.py --mode anomaly    # 이상 데이터만
python simulation.py --mode mixed      # 혼합

# 리포트는 프로젝트 루트에 test_report_YYYYMMDD_HHMMSS.html로 생성
```

### 4.3 간단 E2E 흐름 테스트

```bash
cd tests
python neural-flow-test.py
```

### 4.4 센서 시뮬레이터 (연속 데이터 생성)

```bash
cd tools

# 기본 실행 (normal 모드)
python sensor-simulator.py

# 이상 시나리오
python sensor-simulator.py --mode anomaly

# 스트레스 테스트
python sensor-simulator.py --mode stress
```

### 4.5 수동 API 테스트 (빠른 검증)

```bash
# 1. 센서 데이터 전송
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "temp-sensor-01",
    "sensorType": "temperature",
    "value": 42.5,
    "unit": "celsius",
    "farmId": "farm-001"
  }'

# 2. 10초 대기 (Kafka → AI 분석 → DB 저장)
sleep 10

# 3. 인사이트 확인
curl http://localhost:8083/api/v1/dashboard/insights | python -m json.tool

# 4. 대기 중인 액션 플랜 확인 (이상 데이터 전송 시)
curl http://localhost:8083/api/actions/pending | python -m json.tool

# 5. 액션 플랜 승인 (planId를 위에서 확인한 값으로 교체)
curl -X POST http://localhost:8083/api/actions/plan-12345/approve \
  -H "Content-Type: application/json" \
  -d '{"approvedBy": "admin", "approvalNote": "test"}'
```

---

## 5. 개발 워크플로우

### 5.1 브랜치 전략

```
main             # 안정 버전
├── develop      # 개발 통합 브랜치
│   ├── feature/ISSUE-01-mqtt-listener     # 기능 브랜치
│   ├── feature/ISSUE-02-security-rbac     # 기능 브랜치
│   └── fix/ISSUE-03-schema-mismatch       # 버그 수정
└── release/v2.2.0  # 릴리즈 준비
```

### 5.2 커밋 메시지 컨벤션

```
feat(terra-sense): implement MQTT listener for IoT devices
fix(terra-ops): resolve schema mismatch between init.sql and JPA entities
docs: update API_REFERENCE.md with new endpoints
refactor(terra-cortex): remove legacy logic.py
test(terra-ops): add unit tests for SafetyValidator
chore: update docker-compose.yml dependencies
```

### 5.3 일반적인 개발 사이클

```
1. 이슈 확인 (docs/PROJECT_STATUS.md의 백로그 참조)
2. feature 브랜치 생성
3. 코드 수정
4. 로컬 빌드 & 확인
5. Docker Compose로 E2E 테스트
6. PR 생성
7. 코드 리뷰
8. develop에 병합
```

---

## 6. 코드 구조 & 컨벤션

### 6.1 Java 서비스 (terra-sense, terra-ops, terra-gateway)

**패키지 구조:**
```
com.terraneuron.<service>/
├── <Service>Application.java     # Spring Boot 메인
├── controller/                   # REST 컨트롤러
├── model/ (또는 entity/)         # 데이터 모델 / JPA 엔티티
├── dto/                          # 데이터 전송 객체
├── repository/                   # Spring Data JPA 레포지토리
├── service/                      # 비즈니스 로직
├── security/                     # 보안 (JWT, Filter, Config)
└── config/                       # 설정 클래스
```

**스택:**
- Java 17, Spring Boot 3.2
- Gradle (빌드)
- Spring Data JPA + Hibernate (terra-ops)
- Spring Kafka
- Lombok (보일러플레이트 축소)
- Micrometer + Prometheus (메트릭)

**설정:** `src/main/resources/application.properties`

### 6.2 Python 서비스 (terra-cortex)

**모듈 구조:**
```
src/
├── main.py                # FastAPI 앱 + Kafka consumer/producer
├── local_analyzer.py      # Stage 1: 규칙 기반 분석
├── cloud_advisor.py       # Stage 2: LLM 호출
├── rag_advisor.py         # Stage 3: RAG 벡터 검색
├── cloudevents_models.py  # CloudEvents 데이터 모델
├── models.py              # Pydantic 데이터 모델
├── ingest_knowledge.py    # KB 임포트 유틸
└── logic.py               # ⚠️ 레거시 (삭제 예정)
```

**스택:**
- Python 3.10, FastAPI 0.109.0
- aiokafka (비동기 Kafka)
- OpenAI SDK 1.7.0
- LangChain 0.1.0 + ChromaDB 0.4.22
- sentence-transformers (임베딩)
- Pydantic (데이터 검증)

### 6.3 인프라 설정 파일

| 파일 | 설명 |
|------|------|
| `docker-compose.yml` | 전체 서비스 + 인프라 정의 |
| `infra/mysql/init.sql` | DB 초기화 (테이블 + 데모 데이터) |
| `infra/mosquitto/mosquitto.conf` | MQTT 브로커 설정 |
| `infra/prometheus/prometheus.yml` | 메트릭 수집 타겟 |
| `infra/grafana/dashboards/*.json` | Grafana 대시보드 |
| `infra/grafana/provisioning/` | Grafana 자동 프로비저닝 |

### 6.4 Kafka 토픽 & CloudEvents

새로운 이벤트 타입을 추가할 때:

1. **타입 네이밍:** `terra.<service>.<category>.<action>` (예: `terra.ops.alert.triggered`)
2. **CloudEvents 필수 필드:** `specversion`, `type`, `source`, `id`, `time`, `datacontenttype`, `data`
3. **`data.trace_id` 필수:** 모든 이벤트에 `trace_id` 전파
4. **상세 스펙:** `docs/ACTION_PROTOCOL.md` 참조

---

## 7. 디버깅 가이드

### 7.1 로그 레벨 변경

**Java 서비스:**
```properties
# application.properties
logging.level.com.terraneuron=DEBUG
logging.level.org.springframework.kafka=DEBUG
logging.level.org.hibernate.SQL=DEBUG
```

**Python (terra-cortex):**
```python
# main.py 상단
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 7.2 Kafka 디버깅

```bash
# 토픽 목록 확인
docker exec -it terraneuron-kafka kafka-topics --list --bootstrap-server localhost:9092

# 토픽 메시지 실시간 모니터링
docker exec -it terraneuron-kafka kafka-console-consumer \
  --topic raw-sensor-data \
  --from-beginning \
  --bootstrap-server localhost:9092

# Consumer Group lag 확인
docker exec -it terraneuron-kafka kafka-consumer-groups \
  --describe --group terra-cortex-group \
  --bootstrap-server localhost:9092
```

### 7.3 MySQL 디버깅

```bash
# MySQL 쉘 접속
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_ops

# 유용한 쿼리
SELECT COUNT(*) FROM insights;
SELECT * FROM insights ORDER BY created_at DESC LIMIT 5;
SELECT * FROM action_plans WHERE status = 'PENDING';
SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;
SHOW TABLES;
DESCRIBE insights;
```

### 7.4 컨테이너 내부 확인

```bash
# 쉘 접속
docker exec -it terra-cortex sh
docker exec -it terra-ops bash

# 네트워크 연결 테스트
docker exec terra-ops ping kafka
docker exec terra-ops nc -zv mysql 3306

# 메모리/CPU 확인
docker stats
```

### 7.5 흔한 문제 & 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| 센서 데이터 전송 후 인사이트 안 뜸 | terra-cortex Kafka 소비 안 됨 | `docker-compose logs terra-cortex` 확인 |
| terra-ops 계속 재시작 | MySQL 아직 준비 안 됨 | MySQL 완전 기동 후 재시작 `docker-compose restart terra-ops` |
| LLM 추천이 비어있음 | OpenAI API 키 미설정 / Ollama 미설치 | `.env` 확인 또는 `OLLAMA_SETUP.md` 참조 |
| Rate limit 429 에러 | Gateway rate limiter 동작 | Redis 상태 확인 또는 limit 조정 |
| JPA 엔티티 오류 | init.sql과 JPA 설계 충돌 | `docker-compose down -v` 후 재시작 |

---

## 8. 자주 묻는 질문

### Q: OpenAI 없이 개발할 수 있나요?

**A:** 네. Ollama (로컬 LLM)로 대체 가능합니다. `OLLAMA_SETUP.md` 참조.  
또한 terra-cortex의 Stage 2 (LLM)는 ANOMALY 시에만 호출되므로, 정상 범위 데이터로 테스트하면 LLM 없이도 전체 파이프라인이 동작합니다.

### Q: 어떤 서비스부터 수정해야 하나요?

**A:** `docs/PROJECT_STATUS.md`의 **우선순위 백로그**를 참조하세요. 현재 최우선은:
1. Spring Security RBAC 활성화 (terra-ops)
2. AuthController DB 연동 (terra-ops)
3. DB 스키마 통일 (init.sql + JPA)

### Q: 단위 테스트는 어떻게 작성하나요?

**A:** 현재 테스트 코드가 없습니다. 아래 경로에 추가하면 됩니다:
- Java: `services/<service>/src/test/java/com/terraneuron/...`
- Python: `services/terra-cortex/tests/`

Java 테스트 의존성 (`spring-boot-starter-test`, `spring-kafka-test`, `H2`)은 이미 `build.gradle`에 포함되어 있습니다.

### Q: Grafana 대시보드는 어떻게 수정하나요?

**A:** `infra/grafana/dashboards/terraneuron-overview.json`을 직접 편집하거나, Grafana UI에서 수정 후 JSON을 내보내기(Export)하여 덮어씁니다.

### Q: 새로운 센서 타입을 추가하려면?

**A:**
1. `terra-cortex/src/local_analyzer.py` — 임계치 규칙 추가
2. `terra-cortex/src/main.py` — Action Plan 생성 시 디바이스 매핑 추가
3. `infra/mysql/init.sql` — 필요 시 센서 데모 데이터 추가
4. `tools/sensor-simulator.py` — 시뮬레이터에 새 센서 추가

---

## 📚 관련 문서

| 문서 | 내용 |
|------|------|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 프로젝트 현황, 알려진 이슈, 백로그 |
| [API_REFERENCE.md](API_REFERENCE.md) | 전체 API 엔드포인트 레퍼런스 |
| [ACTION_PROTOCOL.md](ACTION_PROTOCOL.md) | CloudEvents 프로토콜 스펙 |
| [ANDERCORE_FIT_ARCHITECTURE.md](ANDERCORE_FIT_ARCHITECTURE.md) | 아키텍처 설계 철학 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 프로덕션 배포 가이드 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 문제 해결 |
| [OLLAMA_SETUP.md](../OLLAMA_SETUP.md) | 로컬 LLM (Ollama) 설정 |

---

*이 문서는 개발 환경이 변경될 때마다 업데이트되어야 합니다.*
