# TerraNeuron 시뮬레이터 도구

실시간 센서 데이터를 생성하여 시스템을 테스트하는 도구들입니다.

## 📊 센서 데이터 시뮬레이터

### 설치

```bash
pip install requests
```

### 사용법

#### 1. 정상 모드 (Normal Mode)
모든 센서가 정상 범위 내 데이터를 생성합니다.

```bash
python tools/sensor-simulator.py --mode normal --duration 60
```

#### 2. 이상 모드 (Anomaly Mode)
특정 시나리오의 이상 데이터를 생성합니다.

```bash
# 폭염 시나리오
python tools/sensor-simulator.py --mode anomaly --scenario heat_wave --duration 30

# 한파 시나리오
python tools/sensor-simulator.py --mode anomaly --scenario cold_snap --duration 30

# 높은 CO2 시나리오
python tools/sensor-simulator.py --mode anomaly --scenario high_co2 --duration 30

# 가뭄 시나리오
python tools/sensor-simulator.py --mode anomaly --scenario drought --duration 30
```

#### 3. 혼합 모드 (Mixed Mode)
정상과 이상 데이터가 섞인 현실적인 시뮬레이션입니다.

```bash
python tools/sensor-simulator.py --mode mixed --duration 120 --interval 3
```

#### 4. 부하 테스트 (Stress Test)
대량의 데이터를 빠르게 전송하여 시스템 성능을 테스트합니다.

```bash
python tools/sensor-simulator.py --mode stress --rate 1000
```

### 전체 옵션

```bash
python tools/sensor-simulator.py --help

옵션:
  --url URL            Terra-Sense API URL (기본: http://localhost:8081)
  --mode {normal,anomaly,mixed,stress}
                       시뮬레이션 모드 (기본: mixed)
  --scenario {heat_wave,cold_snap,high_co2,drought}
                       이상 시나리오 (anomaly 모드용)
  --interval SECONDS   데이터 전송 간격 (기본: 4초)
  --duration SECONDS   실행 시간 (기본: 60초)
  --rate COUNT         부하 테스트 데이터 개수 (기본: 100)
```

## 🧪 사용 예시

### 시나리오 1: 일일 정상 운영 시뮬레이션

```bash
# 10분간 정상 데이터 생성
python tools/sensor-simulator.py --mode normal --duration 600 --interval 5
```

### 시나리오 2: 폭염 경보 테스트

```bash
# 5분간 폭염 시뮬레이션
python tools/sensor-simulator.py --mode anomaly --scenario heat_wave --duration 300 --interval 2
```

### 시나리오 3: 24시간 연속 모니터링

```bash
# 24시간 혼합 모드 (86400초)
python tools/sensor-simulator.py --mode mixed --duration 86400 --interval 10
```

### 시나리오 4: 시스템 부하 테스트

```bash
# 10,000개 데이터 전송
python tools/sensor-simulator.py --mode stress --rate 10000
```

## 📈 센서 정의

시뮬레이터는 다음 센서들을 지원합니다:

| 센서 ID | 타입 | 농장 | 위치 | 정상 범위 |
|---------|------|------|------|-----------|
| sensor-001 | temperature | farm-A | A동-구역1 | 18-28°C |
| sensor-002 | humidity | farm-A | A동-구역1 | 50-75% |
| sensor-003 | co2 | farm-A | A동-구역1 | 400-800 ppm |
| sensor-004 | temperature | farm-B | B동-구역1 | 18-28°C |
| sensor-005 | humidity | farm-B | B동-구역1 | 50-75% |
| sensor-006 | co2 | farm-B | B동-구역2 | 400-800 ppm |
| sensor-007 | soil_moisture | farm-A | A동-구역2 | 30-60% |
| sensor-008 | light | farm-B | B동-구역1 | 200-800 lux |

## 🎭 이상 시나리오

### 폭염 (heat_wave)
- 온도: ~35°C
- 습도: ~85%

### 한파 (cold_snap)
- 온도: ~10°C
- 습도: ~40%

### 높은 CO2 (high_co2)
- CO2: ~1500 ppm

### 가뭄 (drought)
- 토양 수분: ~15%

## 🔍 모니터링

시뮬레이터 실행 중 다음을 통해 모니터링할 수 있습니다:

```bash
# Dashboard 조회
curl http://localhost:8080/api/v1/dashboard/summary

# 최근 인사이트 조회
curl http://localhost:8080/api/v1/insights | jq '.'

# Grafana 대시보드
open http://localhost:3000
```

## 💡 팁

1. **장시간 실행 시** `nohup` 사용:
   ```bash
   nohup python tools/sensor-simulator.py --mode mixed --duration 86400 &
   ```

2. **결과 로깅**:
   ```bash
   python tools/sensor-simulator.py --mode mixed --duration 3600 > simulator.log 2>&1
   ```

3. **여러 시뮬레이터 동시 실행**:
   ```bash
   # 터미널 1: 정상 데이터
   python tools/sensor-simulator.py --mode normal --duration 600
   
   # 터미널 2: 이상 데이터
   python tools/sensor-simulator.py --mode anomaly --scenario heat_wave --duration 60
   ```
