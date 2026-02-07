"""
Terra Data Collector - Core Collector Engine
Provider에서 데이터를 수집하고 Exporter로 내보내는 핵심 엔진
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.config import AppConfig
from src.models import CollectedSensorData, CollectionResult, CollectionSummary

# Providers
from src.providers import BaseProvider
from src.providers.open_meteo import OpenMeteoProvider
from src.providers.nasa_power import NasaPowerProvider
from src.providers.thingspeak import ThingSpeakProvider

# Exporters
from src.exporters import BaseExporter
from src.exporters.terra_bridge import TerraBridgeExporter
from src.exporters.kafka_bridge import KafkaBridgeExporter
from src.exporters.csv_exporter import CsvExporter
from src.exporters.jsonl_exporter import JsonlExporter
from src.exporters.parquet_exporter import ParquetExporter

logger = logging.getLogger(__name__)


# Provider 레지스트리
PROVIDER_REGISTRY: Dict[str, type] = {
    "open_meteo": OpenMeteoProvider,
    "nasa_power": NasaPowerProvider,
    "thingspeak": ThingSpeakProvider,
}

# Exporter 레지스트리
EXPORTER_REGISTRY: Dict[str, type] = {
    "terra_bridge": TerraBridgeExporter,
    "kafka_bridge": KafkaBridgeExporter,
    "csv_export": CsvExporter,
    "jsonl_export": JsonlExporter,
    "parquet_export": ParquetExporter,
}


class Collector:
    """
    데이터 수집 엔진.
    설정에 따라 Provider와 Exporter를 조합하여 실행.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.providers: Dict[str, BaseProvider] = {}
        self.exporters: Dict[str, BaseExporter] = {}
        self._init_providers()
        self._init_exporters()

    def _init_providers(self):
        """설정된 Provider 초기화"""
        farms = self.config.farms

        for name, provider_cls in PROVIDER_REGISTRY.items():
            provider_config = self.config.providers.get(name, {})
            if provider_config.get("enabled", False):
                self.providers[name] = provider_cls(provider_config, farms)
                logger.info(f"  ✅ Provider '{name}' initialized")
            else:
                logger.info(f"  ⏭️ Provider '{name}' disabled")

    def _init_exporters(self):
        """설정된 Exporter 초기화"""
        for name, exporter_cls in EXPORTER_REGISTRY.items():
            exporter_config = self.config.exporters.get(name, {})
            if exporter_config.get("enabled", False):
                self.exporters[name] = exporter_cls(exporter_config)
                logger.info(f"  ✅ Exporter '{name}' initialized")
            else:
                logger.info(f"  ⏭️ Exporter '{name}' disabled")

    async def collect_and_export(
        self,
        provider_names: Optional[List[str]] = None,
        exporter_names: Optional[List[str]] = None,
        historical: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CollectionSummary:
        """
        데이터 수집 → 내보내기 전체 파이프라인 실행.

        Args:
            provider_names: 사용할 Provider 목록 (None이면 전체)
            exporter_names: 사용할 Exporter 목록 (None이면 전체)
            historical: 과거 데이터 수집 여부
            start_date/end_date: 과거 데이터 기간

        Returns:
            수집 세션 요약
        """
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        summary = CollectionSummary(
            session_id=session_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # 1. 데이터 수집
        all_records: List[CollectedSensorData] = []

        providers = self._select_providers(provider_names)
        for name, provider in providers.items():
            start_time = time.time()
            try:
                records = await provider.collect_all_farms(
                    historical=historical,
                    start_date=start_date or "",
                    end_date=end_date or "",
                )
                duration = (time.time() - start_time) * 1000

                all_records.extend(records)
                summary.providers_used.append(name)
                summary.results.append(CollectionResult(
                    provider=name,
                    farm_id="all",
                    records_collected=len(records),
                    duration_ms=round(duration, 1),
                ))
                logger.info(
                    f"📊 [{name}] Collected {len(records)} records "
                    f"in {duration:.0f}ms"
                )
            except Exception as e:
                summary.results.append(CollectionResult(
                    provider=name,
                    farm_id="all",
                    errors=[str(e)],
                    duration_ms=(time.time() - start_time) * 1000,
                ))
                summary.total_errors += 1
                logger.error(f"❌ [{name}] Collection failed: {e}")

        summary.total_records = len(all_records)

        if not all_records:
            logger.warning("⚠️ No records collected from any provider")
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            return summary

        # 2. 데이터 내보내기
        exporters = self._select_exporters(exporter_names)
        for name, exporter in exporters.items():
            try:
                exported = await exporter.export(all_records)
                summary.total_exported += exported
                logger.info(f"📤 [{name}] Exported {exported} records")
            except Exception as e:
                summary.total_errors += 1
                logger.error(f"❌ [{name}] Export failed: {e}")

        summary.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"✅ Session {session_id} complete: "
            f"{summary.total_records} collected, "
            f"{summary.total_exported} exported, "
            f"{summary.total_errors} errors"
        )
        return summary

    def _select_providers(
        self, names: Optional[List[str]],
    ) -> Dict[str, BaseProvider]:
        if names is None:
            return self.providers
        return {n: p for n, p in self.providers.items() if n in names}

    def _select_exporters(
        self, names: Optional[List[str]],
    ) -> Dict[str, BaseExporter]:
        if names is None:
            return self.exporters
        return {n: e for n, e in self.exporters.items() if n in names}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "providers": {n: p.get_stats() for n, p in self.providers.items()},
            "exporters": {n: e.get_stats() for n, e in self.exporters.items()},
        }
