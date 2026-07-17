"""
Kafka Bridge Exporter
수집된 데이터를 raw-sensor-data Kafka 토픽에 직접 전송.
Docker 환경에서 terra-sense를 거치지 않고 직접 주입.
"""
import json
import logging
from typing import List, Dict, Any

from src.models import CollectedSensorData
from src.exporters import BaseExporter

logger = logging.getLogger(__name__)


class KafkaBridgeExporter(BaseExporter):
    """
    Kafka raw-sensor-data 토픽으로 직접 전송.
    terra-sense를 거치지 않는 직접 경로.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._producer = None

    @property
    def name(self) -> str:
        return "kafka_bridge"

    async def _get_producer(self):
        """Lazy Kafka producer 초기화"""
        if self._producer is None:
            from aiokafka import AIOKafkaProducer
            bootstrap = self.config.get("bootstrap_servers", "localhost:9092")
            self._producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
            logger.info(f"✅ Kafka producer started: {bootstrap}")
        return self._producer

    async def export(self, records: List[CollectedSensorData]) -> int:
        """raw-sensor-data 토픽으로 전송"""
        topic = self.config.get("topic", "raw-sensor-data")
        producer = await self._get_producer()

        success_count = 0
        for record in records:
            try:
                payload = record.to_kafka_payload()
                event_id = record.eventId
                await producer.send_and_wait(
                    topic,
                    value=payload,
                    key=event_id.encode("utf-8"),
                    headers=[("event_id", event_id.encode("utf-8"))],
                )
                success_count += 1
            except Exception as e:
                self._error_count += 1
                logger.error(f"  ❌ Kafka send failed: {e}")

        self._export_count += success_count
        logger.info(
            f"📤 [kafka_bridge] Sent {success_count}/{len(records)} "
            f"records to topic '{topic}'"
        )
        return success_count

    async def close(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
