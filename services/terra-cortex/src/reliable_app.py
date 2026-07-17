"""Reliable Kafka runtime for Terra-Cortex.

This module keeps the existing FastAPI surface and AI components from ``src.main``
while replacing its Kafka lifecycle with consume-transform-produce transactions.
Output records and the consumed input offset are committed atomically.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition

from src import main as legacy
from src.cloudevents_models import (
    InsightStatus,
    Priority,
    Severity,
    create_action_plan_event,
    create_insight_event,
    generate_trace_id,
)
from src.models import Insight, SensorData

logger = logging.getLogger(__name__)

DLT_TOPIC = os.getenv("KAFKA_DLT_TOPIC", f"{legacy.INPUT_TOPIC}.DLT")
MAX_PROCESSING_ATTEMPTS = int(os.getenv("KAFKA_PROCESSING_MAX_ATTEMPTS", "3"))
BASE_RETRY_SECONDS = float(os.getenv("KAFKA_PROCESSING_RETRY_SECONDS", "1"))
MAX_RETRY_SECONDS = float(os.getenv("KAFKA_PROCESSING_MAX_RETRY_SECONDS", "30"))
MAX_POLL_INTERVAL_MS = int(os.getenv("KAFKA_MAX_POLL_INTERVAL_MS", "900000"))
TRANSACTION_TIMEOUT_MS = int(os.getenv("KAFKA_TRANSACTION_TIMEOUT_MS", "60000"))
INSTANCE_ID = os.getenv("KAFKA_INSTANCE_ID", socket.gethostname())
TRANSACTIONAL_ID = os.getenv(
    "KAFKA_TRANSACTIONAL_ID", f"terra-cortex-{INSTANCE_ID}"
)
CONSUMER_REBALANCE_LISTENER: Optional[Any] = None

_delivery_stats: Dict[str, int] = {
    "processed": 0,
    "retried": 0,
    "dead_lettered": 0,
    "transaction_failures": 0,
}


@dataclass(frozen=True)
class AnalysisResult:
    """Kafka records produced from one input sensor event."""

    trace_id: str
    sensor_data: SensorData
    insight: Insight
    insight_event: Dict[str, Any]
    action_plan_event: Optional[Dict[str, Any]]


def _trace_id_from_headers(message: Any) -> str:
    for key, value in message.headers or []:
        if key == "trace_id" and value:
            try:
                return value.decode("utf-8")
            except (AttributeError, UnicodeDecodeError):
                break
    return generate_trace_id()


def _source_position(message: Any) -> str:
    return f"{message.topic}:{message.partition}:{message.offset}"


def _retry_delay(attempt: int) -> float:
    return min(BASE_RETRY_SECONDS * (2 ** max(attempt - 1, 0)), MAX_RETRY_SECONDS)


async def _analyze_sensor_event(payload: Dict[str, Any], trace_id: str) -> AnalysisResult:
    """Run the existing AI pipeline without producing Kafka side effects."""

    sensor_data = SensorData(**payload)
    logger.info(
        "📥 [%s...] Received: %s - %s: %s",
        trace_id[:20],
        sensor_data.farmId,
        sensor_data.sensorType,
        sensor_data.value,
    )

    weather = (
        await legacy.weather_provider.get_weather()
        if legacy.weather_provider.enabled
        else None
    )
    if weather:
        legacy.local_analyzer.set_weather_context(weather)

    crop_ctx = await legacy.crop_provider.get_crop_context(sensor_data.farmId)
    if crop_ctx and crop_ctx.has_crop_profile:
        legacy.local_analyzer.set_crop_context(crop_ctx)
    else:
        legacy.local_analyzer.set_crop_context(None)

    trend_ctx = None
    try:
        trend_ctx = await legacy.trend_analyzer.get_trend_context(
            sensor_data.farmId, sensor_data.sensorType.lower()
        )
        if trend_ctx and trend_ctx.has_data:
            legacy.local_analyzer.set_trend_context(trend_ctx)
        else:
            legacy.local_analyzer.set_trend_context(None)
    except Exception as exc:
        logger.warning("Trend context fetch failed: %s", exc)
        legacy.local_analyzer.set_trend_context(None)

    insight = legacy.local_analyzer.analyze(sensor_data)
    if insight.status == "ANOMALY" and legacy.cloud_advisor.enabled:
        recommendation = await legacy.cloud_advisor.get_recommendation(
            sensor_data, insight, weather, crop_ctx, trend_ctx
        )
        if recommendation:
            insight.llmRecommendation = recommendation

    severity = {
        "info": Severity.INFO,
        "warning": Severity.WARNING,
        "critical": Severity.CRITICAL,
    }.get(insight.severity, Severity.INFO)

    insight_event = create_insight_event(
        trace_id=trace_id,
        farm_id=insight.farmId,
        sensor_type=insight.sensorType,
        status=(
            InsightStatus.ANOMALY
            if insight.status == "ANOMALY"
            else InsightStatus.NORMAL
        ),
        severity=severity,
        message=insight.message,
        raw_value=insight.rawValue,
        confidence=insight.confidence,
        llm_recommendation=insight.llmRecommendation,
    ).model_dump(mode="json")

    action_plan_event = _build_action_plan_event(
        trace_id, sensor_data, insight
    )

    return AnalysisResult(
        trace_id=trace_id,
        sensor_data=sensor_data,
        insight=insight,
        insight_event=insight_event,
        action_plan_event=action_plan_event,
    )


def _build_action_plan_event(
    trace_id: str, sensor_data: SensorData, insight: Insight
) -> Optional[Dict[str, Any]]:
    if insight.status != "ANOMALY":
        return None

    sensor_type = sensor_data.sensorType.lower()
    if sensor_type not in legacy.ACTION_PLAN_CONFIG:
        return None

    severity = insight.severity.lower()
    severity_key = (
        severity
        if severity in legacy.ACTION_PLAN_CONFIG[sensor_type]
        else "high"
    )
    if severity_key not in legacy.ACTION_PLAN_CONFIG[sensor_type]:
        return None

    config = legacy.ACTION_PLAN_CONFIG[sensor_type][severity_key]
    priority = {
        "warning": Priority.MEDIUM,
        "critical": Priority.HIGH,
    }.get(severity, Priority.MEDIUM)

    return create_action_plan_event(
        trace_id=trace_id,
        farm_id=sensor_data.farmId,
        target_asset_id=config["asset"],
        action_category=config["category"],
        action_type=config["action"],
        reasoning=(
            f"{insight.message}. "
            f"{insight.llmRecommendation or 'Automatic recommendation based on threshold analysis.'}"
        ),
        priority=priority,
        parameters=config.get("params", {}),
        safety_conditions=[
            f"{config['asset']}_device_online",
            "no_maintenance_mode",
            f"{sensor_type}_above_threshold",
        ],
        expires_minutes=30,
    ).model_dump(mode="json")


async def _publish_result_transactionally(
    producer: AIOKafkaProducer,
    message: Any,
    result: AnalysisResult,
) -> None:
    """Atomically publish outputs and commit the consumed input offset."""

    partition = TopicPartition(message.topic, message.partition)
    offsets = {partition: message.offset + 1}
    headers = [("trace_id", result.trace_id.encode("utf-8"))]
    key = result.sensor_data.farmId.encode("utf-8")

    async with producer.transaction():
        await producer.send_and_wait(
            legacy.OUTPUT_TOPIC,
            value=result.insight_event,
            key=key,
            headers=headers,
        )
        if result.action_plan_event is not None:
            await producer.send_and_wait(
                legacy.ACTION_PLAN_TOPIC,
                value=result.action_plan_event,
                key=key,
                headers=headers,
            )
        await producer.send_offsets_to_transaction(offsets, legacy.CONSUMER_GROUP)


async def _publish_dlt_transactionally(
    producer: AIOKafkaProducer,
    message: Any,
    trace_id: str,
    error: Exception,
    attempts: int,
) -> None:
    """Publish an exhausted input to DLT and commit its offset atomically."""

    partition = TopicPartition(message.topic, message.partition)
    offsets = {partition: message.offset + 1}
    dlt_event = {
        "specversion": "1.0",
        "type": "terra.cortex.sensor-processing.failed",
        "source": "//terraneuron/terra-cortex",
        "id": generate_trace_id(),
        "time": datetime.now(timezone.utc).isoformat(),
        "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id,
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
    headers = [
        ("trace_id", trace_id.encode("utf-8")),
        ("x-original-topic", message.topic.encode("utf-8")),
        ("x-exception-type", type(error).__name__.encode("utf-8")),
    ]

    async with producer.transaction():
        await producer.send_and_wait(
            DLT_TOPIC,
            value=dlt_event,
            key=message.key,
            headers=headers,
        )
        await producer.send_offsets_to_transaction(offsets, legacy.CONSUMER_GROUP)


async def _accumulate_knowledge_best_effort(result: AnalysisResult) -> None:
    if not legacy.knowledge_collector:
        return
    try:
        legacy.knowledge_collector.accumulate_insight(
            result.insight.model_dump(mode="json")
        )
    except Exception as exc:
        logger.warning("Knowledge accumulation failed after Kafka commit: %s", exc)


async def _process_message(
    message: Any,
    *,
    producer: Optional[AIOKafkaProducer] = None,
    analyze_fn: Callable[[Dict[str, Any], str], Awaitable[AnalysisResult]] = _analyze_sensor_event,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_attempts: int = MAX_PROCESSING_ATTEMPTS,
) -> None:
    """Process one record until either success or a committed DLT outcome."""

    active_producer = producer or legacy.producer
    trace_id = _trace_id_from_headers(message)
    analysis_result: Optional[AnalysisResult] = None
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            if analysis_result is None:
                analysis_result = await analyze_fn(message.value, trace_id)
            await _publish_result_transactionally(
                active_producer, message, analysis_result
            )
            _delivery_stats["processed"] += 1
            await _accumulate_knowledge_best_effort(analysis_result)
            logger.info(
                "✅ Kafka transaction committed for %s",
                _source_position(message),
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_error = exc
            _delivery_stats["transaction_failures"] += 1
            if attempt < max_attempts:
                _delivery_stats["retried"] += 1
                delay = _retry_delay(attempt)
                logger.warning(
                    "Processing failed for %s (attempt %s/%s): %s; retrying in %.1fs",
                    _source_position(message),
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                await sleep_fn(delay)

    assert last_error is not None
    dlt_attempt = 0
    while True:
        dlt_attempt += 1
        try:
            await _publish_dlt_transactionally(
                active_producer,
                message,
                trace_id,
                last_error,
                max_attempts,
            )
            _delivery_stats["dead_lettered"] += 1
            logger.error(
                "☠️ Dead-lettered %s after %s processing attempts",
                _source_position(message),
                max_attempts,
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception as dlt_error:
            delay = min(_retry_delay(dlt_attempt), MAX_RETRY_SECONDS)
            logger.error(
                "DLT transaction failed for %s: %s; retrying in %.1fs",
                _source_position(message),
                dlt_error,
                delay,
            )
            await sleep_fn(delay)


async def reliable_consume_messages() -> None:
    logger.info(
        "Starting reliable Kafka loop: auto-commit disabled, read_committed, transactional outputs"
    )
    try:
        async for message in legacy.consumer:
            await _process_message(message)
    except asyncio.CancelledError:
        logger.info("Reliable Kafka consumer loop cancelled")
        raise
    except Exception:
        logger.exception("Reliable Kafka consumer loop terminated unexpectedly")
        raise


async def reliable_start_kafka() -> None:
    """Start manual-commit consumer and transactional producer with retries."""

    max_retries = int(os.getenv("KAFKA_START_MAX_RETRIES", "10"))
    retry_delay = float(os.getenv("KAFKA_START_RETRY_SECONDS", "5"))

    for attempt in range(1, max_retries + 1):
        consumer: Optional[AIOKafkaConsumer] = None
        producer: Optional[AIOKafkaProducer] = None
        try:
            consumer = AIOKafkaConsumer(
                bootstrap_servers=legacy.KAFKA_BOOTSTRAP_SERVERS,
                group_id=legacy.CONSUMER_GROUP,
                value_deserializer=lambda data: __import__("json").loads(
                    data.decode("utf-8")
                ),
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                isolation_level="read_committed",
                max_poll_interval_ms=MAX_POLL_INTERVAL_MS,
            )
            consumer.subscribe(
                [legacy.INPUT_TOPIC],
                listener=CONSUMER_REBALANCE_LISTENER,
            )
            producer = AIOKafkaProducer(
                bootstrap_servers=legacy.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda value: __import__("json").dumps(
                    value
                ).encode("utf-8"),
                transactional_id=TRANSACTIONAL_ID,
                transaction_timeout_ms=TRANSACTION_TIMEOUT_MS,
            )
            await consumer.start()
            await producer.start()

            legacy.consumer = consumer
            legacy.producer = producer
            legacy.kafka_task = asyncio.create_task(reliable_consume_messages())
            logger.info(
                "Kafka reliability runtime started: group=%s transactional_id=%s dlt=%s",
                legacy.CONSUMER_GROUP,
                TRANSACTIONAL_ID,
                DLT_TOPIC,
            )
            return
        except Exception as exc:
            logger.warning(
                "Kafka reliability startup attempt %s/%s failed: %s",
                attempt,
                max_retries,
                exc,
            )
            if producer is not None:
                try:
                    await producer.stop()
                except Exception:
                    logger.exception("Failed to stop partial Kafka producer")
            if consumer is not None:
                try:
                    await consumer.stop()
                except Exception:
                    logger.exception("Failed to stop partial Kafka consumer")
            if attempt == max_retries:
                raise
            await asyncio.sleep(retry_delay)


async def reliable_stop_kafka() -> None:
    task = legacy.kafka_task
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(
                "Kafka consumer task had already failed during shutdown: %s",
                type(exc).__name__,
            )

    if legacy.consumer:
        await legacy.consumer.stop()
    if legacy.producer:
        await legacy.producer.stop()

    legacy.kafka_task = None
    legacy.consumer = None
    legacy.producer = None
    logger.info("Reliable Kafka runtime stopped")


# Patch the existing lifespan's global function lookups before uvicorn starts it.
legacy.start_kafka = reliable_start_kafka
legacy.stop_kafka = reliable_stop_kafka
legacy.consume_messages = reliable_consume_messages

app = legacy.app


@app.get("/api/kafka/delivery")
async def kafka_delivery_status() -> Dict[str, Any]:
    task = legacy.kafka_task
    return {
        "consumer_group": legacy.CONSUMER_GROUP,
        "input_topic": legacy.INPUT_TOPIC,
        "output_topic": legacy.OUTPUT_TOPIC,
        "action_plan_topic": legacy.ACTION_PLAN_TOPIC,
        "dlt_topic": DLT_TOPIC,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        "isolation_level": "read_committed",
        "transactional_id": TRANSACTIONAL_ID,
        "consumer_task_running": task is not None and not task.done(),
        "stats": dict(_delivery_stats),
    }
