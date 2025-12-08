# Kafka 토픽 구성
# TerraNeuron Smart Farm Platform

## 토픽 목록

### 1. raw-sensor-data
- **Producer**: terra-sense
- **Consumer**: terra-cortex
- **설명**: IoT 센서에서 수집된 원시 데이터
- **데이터 형식**: JSON
```json
{
  "sensorId": "sensor-001",
  "sensorType": "temperature",
  "value": 25.5,
  "timestamp": "2025-12-08T10:30:00Z",
  "farmId": "farm-A"
}
```

### 2. processed-insights
- **Producer**: terra-cortex
- **Consumer**: terra-ops
- **설명**: AI 분석을 통해 처리된 인사이트 데이터
- **데이터 형식**: JSON
```json
{
  "sensorId": "sensor-001",
  "insightType": "anomaly",
  "severity": "warning",
  "message": "온도가 정상 범위를 벗어났습니다",
  "confidenceScore": 0.95,
  "detectedAt": "2025-12-08T10:30:05Z",
  "rawData": { ... }
}
```

## 수동 토픽 생성 (선택사항)
Docker Compose가 자동 생성을 활성화했지만, 수동으로 생성하려면:

```bash
# Kafka 컨테이너 접속
docker exec -it terraneuron-kafka bash

# 토픽 생성
kafka-topics --create --topic raw-sensor-data --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic processed-insights --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

# 토픽 목록 확인
kafka-topics --list --bootstrap-server localhost:9092
```
