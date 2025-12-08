# TerraNeuron Testing Suite

이 디렉토리는 TerraNeuron Smart Farm Platform의 전체 시스템 통합 테스트 및 시뮬레이션 도구를 포함합니다.

## 📁 포함된 파일

- **`simulation.py`** - 엔드-투-엔드 파이프라인 시뮬레이션 및 HTML 테스트 보고서 생성 (⭐ UPGRADED!)
- **`TEST_REPORTER_README.md`** - HTML 테스트 보고서 상세 가이드 (NEW! 📊)
- **`neural-flow-test.py`** - 데이터 플로우 통합 테스트 (기존)

---

## 🚀 빠른 시작 가이드

### 사전 요구사항

1. **Python 의존성 설치:**
   ```bash
   pip install requests
   ```

2. **전체 스택 시작:**
   ```bash
   # 프로젝트 루트 디렉토리에서
   docker-compose up -d
   
   # 모든 서비스가 안정화될 때까지 대기 (~30초)
   docker-compose ps
   ```

3. **서비스 상태 확인:**
   ```bash
   # terra-sense (IoT 수집)
   curl http://localhost:8081/api/v1/health
   
   # terra-cortex (AI 분석)
   curl http://localhost:8082/health
   
   # terra-ops (대시보드)
   curl http://localhost:8083/api/v1/health
   ```

---

## 🧪 시뮬레이션 스크립트 실행 (NEW!)

### 기본 사용법

```bash
# 프로젝트 루트에서
python tests/simulation.py
```

**기본 동작:**
- 10개의 센서 데이터 포인트 전송
- Mixed 모드 (80% 정상, 20% 이상)
- 요청 간 1초 간격
- 대상: `http://localhost:8081`

### 고급 사용 예시

#### 1. 정상 데이터만 전송
```bash
python tests/simulation.py --mode normal --count 20 --interval 1
```

#### 2. 이상 데이터만 전송 (AI 탐지 테스트)
```bash
python tests/simulation.py --mode anomaly --count 15 --interval 2
```

#### 3. Mixed 모드 + 상세 출력
```bash
python tests/simulation.py --mode mixed --count 50 --verbose
```

#### 4. 부하 테스트 (빠른 생성)
```bash
python tests/simulation.py --count 100 --interval 0.5
```

#### 5. 커스텀 대상 URL
```bash
python tests/simulation.py --url http://192.168.1.100:8081 --count 30
```

### 명령줄 옵션

```bash
python tests/simulation.py --help
```

**사용 가능한 옵션:**
- `--mode {normal|anomaly|mixed}` - 데이터 생성 모드 (기본값: mixed)
- `--count N` - 전송할 요청 수 (기본값: 10)
- `--interval SECONDS` - 요청 간 간격 (기본값: 1.0)
- `--url URL` - terra-sense 서비스 URL (기본값: http://localhost:8081)
- `--verbose` - 상세 출력 활성화 (요청/응답 전체 표시)
- `--report` - **HTML 테스트 보고서 생성** (AI 검증 권장! 📊)
- `--wait-for-insights N` - 인사이트 조회 전 대기 시간 (기본값: 3초)

---

## 📊 HTML 테스트 보고서 (NEW! ⭐)

### 빠른 시작

```bash
# HTML 보고서와 함께 이상 탐지 테스트 실행
python tests/simulation.py --mode anomaly --count 20 --report
```

**생성되는 내용:**
- ✅ 전문가급 HTML 보고서 (예: `test_report_20251208_224817.html`)
- ✅ 7가지 핵심 메트릭 대시보드
- ✅ AI 권장사항 하이라이트 (보라색 박스)
- ✅ 색상 코딩된 결과 (녹색=정상, 빨강=이상)
- ✅ 성능 메트릭 (지연시간, 성공률)
- ✅ 자동으로 브라우저에서 열림

### 보고서 기능

**요약 대시보드 메트릭:**
| 메트릭 | 설명 |
|--------|------|
| **Total Tests** | 전송된 센서 데이터 개수 |
| **Success Rate** | HTTP 200 응답 성공률 (%) |
| **AI Triggered** | Local Analyzer가 탐지한 이상 개수 |
| **AI Recommendations** | LLM 생성 권장사항 개수 |
| **Avg Latency** | 평균 응답 시간 (밀리초) |

**상세 결과 테이블:**
- 타임스탬프, Farm ID, 센서 타입, 측정값
- AI 상태 (NORMAL/ANOMALY 뱃지)
- 🤖 **AI 권장사항** (보라색 그라디언트로 강조)
- 요청 지연시간
- 테스트 결과 (PASS/FAIL)

**색상 코딩:**
- 🟢 녹색 행: 정상 센서 측정값
- 🔴 빨간색 행: 이상 탐지 (AI 트리거됨)
- 🟣 보라색 박스: LLM 생성 권장사항

### HTML 보고서 사용 예시

#### 예시 1: Local AI 검증 (API 키 없이)
```bash
python tests/simulation.py --mode anomaly --count 10 --report

# 결과:
# - AI Status: 10개 ANOMALY 탐지 ✅
# - AI Recommendations: 0 (Cloud Advisor 비활성) ⚠️
# - 보고서: Local Edge Analyzer 동작 확인
```

#### 예시 2: Hybrid AI 전체 파이프라인 검증 (OpenAI 활성)
```bash
# 먼저 .env에 OPENAI_API_KEY 추가
echo "OPENAI_API_KEY=sk-your-key" >> .env
docker-compose up -d terra-cortex

# 테스트 실행
python tests/simulation.py --mode anomaly --count 20 --report --wait-for-insights 5

# 결과:
# - AI Status: 20개 ANOMALY 탐지 ✅
# - AI Recommendations: 20개 LLM 응답 ✅
# - 보고서: 모든 이상에 보라색 권장사항 박스 표시
```

#### 예시 3: Mixed 모드 성능 테스트
```bash
python tests/simulation.py --mode mixed --count 100 --interval 0.5 --report

# 결과:
# - 정상/이상 혼합 데이터
# - 성능 메트릭 분석 (평균 지연시간)
# - AI 트리거 비율 확인
```

### 보고서 위치

```bash
# 자동 생성되는 파일명
test_report_YYYYMMDD_HHMMSS.html

# 예시
test_report_20251208_224817.html
  - 날짜: 2025년 12월 8일
  - 시간: 22:48:17

# 브라우저에서 열기
# - Windows: 자동으로 열림 (또는 더블클릭)
# - Mac: open test_report_*.html
# - Linux: xdg-open test_report_*.html
```

### 상세 가이드

HTML 테스트 보고서의 모든 기능과 사용법은 다음 문서를 참조하세요:

📖 **[TEST_REPORTER_README.md](./TEST_REPORTER_README.md)** - 전체 가이드 (1000+ 줄)
  - AI 검증 워크플로우
  - OpenAI/Ollama 설정 방법
  - 문제 해결 가이드
  - 테스트 전략 및 Best Practices

---

## 📊 출력 이해하기

### 예시 출력

```
╔═══════════════════════════════════════════════════════════╗
║   🌾 TerraNeuron Pipeline Simulation Tool 🧠              ║
║   End-to-End Testing for Smart Farm Microservices        ║
╚═══════════════════════════════════════════════════════════╝

📋 Configuration:
   Mode:           mixed
   Count:          10 requests
   Interval:       1.0 seconds
   Target URL:     http://localhost:8081

🔍 Checking terra-sense health...
✅ terra-sense is healthy (Status: 200)

🚀 Starting simulation: Sending 10 sensor data points...
------------------------------------------------------------
✅ [1/10] temperature      =   25.34 °C    | HTTP 200
✅ [2/10] humidity         =   65.22 %     | HTTP 200
✅ [3/10] temperature      =   38.50 °C    | HTTP 200  <- ANOMALY
------------------------------------------------------------

============================================================
📊 TEST STATISTICS
============================================================
Total Requests:   10
✅ Success:        10 (100.00%)
❌ Failed:         0 (0.00%)

Status Code Distribution:
  200: 10 (100.00%)
============================================================
```

---

## 🔍 파이프라인 검증

시뮬레이션 실행 후 전체 파이프라인을 통한 데이터 흐름 확인:

### 1. terra-sense 로그 확인
```bash
docker-compose logs -f terra-sense
```
**예상:** "Accepted sensor data" 및 "Published to Kafka" 메시지

### 2. terra-cortex 로그 확인
```bash
docker-compose logs -f terra-cortex
```
**예상:** "📥 Received" 및 "📤 Sent" 메시지 (NORMAL/ANOMALY 상태 포함)

### 3. terra-ops 로그 확인
```bash
docker-compose logs -f terra-ops
```
**예상:** "📥 Kafka Received" 및 "✅ Insight saved" 메시지

### 4. MySQL 데이터베이스 조회
```bash
docker exec -it mysql mysql -u terra -pterra2025 -e \
  "SELECT id, farm_id, status, message, timestamp FROM terra_db.insights ORDER BY timestamp DESC LIMIT 10"
```
**예상:** NORMAL 및 ANOMALY 상태를 표시하는 인사이트 테이블

### 5. Dashboard API 조회
```bash
# 모든 인사이트 조회
curl http://localhost:8083/api/v1/dashboard/insights | jq

# 대시보드 요약
curl http://localhost:8083/api/v1/dashboard/summary | jq

# 이상 데이터만 조회
curl http://localhost:8083/api/v1/insights/status/ANOMALY | jq
```

---

## 🧪 기존 E2E 테스트 실행

### neural-flow-test.py 실행

```bash
# 프로젝트 루트에서
python tests/neural-flow-test.py
```

**테스트 시나리오:**
1. **데이터 수집**: 가짜 센서 데이터를 terra-sense API로 전송
2. **AI 분석**: terra-cortex가 데이터를 소비하고 이상 탐지 수행
3. **데이터 저장**: terra-ops가 분석 결과를 MySQL에 저장
4. **API 조회**: Dashboard API를 통해 저장된 데이터 확인

**기대 결과:**
- ✅ 센서 데이터 전송 성공
- ✅ AI 분석 결과 생성
- ✅ 데이터베이스 저장 확인
- ✅ Dashboard API 정상 응답

---

## 🛠️ 문제 해결

### 문제: "Cannot connect to terra-sense"

**해결 방법:**
```bash
# Docker Compose 실행 확인
docker-compose ps

# 실행 중이 아니면 시작
docker-compose up -d

# 서비스가 안정화될 때까지 대기
sleep 30

# terra-sense 실행 확인
docker-compose logs terra-sense
```

### 문제: "HTTP 500 Internal Server Error"

**해결 방법:**
```bash
# terra-sense 로그에서 에러 확인
docker-compose logs terra-sense | grep ERROR

# Kafka 연결 확인
docker-compose logs terra-sense | grep Kafka

# terra-sense 재시작
docker-compose restart terra-sense
```

### 문제: "terra-ops 대시보드에 데이터 없음"

**가능한 원인:**
1. **Kafka 실행 안 됨:** `docker-compose logs kafka`
2. **terra-cortex 처리 안 함:** `docker-compose logs terra-cortex`
3. **terra-ops 소비 안 함:** `docker-compose logs terra-ops`

**디버그 단계:**
```bash
# 모든 서비스 상태 확인
curl http://localhost:8081/api/v1/health
curl http://localhost:8082/health
curl http://localhost:8083/api/v1/health

# Kafka 토픽 확인
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# raw-sensor-data 토픽의 Kafka 메시지 확인
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic raw-sensor-data \
  --from-beginning \
  --max-messages 5

# processed-insights 토픽의 Kafka 메시지 확인
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic processed-insights \
  --from-beginning \
  --max-messages 5
```

---

## 📈 테스트 시나리오

### 시나리오 1: 정상 운영 테스트
**목표:** 시스템이 정상 센서 데이터를 처리하는지 확인

```bash
python tests/simulation.py --mode normal --count 20
```

**예상 결과:**
- 모든 요청 HTTP 200 반환
- terra-cortex가 대부분 NORMAL 상태 인사이트 생성
- 대시보드에 낮은 이상 카운트 표시

### 시나리오 2: 이상 탐지 테스트
**목표:** AI가 범위를 벗어난 값을 탐지하는지 확인

```bash
python tests/simulation.py --mode anomaly --count 15
```

**예상 결과:**
- 모든 요청 HTTP 200 반환
- terra-cortex가 ANOMALY 상태 인사이트 생성
- 메시지에 "exceeds threshold" 또는 "below threshold" 표시
- 대시보드에 높은 이상 카운트 표시

### 시나리오 3: 부하 테스트
**목표:** 시스템이 높은 처리량을 처리하는지 확인

```bash
python tests/simulation.py --count 100 --interval 0.1
```

**예상 결과:**
- 모든 요청 성공적으로 완료
- 타임아웃이나 에러 없음
- Kafka 컨슈머 지연 낮게 유지
- 모든 인사이트가 최종적으로 MySQL에 저장됨

---

## 📊 성능 기대치

| 메트릭 | 예상 값 |
|--------|---------|
| terra-sense 응답 시간 | < 100ms |
| 엔드-투-엔드 지연시간 | < 200ms |
| 처리량 | > 100 msg/sec |
| 성공률 | > 99% |

---

## 🔧 전체 스택 관리 명령어

```bash
# 모든 서비스 시작
docker-compose up -d

# 모든 서비스 중지
docker-compose down

# 특정 서비스 재시작
docker-compose restart terra-sense

# 로그 보기 (모든 서비스)
docker-compose logs -f

# 로그 보기 (특정 서비스)
docker-compose logs -f terra-sense

# 서비스 상태 확인
docker-compose ps

# 재빌드 및 재시작
docker-compose up -d --build
```

---

## 📝 데이터 흐름 검증

완전한 파이프라인 데이터 흐름:

```
Simulation Script → terra-sense → Kafka (raw-sensor-data) → 
terra-cortex → Kafka (processed-insights) → terra-ops → MySQL
```

**타임라인:**
1. **0ms** - 시뮬레이션이 terra-sense로 HTTP POST 전송
2. **~10ms** - terra-sense가 Kafka에 게시
3. **~50ms** - terra-cortex가 소비 및 분석
4. **~60ms** - terra-cortex가 인사이트를 Kafka에 게시
5. **~100ms** - terra-ops가 소비 및 MySQL에 저장

---

## 🆘 지원

문제가 발생하면:

1. 서비스 로그 확인: `docker-compose logs <service-name>`
2. 네트워크 연결 확인: `docker network inspect terraneuron-smartfarm-platform_default`
3. Kafka 토픽 확인: `docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list`
4. 문서 검토: 각 서비스 디렉토리의 `IMPLEMENTATION.md`, `README.md`, `QUICKREF.md`

---

**Happy Testing! 🌾🧠**
# 서비스가 완전히 시작될 때까지 대기
docker-compose logs terra-sense
docker-compose logs terra-cortex
docker-compose logs terra-ops
```

### Kafka 연결 오류
```bash
# Kafka 토픽 확인
docker exec -it terraneuron-kafka kafka-topics --list --bootstrap-server localhost:9092
```

### MySQL 연결 오류
```bash
# MySQL 접속 확인
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_ops
```
