"""Bounded, durable semantic deduplication for Terra-Cortex sensor events.

Markers are committed atomically with Cortex outputs and the consumed input offset.
The Kafka changelog is retained for a configured processing-time window while an
expiry heap keeps the per-process index bounded without scanning the full map.
"""

from __future__ import annotations

import asyncio
import hashlib
import heapq
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRebalanceListener
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.admin.config_resource import ConfigResource, ConfigResourceType
from aiokafka.errors import TopicAlreadyExistsError
from aiokafka.structs import TopicPartition

from src.event_identity import ensure_event_id, measurement_fingerprint

logger = logging.getLogger(__name__)

DEDUPE_TOPIC = os.getenv("KAFKA_EVENT_DEDUPE_TOPIC", "cortex-processed-event-ids")
DEDUPE_PARTITIONS = int(os.getenv("KAFKA_EVENT_DEDUPE_PARTITIONS", "3"))
DEDUPE_RETENTION_DAYS = int(os.getenv("KAFKA_EVENT_DEDUPE_RETENTION_DAYS", "30"))
DEDUPE_SWEEP_INTERVAL_SECONDS = int(
    os.getenv("KAFKA_EVENT_DEDUPE_SWEEP_INTERVAL_SECONDS", "300")
)
DEDUPE_DELETE_RETENTION_MS = int(
    os.getenv("KAFKA_EVENT_DEDUPE_DELETE_RETENTION_MS", "86400000")
)
DEDUPE_SEGMENT_MS = int(os.getenv("KAFKA_EVENT_DEDUPE_SEGMENT_MS", "3600000"))
DEDUPE_MIN_CLEANABLE_DIRTY_RATIO = os.getenv(
    "KAFKA_EVENT_DEDUPE_MIN_CLEANABLE_DIRTY_RATIO", "0.1"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


class EventClassification(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"


class EventIdConflictError(ValueError):
    pass


@dataclass(frozen=True)
class LedgerEntry:
    fingerprint: str
    processed_at: datetime
    expires_at: datetime
    status: str
    generation: int


class KafkaEventLedger:
    """Read-committed Kafka changelog plus an expiry-indexed in-memory view."""

    def __init__(
        self,
        topic: str = DEDUPE_TOPIC,
        *,
        retention_days: int = DEDUPE_RETENTION_DAYS,
        sweep_interval_seconds: int = DEDUPE_SWEEP_INTERVAL_SECONDS,
        now_fn: Callable[[], datetime] = _utc_now,
    ):
        if retention_days <= 0:
            raise ValueError("dedupe retention must be greater than zero days")
        if sweep_interval_seconds <= 0:
            raise ValueError("dedupe sweep interval must be greater than zero seconds")

        self.topic = topic
        self.retention_days = retention_days
        self.retention = timedelta(days=retention_days)
        self.sweep_interval_seconds = sweep_interval_seconds
        self._now_fn = now_fn
        self._entries: Dict[str, LedgerEntry] = {}
        self._expiry_heap: list[tuple[float, int, str]] = []
        self._generation = 0

        self.restored_markers = 0
        self.restore_records_scanned = 0
        self.expired_markers_skipped = 0
        self.active_event_ids_loaded = 0
        self.last_restore_duration_ms = 0
        self.expired_marker_count = 0
        self.expired_markers_swept = 0
        self.marker_records_followed = 0
        self.last_sweep_time: Optional[datetime] = None
        self.next_scheduled_sweep: Optional[datetime] = None
        self.restore_completed = False

        self._consumer: Optional[AIOKafkaConsumer] = None
        self._consumer_lock = asyncio.Lock()
        self._follower_task: Optional[asyncio.Task[Any]] = None
        self._sweep_task: Optional[asyncio.Task[Any]] = None

    def now(self) -> datetime:
        return _as_utc(self._now_fn())

    @property
    def retention_ms(self) -> int:
        return int(self.retention.total_seconds() * 1000)

    @property
    def topic_configs(self) -> Dict[str, str]:
        return {
            "cleanup.policy": "compact,delete",
            "retention.ms": str(self.retention_ms),
            "delete.retention.ms": str(DEDUPE_DELETE_RETENTION_MS),
            "segment.ms": str(DEDUPE_SEGMENT_MS),
            "min.cleanable.dirty.ratio": DEDUPE_MIN_CLEANABLE_DIRTY_RATIO,
        }

    def classify(self, event_id: str, fingerprint: str) -> EventClassification:
        entry = self._entries.get(event_id)
        if entry is None:
            return EventClassification.NEW
        if entry.expires_at <= self.now():
            del self._entries[event_id]
            self.expired_marker_count += 1
            return EventClassification.NEW
        if entry.fingerprint == fingerprint:
            return EventClassification.DUPLICATE
        return EventClassification.CONFLICT

    def build_marker(
        self,
        event_id: str,
        fingerprint: str,
        message: Any,
        status: str,
    ) -> Dict[str, Any]:
        processed_at = self.now()
        expires_at = processed_at + self.retention
        return {
            "event_id": event_id,
            "fingerprint": fingerprint,
            "status": status,
            "outcome": status,
            "source_topic": message.topic,
            "source_partition": message.partition,
            "source_offset": message.offset,
            "processed_at": processed_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def apply_marker(
        self,
        marker: Mapping[str, Any],
        *,
        count_expired: bool = True,
        record_timestamp_ms: Optional[int] = None,
    ) -> bool:
        event_id = str(marker.get("event_id") or "").strip()
        fingerprint = str(marker.get("fingerprint") or "").strip()
        if not event_id or not fingerprint:
            return False

        processed_at = _parse_datetime(marker.get("processed_at"))
        if processed_at is None and record_timestamp_ms is not None:
            processed_at = datetime.fromtimestamp(
                record_timestamp_ms / 1000, tz=timezone.utc
            )
        if processed_at is None:
            return False

        expires_at = _parse_datetime(marker.get("expires_at"))
        if expires_at is None:
            expires_at = processed_at + self.retention

        if expires_at <= self.now():
            self._entries.pop(event_id, None)
            if count_expired:
                self.expired_marker_count += 1
            return False

        self._generation += 1
        entry = LedgerEntry(
            fingerprint=fingerprint,
            processed_at=processed_at,
            expires_at=expires_at,
            status=str(marker.get("status") or marker.get("outcome") or "PROCESSED"),
            generation=self._generation,
        )
        self._entries[event_id] = entry
        heapq.heappush(
            self._expiry_heap,
            (entry.expires_at.timestamp(), entry.generation, event_id),
        )
        return True

    def mark_local(
        self,
        event_id: str,
        fingerprint: str,
        *,
        processed_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        status: str = "PROCESSED",
    ) -> None:
        processed_at = _as_utc(processed_at or self.now())
        expires_at = _as_utc(expires_at or (processed_at + self.retention))
        self.apply_marker(
            {
                "event_id": event_id,
                "fingerprint": fingerprint,
                "processed_at": processed_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "status": status,
            }
        )

    def sweep_expired(self) -> int:
        now = self.now()
        removed = 0
        while self._expiry_heap and self._expiry_heap[0][0] <= now.timestamp():
            _, generation, event_id = heapq.heappop(self._expiry_heap)
            entry = self._entries.get(event_id)
            if entry is None or entry.generation != generation:
                continue
            if entry.expires_at <= now:
                del self._entries[event_id]
                removed += 1

        self.expired_markers_swept += removed
        self.expired_marker_count += removed
        self.last_sweep_time = now
        self.next_scheduled_sweep = now + timedelta(
            seconds=self.sweep_interval_seconds
        )
        return removed

    @property
    def size(self) -> int:
        return len(self._entries)

    async def ensure_topic(self, bootstrap_servers: str) -> None:
        admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
        await admin.start()
        try:
            try:
                await admin.create_topics(
                    [
                        NewTopic(
                            name=self.topic,
                            num_partitions=DEDUPE_PARTITIONS,
                            replication_factor=1,
                            topic_configs=self.topic_configs,
                        )
                    ]
                )
            except TopicAlreadyExistsError:
                pass

            resource = ConfigResource(
                ConfigResourceType.TOPIC,
                self.topic,
                configs=self.topic_configs,
            )
            await admin.alter_configs([resource])
        finally:
            await admin.close()

    def _new_consumer(self, bootstrap_servers: str) -> AIOKafkaConsumer:
        return AIOKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=None,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            isolation_level="read_committed",
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")) if raw else None,
        )

    async def _assign_all_partitions(self, consumer: AIOKafkaConsumer) -> list[TopicPartition]:
        partitions = consumer.partitions_for_topic(self.topic) or set()
        for _ in range(20):
            if partitions:
                break
            await asyncio.sleep(0.1)
            partitions = consumer.partitions_for_topic(self.topic) or set()
        if not partitions:
            raise RuntimeError(f"No partitions found for dedupe topic {self.topic}")

        topic_partitions = [
            TopicPartition(self.topic, value) for value in sorted(partitions)
        ]
        consumer.assign(topic_partitions)
        return topic_partitions

    def _apply_record(self, message: Any, *, restoring: bool) -> None:
        if restoring:
            self.restore_records_scanned += 1
        else:
            self.marker_records_followed += 1

        marker = message.value
        if marker is None:
            key = message.key.decode("utf-8") if message.key else ""
            if key:
                self._entries.pop(key, None)
            return
        if not isinstance(marker, Mapping):
            return

        loaded = self.apply_marker(
            marker,
            count_expired=not restoring,
            record_timestamp_ms=getattr(message, "timestamp", None),
        )
        if restoring and not loaded:
            expires_at = _parse_datetime(marker.get("expires_at"))
            processed_at = _parse_datetime(marker.get("processed_at"))
            effective_expiry = expires_at or (
                processed_at + self.retention if processed_at else None
            )
            if effective_expiry is not None and effective_expiry <= self.now():
                self.expired_markers_skipped += 1
                self.expired_marker_count += 1

    async def _drain_to(
        self,
        consumer: AIOKafkaConsumer,
        topic_partitions: list[TopicPartition],
        end_offsets: Mapping[TopicPartition, int],
        *,
        restoring: bool,
    ) -> None:
        while True:
            records = await consumer.getmany(
                *topic_partitions,
                timeout_ms=500,
                max_records=1000,
            )
            for messages in records.values():
                for message in messages:
                    self._apply_record(message, restoring=restoring)

            caught_up = True
            for partition in topic_partitions:
                if await consumer.position(partition) < end_offsets[partition]:
                    caught_up = False
                    break
            if caught_up:
                return

    async def _restore_consumer(self, consumer: AIOKafkaConsumer) -> None:
        started = time.monotonic()
        self.restore_completed = False
        self.restore_records_scanned = 0
        self.expired_markers_skipped = 0
        topic_partitions = await self._assign_all_partitions(consumer)
        await consumer.seek_to_beginning(*topic_partitions)
        end_offsets = await consumer.end_offsets(topic_partitions)
        await self._drain_to(
            consumer,
            topic_partitions,
            end_offsets,
            restoring=True,
        )
        self.active_event_ids_loaded = self.size
        self.restored_markers = self.active_event_ids_loaded
        self.last_restore_duration_ms = int((time.monotonic() - started) * 1000)
        self.restore_completed = True

    async def restore(self, bootstrap_servers: str) -> None:
        consumer = self._new_consumer(bootstrap_servers)
        await consumer.start()
        try:
            await self._restore_consumer(consumer)
        finally:
            await consumer.stop()

    async def catch_up(self) -> None:
        """Drain committed markers before a raw partition assignment starts."""

        if self._consumer is None:
            return
        async with self._consumer_lock:
            topic_partitions = list(self._consumer.assignment())
            if not topic_partitions:
                return
            end_offsets = await self._consumer.end_offsets(topic_partitions)
            await self._drain_to(
                self._consumer,
                topic_partitions,
                end_offsets,
                restoring=False,
            )

    async def _follow_markers(self) -> None:
        assert self._consumer is not None
        try:
            while True:
                async with self._consumer_lock:
                    records = await self._consumer.getmany(
                        timeout_ms=1000,
                        max_records=1000,
                    )
                    for messages in records.values():
                        for message in messages:
                            self._apply_record(message, restoring=False)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dedupe marker follower terminated unexpectedly")
            raise

    async def _sweep_loop(self) -> None:
        try:
            while True:
                self.next_scheduled_sweep = self.now() + timedelta(
                    seconds=self.sweep_interval_seconds
                )
                await asyncio.sleep(self.sweep_interval_seconds)
                removed = self.sweep_expired()
                if removed:
                    logger.info("Expired %s in-memory dedupe markers", removed)
        except asyncio.CancelledError:
            raise

    async def initialize(self, bootstrap_servers: str) -> None:
        await self.ensure_topic(bootstrap_servers)
        consumer = self._new_consumer(bootstrap_servers)
        await consumer.start()
        self._consumer = consumer
        try:
            async with self._consumer_lock:
                await self._restore_consumer(consumer)
            self.next_scheduled_sweep = self.now() + timedelta(
                seconds=self.sweep_interval_seconds
            )
            self._follower_task = asyncio.create_task(self._follow_markers())
            self._sweep_task = asyncio.create_task(self._sweep_loop())
        except Exception:
            await consumer.stop()
            self._consumer = None
            raise

        logger.info(
            "Event dedupe ledger restored: topic=%s active=%s scanned=%s expired=%s duration_ms=%s",
            self.topic,
            self.size,
            self.restore_records_scanned,
            self.expired_markers_skipped,
            self.last_restore_duration_ms,
        )

    async def stop(self) -> None:
        for task in (self._follower_task, self._sweep_task):
            if task is not None:
                task.cancel()
        for task in (self._follower_task, self._sweep_task):
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._follower_task = None
        self._sweep_task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None


class LedgerRebalanceListener(ConsumerRebalanceListener):
    """Synchronize the local changelog view at raw consumer ownership changes."""

    def __init__(self, ledger: KafkaEventLedger):
        self.ledger = ledger

    async def on_partitions_revoked(self, revoked: Any) -> None:
        return None

    async def on_partitions_assigned(self, assigned: Any) -> None:
        await self.ledger.catch_up()


def _fallback_identity(payload: Mapping[str, Any]) -> tuple[str, str]:
    canonical = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(canonical).hexdigest()
    supplied = str(payload.get("eventId") or "").strip()
    return supplied or f"invalid-{fingerprint}", fingerprint


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
    marker: Mapping[str, Any],
) -> None:
    event_id = str(marker["event_id"])
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
            value=dict(marker),
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
    marker: Optional[Mapping[str, Any]],
) -> None:
    offsets = {TopicPartition(message.topic, message.partition): message.offset + 1}
    dlt_event = {
        "specversion": "1.0",
        "type": "terra.cortex.sensor-processing.failed",
        "source": "//terraneuron/terra-cortex",
        "id": reliable.generate_trace_id(),
        "time": _utc_now().isoformat(),
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
            "error_code": (
                "EVENT_ID_CONFLICT"
                if isinstance(error, EventIdConflictError)
                else "SENSOR_PROCESSING_FAILED"
            ),
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
        if marker is not None:
            await producer.send_and_wait(
                ledger.topic,
                value=dict(marker),
                key=event_id.encode("utf-8"),
                headers=[("event_id", event_id.encode("utf-8"))],
            )
        await producer.send_offsets_to_transaction(offsets, legacy.CONSUMER_GROUP)


async def _retry_terminal_dlt(
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
    marker: Optional[Mapping[str, Any]],
    sleep_fn: Callable[[float], Any],
) -> None:
    retry = 0
    while True:
        try:
            await _publish_dlt(
                reliable,
                legacy,
                ledger,
                producer,
                message,
                trace_id,
                event_id,
                fingerprint,
                error,
                attempts,
                marker,
            )
            if marker is not None:
                ledger.apply_marker(marker)
            reliable._delivery_stats["dead_lettered"] += 1
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            retry += 1
            reliable._delivery_stats["transaction_failures"] += 1
            await sleep_fn(reliable._retry_delay(retry))
            logger.error("DLT transaction failed: %s", exc)


def _status_payload(
    ledger: KafkaEventLedger,
    delivery_stats: Mapping[str, int],
) -> Dict[str, Any]:
    return {
        "enabled": True,
        "topic": ledger.topic,
        "cleanup_policy": "compact,delete",
        "topic_policy": ledger.topic_configs,
        "configured_retention": {
            "days": ledger.retention_days,
            "milliseconds": ledger.retention_ms,
            "basis": "cortex_processed_at",
        },
        "active_marker_count": ledger.size,
        "expired_marker_count": ledger.expired_marker_count,
        "last_sweep_time": (
            ledger.last_sweep_time.isoformat() if ledger.last_sweep_time else None
        ),
        "next_scheduled_sweep": (
            ledger.next_scheduled_sweep.isoformat()
            if ledger.next_scheduled_sweep
            else None
        ),
        "sweep_interval_seconds": ledger.sweep_interval_seconds,
        "restore": {
            "completed": ledger.restore_completed,
            "expired_markers_skipped": ledger.expired_markers_skipped,
            "active_event_ids_loaded": ledger.active_event_ids_loaded,
            "restore_duration_ms": ledger.last_restore_duration_ms,
            "restore_records_scanned": ledger.restore_records_scanned,
        },
        "runtime": {
            "expired_markers_swept": ledger.expired_markers_swept,
            "marker_records_followed": ledger.marker_records_followed,
            "marker_follower_running": (
                ledger._follower_task is not None
                and not ledger._follower_task.done()
            ),
            "expiry_sweep_running": (
                ledger._sweep_task is not None and not ledger._sweep_task.done()
            ),
        },
        "expired_event_policy": "process_as_new",
        "dead_lettered_marker_retention": "same_window",
        "required_input_key": "eventId",
        # Backward-compatible fields retained for existing probes.
        "unique_events_loaded": ledger.size,
        "restored_markers": ledger.restored_markers,
        "stats": {
            "duplicates_suppressed": delivery_stats["duplicates_suppressed"],
            "event_id_conflicts": delivery_stats["event_id_conflicts"],
            "legacy_event_ids_generated": delivery_stats[
                "legacy_event_ids_generated"
            ],
        },
    }


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
    original_stop = reliable.reliable_stop_kafka
    original_process = reliable._process_message
    reliable.CONSUMER_REBALANCE_LISTENER = LedgerRebalanceListener(ledger)

    async def start_with_ledger() -> None:
        await ledger.initialize(legacy.KAFKA_BOOTSTRAP_SERVERS)
        try:
            await original_start()
        except Exception:
            await ledger.stop()
            raise

    async def stop_with_ledger() -> None:
        try:
            await original_stop()
        finally:
            await ledger.stop()

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
        identity_error: Optional[Exception] = None
        try:
            event_id = ensure_event_id(payload)
            fingerprint = measurement_fingerprint(payload)
        except Exception as exc:
            identity_error = exc
            event_id, fingerprint = _fallback_identity(payload)

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
            await _retry_terminal_dlt(
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
                None,
                sleep_fn,
            )
            return

        if identity_error is not None:
            marker = ledger.build_marker(
                event_id, fingerprint, message, "DEAD_LETTERED"
            )
            await _retry_terminal_dlt(
                reliable,
                legacy,
                ledger,
                active_producer,
                message,
                trace_id,
                event_id,
                fingerprint,
                identity_error,
                0,
                marker,
                sleep_fn,
            )
            return

        analysis_result = None
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                if analysis_result is None:
                    analysis_result = await analyze_fn(payload, trace_id)
                marker = ledger.build_marker(
                    event_id, fingerprint, message, "PROCESSED"
                )
                await _publish_result_with_marker(
                    reliable,
                    legacy,
                    ledger,
                    active_producer,
                    message,
                    analysis_result,
                    marker,
                )
                ledger.apply_marker(marker)
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
        marker = ledger.build_marker(
            event_id, fingerprint, message, "DEAD_LETTERED"
        )
        await _retry_terminal_dlt(
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
            marker,
            sleep_fn,
        )

    reliable.reliable_start_kafka = start_with_ledger
    reliable.reliable_stop_kafka = stop_with_ledger
    reliable._process_message = process_with_dedupe
    legacy.start_kafka = start_with_ledger
    legacy.stop_kafka = stop_with_ledger
    legacy.consume_messages = reliable.reliable_consume_messages

    @reliable.app.get("/api/kafka/deduplication")
    async def event_deduplication_status() -> Dict[str, Any]:
        return _status_payload(ledger, reliable._delivery_stats)

    return ledger
