"""Runtime health and Prometheus observability for Terra-Cortex.

Readiness is deliberately stricter than process liveness: a Cortex replica must
not receive traffic while its transactional Kafka runtime or any part of the
dedupe ledger maintenance loop is unavailable.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from fastapi import Response
from fastapi.responses import JSONResponse
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily


def _task_running(task: Any) -> bool:
    return task is not None and not task.done()


def _client_running(client: Any) -> bool:
    return client is not None and not bool(getattr(client, "_closed", False))


def runtime_components(legacy: Any, ledger: Any) -> Dict[str, bool]:
    """Return non-sensitive component state used by probes and metrics."""

    return {
        "kafka_consumer": _client_running(getattr(legacy, "consumer", None)),
        "kafka_producer": _client_running(getattr(legacy, "producer", None)),
        "kafka_consumer_task": _task_running(
            getattr(legacy, "kafka_task", None)
        ),
        "dedupe_restore": bool(getattr(ledger, "restore_completed", False)),
        "dedupe_marker_follower": _task_running(
            getattr(ledger, "_follower_task", None)
        ),
        "dedupe_expiry_sweep": _task_running(
            getattr(ledger, "_sweep_task", None)
        ),
    }


_REASON_CODES = {
    "kafka_consumer": "KAFKA_CONSUMER_NOT_READY",
    "kafka_producer": "KAFKA_PRODUCER_NOT_READY",
    "kafka_consumer_task": "KAFKA_CONSUMER_TASK_STOPPED",
    "dedupe_restore": "DEDUPE_RESTORE_INCOMPLETE",
    "dedupe_marker_follower": "DEDUPE_MARKER_FOLLOWER_STOPPED",
    "dedupe_expiry_sweep": "DEDUPE_EXPIRY_SWEEP_STOPPED",
}


def readiness_payload(legacy: Any, ledger: Any) -> tuple[Dict[str, Any], int]:
    components = runtime_components(legacy, ledger)
    reasons = [
        _REASON_CODES[name] for name, running in components.items() if not running
    ]
    payload: Dict[str, Any] = {
        "status": "ready" if not reasons else "not_ready",
        "service": "terra-cortex",
        "components": {
            name: "up" if running else "down"
            for name, running in components.items()
        },
    }
    if reasons:
        payload["reasons"] = reasons
    return payload, 200 if not reasons else 503


def liveness_payload(supervisor: Optional[Any]) -> tuple[Dict[str, str], int]:
    payload = {"status": "alive", "service": "terra-cortex"}
    if supervisor is not None and supervisor.fatal:
        payload = {
            "status": "fatal",
            "service": "terra-cortex",
            "reason": supervisor.fatal_reason,
        }
        return payload, 503
    return payload, 200


def _counter(
    name: str,
    description: str,
    value: int | float,
) -> CounterMetricFamily:
    metric = CounterMetricFamily(name, description)
    metric.add_metric([], value)
    return metric


def _gauge(
    name: str,
    description: str,
    value: int | float,
) -> GaugeMetricFamily:
    metric = GaugeMetricFamily(name, description)
    metric.add_metric([], value)
    return metric


class CortexRuntimeCollector:
    """Collect current runtime state without maintaining duplicate counters."""

    def __init__(
        self,
        reliable: Any,
        legacy: Any,
        ledger: Any,
        supervisor: Optional[Any] = None,
    ):
        self.reliable = reliable
        self.legacy = legacy
        self.ledger = ledger
        self.supervisor = supervisor

    def collect(self) -> Iterable[Any]:
        stats: Mapping[str, int] = self.reliable._delivery_stats
        counters = (
            (
                "terra_cortex_events_processed",
                "Sensor events transactionally processed by Terra-Cortex.",
                "processed",
            ),
            (
                "terra_cortex_event_retries",
                "Terra-Cortex event processing retries.",
                "retried",
            ),
            (
                "terra_cortex_events_dead_lettered",
                "Sensor events committed to the dead-letter topic.",
                "dead_lettered",
            ),
            (
                "terra_cortex_kafka_transaction_failures",
                "Failed Kafka transaction attempts.",
                "transaction_failures",
            ),
            (
                "terra_cortex_duplicates_suppressed",
                "Duplicate sensor events suppressed within the dedupe window.",
                "duplicates_suppressed",
            ),
            (
                "terra_cortex_event_id_conflicts",
                "Conflicting payloads observed for an active event ID.",
                "event_id_conflicts",
            ),
            (
                "terra_cortex_legacy_event_ids_generated",
                "Legacy sensor events for which Cortex generated an event ID.",
                "legacy_event_ids_generated",
            ),
        )
        for name, description, key in counters:
            yield _counter(name, description, stats.get(key, 0))

        components = runtime_components(self.legacy, self.ledger)
        for component, running in components.items():
            yield _gauge(
                f"terra_cortex_{component}_up",
                f"Whether the Terra-Cortex {component} component is running.",
                int(running),
            )

        fatal = bool(self.supervisor is not None and self.supervisor.fatal)
        yield _gauge(
            "terra_cortex_ready",
            "Whether all required Terra-Cortex runtime components are ready.",
            int(all(components.values()) and not fatal),
        )
        yield _gauge(
            "terra_cortex_runtime_fatal",
            "Whether a critical Terra-Cortex background task has terminated.",
            int(fatal),
        )
        yield _counter(
            "terra_cortex_critical_task_failures",
            "Unexpected critical background task exits since process start.",
            (
                self.supervisor.critical_task_failures
                if self.supervisor is not None
                else 0
            ),
        )
        yield _gauge(
            "terra_cortex_process_termination_scheduled",
            "Whether graceful termination is pending after a fatal task exit.",
            int(
                self.supervisor is not None
                and self.supervisor.termination_scheduled
            ),
        )
        yield _gauge(
            "terra_cortex_dedupe_active_markers",
            "Active event IDs held in the in-memory dedupe ledger.",
            self.ledger.size,
        )
        yield _counter(
            "terra_cortex_dedupe_expired_markers",
            "Expired dedupe markers skipped or removed since process start.",
            self.ledger.expired_marker_count,
        )
        yield _gauge(
            "terra_cortex_dedupe_restore_duration_seconds",
            "Duration of the latest dedupe ledger restore.",
            self.ledger.last_restore_duration_ms / 1000,
        )
        yield _gauge(
            "terra_cortex_dedupe_restore_records_scanned",
            "Marker records scanned by the latest dedupe ledger restore.",
            self.ledger.restore_records_scanned,
        )


def create_metrics_registry(
    reliable: Any,
    legacy: Any,
    ledger: Any,
    supervisor: Optional[Any] = None,
) -> CollectorRegistry:
    registry = CollectorRegistry(auto_describe=True)
    registry.register(
        CortexRuntimeCollector(reliable, legacy, ledger, supervisor)
    )
    return registry


def install(
    reliable: Any,
    legacy: Any,
    ledger: Any,
    supervisor: Optional[Any] = None,
) -> CollectorRegistry:
    """Install health probes and metrics exactly once on the Cortex app."""

    existing = getattr(reliable, "_runtime_observability_registry", None)
    if existing is not None:
        return existing

    active_supervisor = supervisor or getattr(
        reliable, "_critical_task_supervisor", None
    )
    registry = create_metrics_registry(
        reliable, legacy, ledger, active_supervisor
    )
    reliable._runtime_observability_registry = registry

    @reliable.app.get("/health/live")
    async def liveness() -> Any:
        payload, status_code = liveness_payload(active_supervisor)
        if status_code == 503:
            return JSONResponse(status_code=status_code, content=payload)
        return payload

    @reliable.app.get("/health/ready")
    async def readiness() -> Any:
        payload, status_code = readiness_payload(legacy, ledger)
        if status_code == 503:
            return JSONResponse(status_code=status_code, content=payload)
        return payload

    @reliable.app.get("/metrics")
    async def metrics() -> Response:
        return Response(
            content=generate_latest(registry),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )

    return registry
