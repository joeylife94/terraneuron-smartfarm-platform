# 🌿 TerraNeuron 빠른 시작 가이드

## 📋 사전 요구사항

- Docker & Docker Compose
- Java 17+ (로컬 개발시)
- Python 3.10+ (로컬 개발시)
- Git

## 🚀 1분 안에 실행하기

### 1단계: 전체 시스템 시작
```bash
docker-compose up -d
```

### 2단계: 서비스 상태 확인 (30초 대기)
```bash
docker-compose ps
```

### 3단계: E2E 테스트 실행
```bash
pip install requests
python tests/neural-flow-test.py
```

## 🔗 서비스 접속 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| **terra-sense** | http://localhost:8081 | IoT 센서 데이터 수집 API |
| **terra-cortex** | http://localhost:8082 | AI 분석 엔진 API |
| **terra-ops** | http://localhost:8080 | Dashboard & 관리 API |
| **Swagger UI** | http://localhost:8080/swagger-ui.html | API 문서 |
| **Kafka UI** | localhost:9092 | Kafka 브로커 |
| **MySQL** | localhost:3306 | 데이터베이스 (terra/terra2025) |
| **InfluxDB** | http://localhost:8086 | 시계열 데이터베이스 |
| **MQTT Broker** | localhost:1883 | IoT 디바이스 연결 |

## 📊 테스트용 API 호출

### 센서 데이터 전송
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

### Dashboard 조회
```bash
curl http://localhost:8080/api/v1/dashboard/summary
```

### 인사이트 조회
```bash
curl http://localhost:8080/api/v1/insights
```

## 🔍 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f terra-sense
docker-compose logs -f terra-cortex
docker-compose logs -f terra-ops
```

## 🛑 시스템 종료

```bash
docker-compose down

# 데이터까지 삭제
docker-compose down -v
```

## 🔧 개발 모드

### terra-sense (Java)
```bash
cd services/terra-sense
./gradlew bootRun
```

### terra-cortex (Python)
```bash
cd services/terra-cortex
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8082
```

### terra-ops (Java)
```bash
cd services/terra-ops
./gradlew bootRun
```

## 📁 디렉토리 구조
```
terraneuron-smartfarm-platform/
├── services/
│   ├── terra-sense/      # IoT 데이터 수집 (Java)
│   ├── terra-cortex/     # AI 분석 엔진 (Python)
│   └── terra-ops/        # 운영 관리 (Java)
├── infra/                # 인프라 설정
├── tests/                # E2E 테스트
└── docker-compose.yml    # 전체 시스템 오케스트레이션
```

## 🆘 트러블슈팅

### Kafka 연결 오류
```bash
docker exec -it terraneuron-kafka kafka-topics --list --bootstrap-server localhost:9092
```

### MySQL 연결 확인
```bash
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_ops
```

### 포트 충돌
```bash
# 사용 중인 포트 확인
netstat -an | findstr "8080 8081 8082 9092 3306"
```

## 📚 추가 문서

- [아키텍처 상세](README.md)
- [테스트 가이드](tests/README.md)
- [인프라 설정](infra/)
