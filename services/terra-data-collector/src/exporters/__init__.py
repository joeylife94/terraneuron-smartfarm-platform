"""
Terra Data Collector - Exporter Base Class
모든 데이터 내보내기 핸들러의 추상 인터페이스
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from src.models import CollectedSensorData

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """데이터 내보내기 기본 인터페이스"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self._export_count = 0
        self._error_count = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """내보내기 이름"""
        ...

    @abstractmethod
    async def export(self, records: List[CollectedSensorData]) -> int:
        """
        데이터 내보내기 실행.

        Args:
            records: 내보낼 센서 데이터 리스트

        Returns:
            성공적으로 내보낸 레코드 수
        """
        ...

    def get_stats(self) -> Dict[str, Any]:
        return {
            "exporter": self.name,
            "enabled": self.enabled,
            "total_exported": self._export_count,
            "total_errors": self._error_count,
        }
