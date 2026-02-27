"""
ThingSpeak Provider
공개 IoT 채널에서 실제 센서 데이터 수집 — 무료
https://thingspeak.com/

특징:
  - 실제 IoT 센서에서 나온 데이터 (시뮬레이션 아님)
  - 노이즈, 결측값 등 현실적인 데이터 패턴 포함
  - On-device AI 학습에 가장 현실적인 데이터 소스
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

from src.models import CollectedSensorData, DataSource, DataQuality
from src.providers import BaseProvider

logger = logging.getLogger(__name__)

# ThingSpeak API
THINGSPEAK_API = "https://api.thingspeak.com/channels"


class ThingSpeakProvider(BaseProvider):
    """
    ThingSpeak 공개 채널 데이터 제공자.
    실제 IoT 센서 데이터를 무료로 가져옴.
    """

    @property
    def name(self) -> str:
        return "thingspeak"

    @property
    def quality(self) -> str:
        return DataQuality.MEDIUM.value

    def _get_channels(self) -> List[Dict[str, Any]]:
        return self.config.get("channels", [])

    async def collect_realtime(
        self, farm_id: str, lat: float, lon: float,
    ) -> List[CollectedSensorData]:
        """공개 채널에서 최근 데이터 수집"""
        channels = self._get_channels()
        all_records: List[CollectedSensorData] = []

        for ch_config in channels:
            channel_id = ch_config["channel_id"]
            field_mapping = ch_config.get("field_mapping", {})

            try:
                records = await self._fetch_channel(
                    channel_id=channel_id,
                    field_mapping=field_mapping,
                    farm_id=farm_id,
                    results=10,  # 최근 10개
                )
                all_records.extend(records)
            except Exception as e:
                logger.warning(
                    f"⚠️ [thingspeak] Channel {channel_id} failed: {e}"
                )

        return all_records

    async def collect_historical(
        self, farm_id: str, lat: float, lon: float,
        start_date: str, end_date: str,
    ) -> List[CollectedSensorData]:
        """공개 채널에서 과거 데이터 수집"""
        channels = self._get_channels()
        all_records: List[CollectedSensorData] = []

        for ch_config in channels:
            channel_id = ch_config["channel_id"]
            field_mapping = ch_config.get("field_mapping", {})

            try:
                records = await self._fetch_channel(
                    channel_id=channel_id,
                    field_mapping=field_mapping,
                    farm_id=farm_id,
                    results=8000,  # ThingSpeak 최대
                    start=start_date,
                    end=end_date,
                )
                all_records.extend(records)
            except Exception as e:
                logger.warning(
                    f"⚠️ [thingspeak] Channel {channel_id} historical failed: {e}"
                )

        return all_records

    async def _fetch_channel(
        self,
        channel_id: int,
        field_mapping: Dict[str, str],
        farm_id: str,
        results: int = 100,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[CollectedSensorData]:
        """단일 채널에서 데이터 가져오기"""
        url = f"{THINGSPEAK_API}/{channel_id}/feeds.json"
        params: Dict[str, Any] = {"results": results}
        if start:
            params["start"] = f"{start}%2000:00:00"
        if end:
            params["end"] = f"{end}%2023:59:59"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        records: List[CollectedSensorData] = []
        feeds = data.get("feeds", [])
        channel_info = data.get("channel", {})

        unit_map = {
            "temperature": "°C",
            "humidity": "%",
            "co2": "ppm",
            "soilMoisture": "%",
            "light": "lux",
        }

        for entry in feeds:
            ts = entry.get("created_at", "")
            if ts:
                ts = ts.replace("+00:00", "Z").replace(" ", "T")
                if not ts.endswith("Z"):
                    ts += "Z"

            for field_key, sensor_type in field_mapping.items():
                raw_value = entry.get(field_key)
                if raw_value is None:
                    continue

                try:
                    value = float(raw_value)
                except (ValueError, TypeError):
                    continue

                # 이상치 필터링 (기본적인 유효성 검사)
                if not _is_valid_value(sensor_type, value):
                    continue

                records.append(CollectedSensorData(
                    sensorId=f"thingspeak-ch{channel_id}-{sensor_type}",
                    sensorType=sensor_type,
                    value=round(value, 2),
                    unit=unit_map.get(sensor_type, "unit"),
                    farmId=farm_id,
                    timestamp=ts,
                    source=DataSource.EXTERNAL,
                    provider=self.name,
                    quality=DataQuality.MEDIUM,
                    location=None,
                    raw_variable=f"channel_{channel_id}_{field_key}",
                ))

        logger.info(
            f"📡 [thingspeak] Channel {channel_id}: {len(records)} records "
            f"(from {len(feeds)} feeds)"
        )
        return records


def _is_valid_value(sensor_type: str, value: float) -> bool:
    """기본 이상치 필터링"""
    valid_ranges = {
        "temperature": (-50, 60),
        "humidity": (0, 100),
        "co2": (0, 10000),
        "soilMoisture": (0, 100),
        "light": (0, 200000),
    }
    rng = valid_ranges.get(sensor_type)
    if rng is None:
        return True
    return rng[0] <= value <= rng[1]
