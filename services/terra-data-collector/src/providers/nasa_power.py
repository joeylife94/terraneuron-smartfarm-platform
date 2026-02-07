"""
NASA POWER Provider
NASA Prediction Of Worldwide Energy Resources — 완전 무료
https://power.larc.nasa.gov/

제공 데이터 (농업 특화):
  - T2M       → temperature (°C) — 지상 2m 기온
  - RH2M      → humidity (%) — 상대습도
  - ALLSKY_SFC_SW_DWN → light (W/m² → lux) — 전천 일사량
  - T2M_MAX   → temperature 일 최고
  - T2M_MIN   → temperature 일 최저
  - PRECTOTCORR → 보정강수량 (mm/day)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import httpx

from src.models import CollectedSensorData, DataSource, DataQuality
from src.providers import BaseProvider

logger = logging.getLogger(__name__)

# NASA POWER API
POWER_API = "https://power.larc.nasa.gov/api/temporal/daily/point"

# 파라미터 매핑: NASA → (sensorType, unit, transform)
PARAM_MAP: Dict[str, tuple] = {
    "T2M": ("temperature", "°C", lambda v: round(v, 2)),
    "RH2M": ("humidity", "%", lambda v: round(v, 2)),
    "ALLSKY_SFC_SW_DWN": ("light", "lux", lambda v: round(v * 120, 1)),
    "T2M_MAX": ("temperature", "°C", lambda v: round(v, 2)),
    "T2M_MIN": ("temperature", "°C", lambda v: round(v, 2)),
    "PRECTOTCORR": ("soilMoisture", "%", lambda v: round(min(v * 5, 100), 2)),
}


class NasaPowerProvider(BaseProvider):
    """
    NASA POWER 농업 기상 데이터 제공자.
    일 단위 데이터, 완전 무료, API 키 불필요.
    30년 이상의 기후 데이터 제공 → AI 학습에 최적.
    """

    @property
    def name(self) -> str:
        return "nasa_power"

    @property
    def quality(self) -> str:
        return DataQuality.HIGH.value

    def _get_parameters(self) -> List[str]:
        return self.config.get("parameters", list(PARAM_MAP.keys()))

    async def collect_realtime(
        self, farm_id: str, lat: float, lon: float,
    ) -> List[CollectedSensorData]:
        """최근 7일 데이터 수집 (NASA는 실시간 미제공, 며칠 지연)"""
        end = datetime.now(timezone.utc) - timedelta(days=7)
        start = end - timedelta(days=7)
        return await self.collect_historical(
            farm_id, lat, lon,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    async def collect_historical(
        self, farm_id: str, lat: float, lon: float,
        start_date: str, end_date: str,
    ) -> List[CollectedSensorData]:
        """과거 데이터 수집 (장기 AI 학습용)"""
        parameters = self._get_parameters()

        if not end_date:
            end_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        if not start_date:
            years_back = self.config.get("historical", {}).get("years_back", 3)
            start_date = (
                datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=years_back * 365)
            ).strftime("%Y-%m-%d")

        # NASA 날짜 포맷: YYYYMMDD
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        params = {
            "parameters": ",".join(parameters),
            "community": "AG",       # Agricultural community
            "longitude": lon,
            "latitude": lat,
            "start": start_fmt,
            "end": end_fmt,
            "format": "JSON",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(POWER_API, params=params)
            resp.raise_for_status()
            data = resp.json()

        records: List[CollectedSensorData] = []
        properties = data.get("properties", {})
        param_data = properties.get("parameter", {})

        for param_name in parameters:
            daily_values = param_data.get(param_name, {})
            mapping = PARAM_MAP.get(param_name)
            if not mapping:
                continue

            sensor_type, unit, transform = mapping

            for date_str, value in daily_values.items():
                # NASA는 -999를 결측값으로 사용
                if value is None or value <= -999:
                    continue

                # YYYYMMDD → ISO8601
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    ts = dt.strftime("%Y-%m-%dT12:00:00.000Z")
                except ValueError:
                    continue

                sensor_id = f"nasa-{param_name.lower()}-{farm_id}"

                records.append(CollectedSensorData(
                    sensorId=sensor_id,
                    sensorType=sensor_type,
                    value=transform(value),
                    unit=unit,
                    farmId=farm_id,
                    timestamp=ts,
                    source=DataSource.EXTERNAL,
                    provider=self.name,
                    quality=DataQuality.HIGH,
                    location={"latitude": lat, "longitude": lon},
                    raw_variable=param_name,
                ))

        logger.info(
            f"📊 [nasa_power] Historical: {len(records)} records "
            f"({start_date} ~ {end_date})"
        )
        return records
