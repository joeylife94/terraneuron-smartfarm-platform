# InfluxDB 설정 가이드
# TerraNeuron Smart Farm Platform

## 초기 설정 정보
- Organization: terraneuron
- Bucket: sensor_data
- Admin Token: terra-token-2025
- Username: admin
- Password: terra2025

## API 접근
- URL: http://localhost:8086
- Token: terra-token-2025

## 데이터 구조
센서 데이터는 다음과 같은 구조로 저장됩니다:

measurement: sensor_reading
tags:
  - sensor_id: 센서 고유 ID
  - sensor_type: 센서 유형 (temperature, humidity, co2 등)
  - farm_id: 농장 ID
fields:
  - value: 측정값
timestamp: RFC3339 형식

## 쿼리 예시
```flux
from(bucket: "sensor_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["sensor_type"] == "temperature")
```
