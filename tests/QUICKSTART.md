# 🚀 TerraNeuron Simulation Quick Start

**5분 안에 전체 파이프라인 테스트하기**

---

## Step 1: 전체 스택 시작 (2분)

```bash
# 프로젝트 루트 디렉토리로 이동
cd terraneuron-smartfarm-platform

# Docker Compose로 모든 서비스 시작
docker-compose up -d

# 서비스 시작 확인 (30초 대기)
sleep 30
docker-compose ps
```

**예상 출력:** 13개의 서비스가 모두 `Up` 상태

---

## Step 2: Python 의존성 설치 (30초)

```bash
pip install requests
```

---

## Step 3: 시뮬레이션 실행 (1분)

### 기본 테스트 (10개 요청)
```bash
python tests/simulation.py
```

### 빠른 부하 테스트 (50개 요청)
```bash
python tests/simulation.py --count 50 --interval 0.5
```

### 이상 탐지 테스트 (이상 데이터만)
```bash
python tests/simulation.py --mode anomaly --count 20
```

---

## Step 4: 결과 확인 (1분)

### 대시보드 API로 인사이트 확인
```bash
# 모든 인사이트 조회
curl http://localhost:8083/api/v1/dashboard/insights | jq

# 요약 통계
curl http://localhost:8083/api/v1/dashboard/summary | jq
```

### MySQL 데이터베이스 직접 확인
```bash
docker exec -it mysql mysql -u terra -pterra2025 -e \
  "SELECT id, farm_id, status, message FROM terra_db.insights ORDER BY timestamp DESC LIMIT 5"
```

---

## 💡 주요 명령어 요약

| 작업 | 명령어 |
|------|--------|
| **시작** | `docker-compose up -d` |
| **중지** | `docker-compose down` |
| **로그 보기** | `docker-compose logs -f terra-sense` |
| **시뮬레이션 실행** | `python tests/simulation.py` |
| **상태 확인** | `docker-compose ps` |
| **인사이트 조회** | `curl http://localhost:8083/api/v1/dashboard/insights` |

---

## 🔍 서비스 URL

- **terra-sense (IoT):** http://localhost:8081
- **terra-cortex (AI):** http://localhost:8082
- **terra-ops (Dashboard):** http://localhost:8083
- **Grafana (모니터링):** http://localhost:3000 (admin/admin)
- **Prometheus (메트릭):** http://localhost:9090

---

## ❓ 문제 해결

### 서비스가 시작되지 않으면?
```bash
docker-compose logs <service-name>
```

### 시뮬레이션이 연결 실패?
```bash
# 서비스 상태 확인
curl http://localhost:8081/api/v1/health
curl http://localhost:8082/health
curl http://localhost:8083/api/v1/health
```

### 데이터가 보이지 않으면?
```bash
# 로그 확인
docker-compose logs -f terra-cortex
docker-compose logs -f terra-ops

# Kafka 메시지 확인
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic processed-insights \
  --from-beginning \
  --max-messages 5
```

---

**전체 가이드:** `tests/README.md` 참조

**Happy Testing! 🌾🧠**
