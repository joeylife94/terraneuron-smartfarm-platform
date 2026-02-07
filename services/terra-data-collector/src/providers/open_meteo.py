"""
Open-Meteo Provider
무료 기상 API — API 키 불필요, 초당 10,000 요청 가능
https://open-meteo.com/

제공 데이터:
  - temperature_2m          → temperature (°C)
  - relative_humidity_2m    → humidity (%)
  - soil_moisture_0_to_1cm  → soilMoisture (% 변환)
  - shortwave_radiation     → light (W/m² → lux 변환)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import httpx

from src.models import CollectedSensorData, DataSource, DataQuality
from src.providers import BaseProvider

logger = logging.getLogger(__name__)

# Open-Meteo API 엔드포인트
CURRENT_API = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_API = "https://archive-api.open-meteo.com/v1/archive"

# 변수 매핑: Open-Meteo 변수 → (sensorType, unit, 변환 함수)
VARIABLE_MAP: Dict[str, tuple] = {
    "temperature_2m": ("temperature", "°C", lambda v: round(v, 2)),
    "relative_humidity_2m": ("humidity", "%", lambda v: round(v, 2)),
    "soil_moisture_0_to_1cm": (
        "soilMoisture", "%",
        lambda v: round(v * 100, 2),   # m³/m³ → % 변환
    ),
    "shortwave_radiation": (
        "light", "lux",
        lambda v: round(v * 120, 1),   # W/m² → lux 근사 변환
    ),
}


class OpenMeteoProvider(BaseProvider):
    """
    Open-Meteo 기상 데이터 제공자.
    완전 무료, API 키 불필요, 고품질 ECMWF 기반 데이터.
    """

    @property
    def name(self) -> str:
        return "open_meteo"

    @property
    def quality(self) -> str:
        return DataQuality.HIGH.value

    def _get_variables(self) -> List[str]:
        """설정에서 수집 대상 변수 목록 반환"""
        return self.config.get("variables", list(VARIABLE_MAP.keys()))

    async def collect_realtime(
        self, farm_id: str, lat: float, lon: float,
    ) -> List[CollectedSensorData]:
        """현재 기상 데이터 수집"""
        variables = self._get_variables()
        hourly_vars = ",".join(variables)

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": hourly_vars,
            "current": hourly_vars,
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(CURRENT_API, params=params)
            resp.raise_for_status()
            data = resp.json()

        records: List[CollectedSensorData] = []

        # current 데이터 파싱
        current = data.get("current", {})
        if current:
            ts = current.get("time", datetime.now(timezone.utc).isoformat())
            for var in variables:
                value = current.get(var)
                if value is None:
                    continue

                mapping = VARIABLE_MAP.get(var)
                if not mapping:
                    continue

                sensor_type, unit, transform = mapping
                records.append(CollectedSensorData(
                    sensorId=f"openmeteo-{sensor_type}-{farm_id}",
                    sensorType=sensor_type,
                    value=transform(value),
                    unit=unit,
                    farmId=farm_id,
                    timestamp=_to_iso8601(ts),
                    source=DataSource.EXTERNAL,
                    provider=self.name,
                    quality=DataQuality.HIGH,
                    location={"latitude": lat, "longitude": lon},
                    raw_variable=var,
                ))

        return records

    async def collect_historical(
        self, farm_id: str, lat: float, lon: float,
        start_date: str, end_date: str,
    ) -> List[CollectedSensorData]:
        """과거 기상 데이터 수집 (AI 학습용 대량 데이터)"""
        variables = self._get_variables()
        hourly_vars = ",".join(variables)

        # 날짜 기본값
        if not end_date:
            end_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
        if not start_date:
            days_back = self.config.get("historical", {}).get("days_back", 365)
            start_date = (
                datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days_back)
            ).strftime("%Y-%m-%d")

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": hourly_vars,
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "Asia/Seoul",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(HISTORICAL_API, params=params)
            resp.raise_for_status()
            data = resp.json()

        records: List[CollectedSensorData] = []
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        for i, ts in enumerate(times):
            for var in variables:
                values = hourly.get(var, [])
                if i >= len(values) or values[i] is None:
                    continue

                mapping = VARIABLE_MAP.get(var)
                if not mapping:
                    continue

                sensor_type, unit, transform = mapping
                records.append(CollectedSensorData(
                    sensorId=f"openmeteo-{sensor_type}-{farm_id}",
                    sensorType=sensor_type,
                    value=transform(values[i]),
                    unit=unit,
                    farmId=farm_id,
                    timestamp=_to_iso8601(ts),
                    source=DataSource.EXTERNAL,
                    provider=self.name,
                    quality=DataQuality.HIGH,
                    location={"latitude": lat, "longitude": lon},
                    raw_variable=var,
                ))

        logger.info(
            f"📊 [open_meteo] Historical: {len(records)} records "
            f"({start_date} ~ {end_date})"
        )
        return records


def _to_iso8601(ts: str) -> str:
    """타임스탬프를 ISO8601 형식으로 변환"""
    if "T" in ts and "Z" in ts:
        return ts
    # Open-Meteo 형식: "2024-01-15T10:00"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception:
        return ts
