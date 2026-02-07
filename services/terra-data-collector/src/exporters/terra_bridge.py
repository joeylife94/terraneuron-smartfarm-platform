"""
Terra Bridge Exporter
수집된 데이터를 terra-sense HTTP API로 전송.
→ 실제 IoT 센서에서 데이터가 들어오는 것과 동일한 파이프라인 테스트.
"""
import asyncio
import logging
from typing import List, Dict, Any

import httpx

from src.models import CollectedSensorData
from src.exporters import BaseExporter

logger = logging.getLogger(__name__)


class TerraBridgeExporter(BaseExporter):
    """
    terra-sense HTTP API를 통해 데이터 주입.
    IoT 센서 데이터와 동일한 경로로 파이프라인 전체를 테스트.
    """

    @property
    def name(self) -> str:
        return "terra_bridge"

    async def export(self, records: List[CollectedSensorData]) -> int:
        """terra-sense /api/v1/ingest/sensor-data 로 전송"""
        base_url = self.config.get("terra_sense_url", "http://localhost:8081")
        endpoint = self.config.get("endpoint", "/api/v1/ingest/sensor-data")
        url = f"{base_url}{endpoint}"
        batch_size = self.config.get("batch_size", 10)
        delay_ms = self.config.get("delay_ms", 100)

        success_count = 0

        async with httpx.AsyncClient(timeout=10) as client:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]

                for record in batch:
                    try:
                        payload = record.to_terra_sense_payload()
                        resp = await client.post(url, json=payload)

                        if resp.status_code == 200:
                            success_count += 1
                            logger.debug(
                                f"  ✅ Sent: {record.sensorType}={record.value} "
                                f"→ {record.farmId}"
                            )
                        else:
                            self._error_count += 1
                            logger.warning(
                                f"  ⚠️ HTTP {resp.status_code}: "
                                f"{record.sensorType}={record.value}"
                            )
                    except Exception as e:
                        self._error_count += 1
                        logger.error(f"  ❌ Send failed: {e}")

                # 배치 간 지연
                if delay_ms > 0 and i + batch_size < len(records):
                    await asyncio.sleep(delay_ms / 1000)

        self._export_count += success_count
        logger.info(
            f"📤 [terra_bridge] Sent {success_count}/{len(records)} "
            f"records to {url}"
        )
        return success_count
