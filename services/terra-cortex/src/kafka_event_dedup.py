"""Durable semantic deduplication for Terra-Cortex sensor events.

The dedupe marker is written in the same Kafka transaction as Cortex outputs and the
consumed input offset. A compacted marker topic rebuilds the in-memory index on restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError
from aiokafka.structs import TopicPartition

from src.event_identity import ensure_event_id, measurement_fingerprint

logger = logging.getLogger(__name__)

DEDUPE_TOPIC = os.getenv("KAFKA_EVENT_DEDUPE_TOPIC", "cortex-processed-event-ids")
DEDUPE_PARTITIONS = int(os.getenv("KAFKA_EVENT_DEDUPE_PARTITIONS", "3"))


class EventClassification(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"


class EventIdConflictError(ValueError):
    pass


class KafkaEventLedger:
    """In-memory index rebuilt from a compacted, read-committed Kafka topic."""

    def __init__(self, topic: str = DEDUPE_TOPIC):
        self.topic = topic
        self._fingerprints: Dict[str, str] = {}
        self.restored_markers = 0

    def classify(self, event_id: str, fingerprint: str) -> EventClassification:
        previous = self._fingerprints.get(event_id)
        if previous is None:
            return EventClassification.NEW
        if previous == fingerprint:
            return EventClassification.DUPLICATE
        return EventClassification.CONFLICT

    def mark_local(self, event_id: str, fingerprint: str) -> None:
        self._fingerprints[event_id] = fingerprint

    @property
    def size(self) -> int:
        return len(self._fingerprints)

    async def ensure_topic(self, bootstrap_servers: str) -> None:
        admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin.start()
        try:
            await admin.create_topics(
                [
                    NewTopic(
                        name=self.topic,
                        num_partitions=DEDUPE_PARTITIONS,
                        replication_factor=1,
                        topic_configs={"cleanup.policy": "compact"},
                    )
                ]
            )
        except TopicAlreadyExistsError:
            pass
        finally:
            await admin.close()

    async def restore(self, bootstrap_servers: str) -> None:
        consumer = AIOKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=None,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            isolation_level="read_committed",
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")) if raw else None,
        )
        await consumer.start()
        try:
            partitions = consumer.partitions_for_topic(self.topic) or set()
            for _ in range(20):
                if partitions:
                    break
                await asyncio.sleep(0.1)
                partitions = consumer.partitions_for_topic(self.topic) or set()
            if not partitions:
                logger.warning("No partitions found for dedupe topic %s", self.topic)
                return

            topic_partitions = [TopicPartition(self.topic, value) for value in sorted(partitions)]
            consumer.assign(topic_partitions)
            await consumer.seek_to_beginning(*topic_partitions)
            end_offsets = await consumer.end_offsets(topic_partitions)

            while True:
                records = await consumer.getmany(
                    *topic_partitions,
                    timeout_ms=500,
                    max_records=1000,
                )
                for messages in records.values():
                    for message in messages:
                        marker = message.value or {}
                        event_id = marker.get("event_id")
                        fingerprint = marker.get("fingerprint")
                        if event_id and fingerprint:
                            self.mark_local(event_id, fingerprint)
                            self.restored_markers += 1

                caught_up = True
                for partition in topic_partitions:
                    if await consumer.position(partition) < end_offsets[partition]:
                        caught_up = False
                        break
                if caught_up:
                    return
        finally:
            await consumer.stop()

    async def initialize(self, bootstrap_servers: str) -> None:
        await self.ensure_topic(bootstrap_servers)
        await self.restore(bootstrap_servers)
        logger.info(
            "Event dedupe ledger restored: topic=%s unique_events=%s markers=%s",
            self.topic,
            self.size,
            self.restored_markers,
        )


def _marker(
    event_id: str,
    fingerprint: str,
    message: Any,
    outcome: str,
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "fingerprint": fingerprint,
        "outcome": outcome,
        "source_topic": message.topic,
        "source_partition": message.partition,
        "source_offset": message.offset,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _commit_duplicate(
    producer: AIOKafkaProducer,
    message: Any,
    consumer_group: str,
) -> None:
    offsets = {TopicPartition(message.topic, message.partition): message.offset + 1}
    async with producer.transaction():
        await producer.send_offsets_to_transaction(offsets, consumer_group)


async def _publish_result_with_marker(
    reliable: Any,
    legacy: Any,
    ledger: KafkaEventLedger,
    producer: AIOKafkaProducer,
    message: Any,
    result: Any,
    event_id: str,
    fingerprint: str,
) -> None:
    offsets = {TopicPartition(message.topic, message.partition): message.offset + 1}
    headers = [
        ("trace_id", result.trace_id.encode("utf-8")),
        ("event_id", event_id.encode("utf-8")),
    ]
    output_key = result.sensor_data.farmId.encode("utf-8")

    async with producer.transaction():
        await producer.send_and_wait(
            legacy.OUTPUT_TOPIC,
            value=result.insight_event,
            key=output_key,
            headers=headers,
        )
        if result.action_plan_event is not None:
            await producer.send_and_wait(
                legacy.ACTION_PLAN_TOPIC,
                value=result.action_plan_event,
                key=output_key,
                headers=headers,
            )
        await producer.send_and_wait(
            ledger.topic,
            value=_marker(event_id, fingerprint, message, "PROCESSED"),
            key=event_id.encode("utf-8"),
            headers=[("event_id", event_id.encode("utf-8"))],
        )
        await producer.send_offsets_to_transaction(offsets, legacy.CONSUMER_GROUP)


async def _publish_dlt(
    reliable: Any,
    legacy: Any,
    ledger: KafkaEventLedger,
    producer: AIOKafkaProducer,
    message: Any,
    trace_id: str,
    event_id: str,
    fingerprint: str,
    error: Exception,
    attempts: int,
    mark_terminal: bool,
) -> None:
    offsets = {TopicPartition(message.topic, message.partition): message.offset + 1}
    dlt_event = {
        "specversion": "1.0",
        "type": "terra.cortex.sensor-processing.failed",
        "source": "//terraneuron/terra-cortex",
        "id": reliable.generate_trace_id(),
        "time": datetime.now(timezone.utc).isoformat(),
        "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id,
            "event_id": event_id,
            "fingerprint": fingerprint,
            "source_topic": message.topic,
            "source_partition": message.partition,
            "source_offset": message.offset,
            "consumer_group": legacy.CONSUMER_GROUP,
            "attempts": attempts,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "original_payload": message.value,
        },
    }

    async with producer.transaction():
        await producer.send_and_wait(
            reliable.DLT_TOPIC,
            value=dlt_event,
            key=message.key,
            headers=[
                ("trace_id", trace_id.encode("utf-8")),
                ("event_id", event_id.encode("utf-8")),
                ("x-original-topic", message.topic.encode("utf-8")),
                ("x-exception-type", type(error).__name__.encode("utf-8")),
            ],
        )
        if mark_terminal:
            await producer.send_and_wait(
                ledger.topic,
                value=_marker(event_id, fingerprint, message, "DEAD_LETTERED"),
                key=event_id.encode("utf-8"),
                headers=[("event_id", event_id.encode("utf-8"))],
            )
        await producer.send_offsets_to_transaction(offsets, legacy.CONSUMER_GROUP)


def install(reliable: Any, legacy: Any) -> KafkaEventLedger:
    """Patch the reliable runtime before the FastAPI lifespan starts."""

    if getattr(reliable, "_event_dedupe_installed", False):
        return reliable._event_dedupe_ledger

    ledger = KafkaEventLedger()
    reliable._event_dedupe_installed = True
    reliable._event_dedupe_ledger = ledger
    reliable._delivery_stats.setdefault("duplicates_suppressed", 0)
    reliable._delivery_stats.setdefault("event_id_conflicts", 0)
    reliable._delivery_stats.setdefault("legacy_event_ids_generated", 0)

    original_start = reliable.reliable_start_kafka
    original_process = reliable._process_message

    async def start_with_ledger() -> None:
        await ledger.initialize(legacy.KAFKA_BOOTSTRAP_SERVERS)
        await original_start()

    async def process_with_dedupe(
        message: Any,
        *,
        producer: Optional[AIOKafkaProducer] = None,
        analyze_fn: Any = reliable._analyze_sensor_event,
        sleep_fn: Any = asyncio.sleep,
        max_attempts: int = reliable.MAX_PROCESSING_ATTEMPTS,
    ) -> None:
        if not isinstance(message.value, Mapping):
            await original_process(
                message,
                producer=producer,
                analyze_fn=analyze_fn,
                sleep_fn=sleep_fn,
                max_attempts=max_attempts,
            )
            return

        active_producer = producer or legacy.producer
        payload = dict(message.value)
        had_event_id = bool(str(payload.get("eventId") or "").strip())
        event_id = ensure_event_id(payload)
        fingerprint = measurement_fingerprint(payload)
        if not had_event_id:
            reliable._delivery_stats["legacy_event_ids_generated"] += 1

        classification = ledger.classify(event_id, fingerprint)
        if classification == EventClassification.DUPLICATE:
            retry = 0
            while True:
                try:
                    await _commit_duplicate(
                        active_producer, message, legacy.CONSUMER_GROUP
                    )
                    reliable._delivery_stats["duplicates_suppressed"] += 1
                    logger.info(
                        "Suppressed duplicate sensor event eventId=%s source=%s",
                        event_id,
                        reliable._source_position(message),
                    )
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    retry += 1
                    reliable._delivery_stats["transaction_failures"] += 1
                    reliable._delivery_stats["retried"] += 1
                    delay = reliable._retry_delay(retry)
                    logger.warning(
                        "Duplicate offset commit failed for eventId=%s: %s; retrying in %.1fs",
                        event_id,
                        exc,
                        delay,
                    )
                    await sleep_fn(delay)

        trace_id = reliable._trace_id_from_headers(message)
        if classification == EventClassification.CONFLICT:
            reliable._delivery_stats["event_id_conflicts"] += 1
            conflict = EventIdConflictError(
                f"eventId {event_id} was reused for a different sensor measurement"
            )
            while True:
                try:
                    await _publish_dlt(
                        reliable,
                        legacy,
                        ledger,
                        active_producer,
                        message,
                        trace_id,
                        event_id,
                        fingerprint,
                        conflict,
                        0,
                        False,
                    )
                    reliable._delivery_stats["dead_lettered"] += 1
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    reliable._delivery_stats["transaction_failures"] += 1
                    await sleep_fn(reliable.BASE_RETRY_SECONDS)
                    logger.error("Conflict DLT transaction failed: %s", exc)

        analysis_result = None
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                if analysis_result is None:
                    analysis_result = await analyze_fn(payload, trace_id)
                await _publish_result_with_marker(
                    reliable,
                    legacy,
                    ledger,
                    active_producer,
                    message,
                    analysis_result,
                    event_id,
                    fingerprint,
                )
                ledger.mark_local(event_id, fingerprint)
                reliable._delivery_stats["processed"] += 1
                await reliable._accumulate_knowledge_best_effort(analysis_result)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                reliable._delivery_stats["transaction_failures"] += 1
                if attempt < max_attempts:
                    reliable._delivery_stats["retried"] += 1
                    await sleep_fn(reliable._retry_delay(attempt))

        assert last_error is not None
        retry = 0
        while True:
            try:
                await _publish_dlt(
                    reliable,
                    legacy,
                    ledger,
                    active_producer,
                    message,
                    trace_id,
                    event_id,
                    fingerprint,
                    last_error,
                    max_attempts,
                    True,
                )
                ledger.mark_local(event_id, fingerprint)
                reliable._delivery_stats["dead_lettered"] += 1
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                retry += 1
                reliable._delivery_stats["transaction_failures"] += 1
                await sleep_fn(reliable._retry_delay(retry))
                logger.error("DLT transaction failed: %s", exc)

    reliable.reliable_start_kafka = start_with_ledger
    reliable._process_message = process_with_dedupe
    legacy.start_kafka = start_with_ledger
    legacy.consume_messages = reliable.reliable_consume_messages

    @reliable.app.get("/api/kafka/deduplication")
    async def event_deduplication_status() -> Dict[str, Any]:
        return {
            "enabled": True,
            "topic": ledger.topic,
            "cleanup_policy": "compact",
            "unique_events_loaded": ledger.size,
            "restored_markers": ledger.restored_markers,
            "required_input_key": "eventId",
            "stats": {
                "duplicates_suppressed": reliable._delivery_stats["duplicates_suppressed"],
                "event_id_conflicts": reliable._delivery_stats["event_id_conflicts"],
                "legacy_event_ids_generated": reliable._delivery_stats[
                    "legacy_event_ids_generated"
                ],
            },
        }

    return ledger
