import asyncio
import json
from types import SimpleNamespace

from prometheus_client import generate_latest

from src import runtime_observability as observability


class FakeTask:
    def __init__(self, done=False):
        self._done = done

    def done(self):
        return self._done


class FakeClient:
    def __init__(self, closed=False):
        self._closed = closed


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def register(fn):
            self.routes[path] = fn
            return fn

        return register


def runtime_state():
    legacy = SimpleNamespace(
        consumer=FakeClient(),
        producer=FakeClient(),
        kafka_task=FakeTask(),
    )
    ledger = SimpleNamespace(
        restore_completed=True,
        _follower_task=FakeTask(),
        _sweep_task=FakeTask(),
        size=12,
        expired_marker_count=4,
        last_restore_duration_ms=1250,
        restore_records_scanned=31,
    )
    reliable = SimpleNamespace(
        app=FakeApp(),
        _delivery_stats={
            "processed": 8,
            "retried": 2,
            "dead_lettered": 1,
            "transaction_failures": 3,
            "duplicates_suppressed": 5,
            "event_id_conflicts": 1,
            "legacy_event_ids_generated": 7,
        },
    )
    return reliable, legacy, ledger


def test_readiness_requires_every_runtime_component():
    _reliable, legacy, ledger = runtime_state()

    payload, status_code = observability.readiness_payload(legacy, ledger)

    assert status_code == 200
    assert payload["status"] == "ready"
    assert "reasons" not in payload
    assert set(payload["components"].values()) == {"up"}


def test_stopped_consumer_task_makes_replica_unready():
    _reliable, legacy, ledger = runtime_state()
    legacy.kafka_task = FakeTask(done=True)

    payload, status_code = observability.readiness_payload(legacy, ledger)

    assert status_code == 503
    assert payload["status"] == "not_ready"
    assert payload["reasons"] == ["KAFKA_CONSUMER_TASK_STOPPED"]
    assert payload["components"]["kafka_consumer_task"] == "down"


def test_restore_in_progress_and_background_failures_are_unready():
    _reliable, legacy, ledger = runtime_state()
    ledger.restore_completed = False
    ledger._follower_task = FakeTask(done=True)
    ledger._sweep_task = None

    payload, status_code = observability.readiness_payload(legacy, ledger)

    assert status_code == 503
    assert payload["reasons"] == [
        "DEDUPE_RESTORE_INCOMPLETE",
        "DEDUPE_MARKER_FOLLOWER_STOPPED",
        "DEDUPE_EXPIRY_SWEEP_STOPPED",
    ]


def test_closed_kafka_clients_are_unready_without_error_details():
    _reliable, legacy, ledger = runtime_state()
    legacy.consumer = FakeClient(closed=True)
    legacy.producer = None

    payload, status_code = observability.readiness_payload(legacy, ledger)
    encoded = json.dumps(payload)

    assert status_code == 503
    assert payload["reasons"][:2] == [
        "KAFKA_CONSUMER_NOT_READY",
        "KAFKA_PRODUCER_NOT_READY",
    ]
    assert "eventId" not in encoded
    assert "fingerprint" not in encoded
    assert "payload" not in encoded


def test_health_endpoints_and_unready_http_status_are_installed_once():
    reliable, legacy, ledger = runtime_state()
    first = observability.install(reliable, legacy, ledger)
    second = observability.install(reliable, legacy, ledger)

    assert first is second
    assert set(reliable.app.routes) == {
        "/health/live",
        "/health/ready",
        "/metrics",
    }
    assert asyncio.run(reliable.app.routes["/health/live"]()) == {
        "status": "alive",
        "service": "terra-cortex",
    }

    legacy.kafka_task = FakeTask(done=True)
    response = asyncio.run(reliable.app.routes["/health/ready"]())
    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["reasons"] == ["KAFKA_CONSUMER_TASK_STOPPED"]

    metrics = asyncio.run(reliable.app.routes["/metrics"]())
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain")
    assert b"terra_cortex_ready 0.0" in metrics.body


def test_fatal_supervisor_makes_liveness_fail_with_safe_reason():
    reliable, legacy, ledger = runtime_state()
    supervisor = SimpleNamespace(
        fatal=True,
        fatal_reason="DEDUPE_MARKER_FOLLOWER_STOPPED",
        critical_task_failures=1,
        termination_scheduled=True,
    )
    observability.install(reliable, legacy, ledger, supervisor)

    response = asyncio.run(reliable.app.routes["/health/live"]())
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body == {
        "status": "fatal",
        "service": "terra-cortex",
        "reason": "DEDUPE_MARKER_FOLLOWER_STOPPED",
    }
    assert "exception" not in response.body.decode("utf-8")


def test_prometheus_metrics_reflect_current_counters_and_runtime_state():
    reliable, legacy, ledger = runtime_state()
    registry = observability.create_metrics_registry(reliable, legacy, ledger)

    output = generate_latest(registry).decode("utf-8")

    assert "terra_cortex_events_processed_total 8.0" in output
    assert "terra_cortex_duplicates_suppressed_total 5.0" in output
    assert "terra_cortex_event_id_conflicts_total 1.0" in output
    assert "terra_cortex_events_dead_lettered_total 1.0" in output
    assert "terra_cortex_kafka_transaction_failures_total 3.0" in output
    assert "terra_cortex_dedupe_active_markers 12.0" in output
    assert "terra_cortex_dedupe_expired_markers_total 4.0" in output
    assert "terra_cortex_dedupe_restore_duration_seconds 1.25" in output
    assert "terra_cortex_dedupe_restore_records_scanned 31.0" in output
    assert "terra_cortex_kafka_consumer_up 1.0" in output
    assert "terra_cortex_dedupe_marker_follower_up 1.0" in output
    assert "terra_cortex_dedupe_expiry_sweep_up 1.0" in output
    assert "terra_cortex_ready 1.0" in output
    assert "terra_cortex_process_start_time_seconds " in output
    assert "eventId" not in output
    assert "fingerprint" not in output

    legacy.kafka_task = FakeTask(done=True)
    updated = generate_latest(registry).decode("utf-8")
    assert "terra_cortex_kafka_consumer_task_up 0.0" in updated
    assert "terra_cortex_ready 0.0" in updated


def test_prometheus_metrics_report_fatal_supervision_state():
    reliable, legacy, ledger = runtime_state()
    supervisor = SimpleNamespace(
        fatal=True,
        fatal_reason="KAFKA_CONSUMER_TASK_STOPPED",
        critical_task_failures=2,
        termination_scheduled=True,
    )
    registry = observability.create_metrics_registry(
        reliable, legacy, ledger, supervisor
    )

    output = generate_latest(registry).decode("utf-8")

    assert "terra_cortex_runtime_fatal 1.0" in output
    assert "terra_cortex_critical_task_failures_total 2.0" in output
    assert "terra_cortex_process_termination_scheduled 1.0" in output
    assert "terra_cortex_process_start_time_seconds " in output
    assert "terra_cortex_ready 0.0" in output
    assert supervisor.fatal_reason not in output
