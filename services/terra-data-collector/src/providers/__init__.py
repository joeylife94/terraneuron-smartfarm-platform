"""
Terra Data Collector - Provider Base Class
모든 데이터 제공자의 추상 인터페이스
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from src.models import CollectedSensorData

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    외부 데이터 제공자 기본 인터페이스.
    모든 Provider는 이 클래스를 상속받아 구현합니다.
    """

    def __init__(self, config: Dict[str, Any], farms: List[Dict[str, Any]]):
        self.config = config
        self.farms = farms
        self.enabled = config.get("enabled", True)
        self._collection_count = 0
        self._error_count = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """제공자 이름"""
        ...

    @property
    @abstractmethod
    def quality(self) -> str:
        """데이터 품질 등급: high, medium, low"""
        ...

    @abstractmethod
    async def collect_realtime(self, farm_id: str, lat: float, lon: float) -> List[CollectedSensorData]:
        """
        실시간 데이터 수집 (현재 시점).

        Args:
            farm_id: 매핑할 농장 ID
            lat: 위도
            lon: 경도

        Returns:
            수집된 센서 데이터 리스트
        """
        ...

    @abstractmethod
    async def collect_historical(
        self, farm_id: str, lat: float, lon: float,
        start_date: str, end_date: str,
    ) -> List[CollectedSensorData]:
        """
        과거 데이터 수집 (AI 학습용).

        Args:
            farm_id: 매핑할 농장 ID
            lat / lon: 위도 / 경도
            start_date / end_date: 조회 기간 (YYYY-MM-DD)

        Returns:
            수집된 센서 데이터 리스트
        """
        ...

    async def collect_all_farms(self, historical: bool = False, **kwargs) -> List[CollectedSensorData]:
        """모든 농장에 대해 데이터 수집"""
        all_data: List[CollectedSensorData] = []

        for farm in self.farms:
            farm_id = farm["farm_id"]
            lat = farm["latitude"]
            lon = farm["longitude"]

            try:
                if historical:
                    data = await self.collect_historical(
                        farm_id, lat, lon,
                        kwargs.get("start_date", ""),
                        kwargs.get("end_date", ""),
                    )
                else:
                    data = await self.collect_realtime(farm_id, lat, lon)

                all_data.extend(data)
                self._collection_count += len(data)
                logger.info(
                    f"✅ [{self.name}] {farm_id}: {len(data)} records collected"
                )
            except Exception as e:
                self._error_count += 1
                logger.error(f"❌ [{self.name}] {farm_id} collection failed: {e}")

        return all_data

    def get_stats(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "enabled": self.enabled,
            "quality": self.quality,
            "total_collected": self._collection_count,
            "total_errors": self._error_count,
        }
