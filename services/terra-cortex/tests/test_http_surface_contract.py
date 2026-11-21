"""HTTP surface contract for the production Terra-Cortex ASGI application.

These tests drive the real ``src.authenticated_app:app`` (the Docker ``CMD``
target) through the FastAPI/Starlette request stack in-process. Kafka, InfluxDB,
LLM and embedding back-ends are never contacted: requests run without the
lifespan unless a test explicitly enters it with stubbed runtime factories.

They pin the behaviour other components rely on (Docker/Compose health checks,
the CI readiness wait, Prometheus scraping, the dashboard proxy and request
validation) so a web-framework upgrade cannot silently change it.
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST


SERVICE_ROUTES = {
    "/",
    "/health",
    "/info",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/api/kafka/delivery",
    "/api/kafka/deduplication",
    "/api/trends/{farm_id}/{sensor_type}",
    "/api/trends/{farm_id}/{sensor_type}/daily",
    "/api/trends/{farm_id}/{sensor_type}/hourly",
    "/api/knowledge/stats",
    "/api/knowledge/entries",
    "/api/knowledge/collect",
    "/api/knowledge/ingest",
}

READINESS_COMPONENTS = {
    "kafka_consumer",
    "kafka_producer",
    "kafka_consumer_task",
    "dedupe_restore",
    "dedupe_marker_follower",
    "dedupe_expiry_sweep",
}


class FakeTask:
    def done(self):
        return False


class FakeClient:
    _closed = False


def _restore_module(module, snapshot):
    for name in set(vars(module)) - set(snapshot):
        delattr(module, name)
    for name, value in snapshot.items():
        if vars(module).get(name) is not value:
            setattr(module, name, value)


@pytest.fixture(scope="module")
def cortex():
    """Import the production app, then undo its module-level runtime patching.

    ``src.authenticated_app`` installs deduplication, supervision and
    observability by patching ``src.main``/``src.reliable_app`` globals and
    registering routes on the shared app. Restoring them afterwards keeps the
    unit tests of those modules independent of test ordering.
    """

    from src import main as legacy
    from src import reliable_app as reliable

    snapshots = {module: dict(vars(module)) for module in (legacy, reliable)}
    routes = list(legacy.app.router.routes)
    already_imported = "src.authenticated_app" in sys.modules
    production = importlib.import_module("src.authenticated_app")
    try:
        yield SimpleNamespace(
            app=production.app,
            legacy=legacy,
            ledger=production.ledger,
            supervisor=production.supervisor,
        )
    finally:
        if not already_imported:
            sys.modules.pop("src.authenticated_app", None)
            for module, snapshot in snapshots.items():
                _restore_module(module, snapshot)
            legacy.app.router.routes[:] = routes
            legacy.app.openapi_schema = None


@pytest.fixture
def client(cortex):
    # No context manager: the lifespan (Kafka, collectors) is not started.
    return TestClient(cortex.app)


def _mark_runtime_ready(monkeypatch, cortex):
    monkeypatch.setattr(cortex.legacy, "consumer", FakeClient())
    monkeypatch.setattr(cortex.legacy, "producer", FakeClient())
    monkeypatch.setattr(cortex.legacy, "kafka_task", FakeTask())
    monkeypatch.setattr(cortex.ledger, "restore_completed", True)
    monkeypatch.setattr(cortex.ledger, "_follower_task", FakeTask())
    monkeypatch.setattr(cortex.ledger, "_sweep_task", FakeTask())


def test_production_app_is_the_shared_service_app(cortex):
    assert cortex.app is cortex.legacy.app


def test_openapi_schema_and_docs_cover_every_service_route(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Terra-Cortex Hybrid AI Engine"
    assert SERVICE_ROUTES <= set(schema["paths"])
    assert client.get("/docs").status_code == 200


def test_liveness_is_alive_until_supervisor_reports_fatal(client, cortex, monkeypatch):
    alive = client.get("/health/live")

    assert alive.status_code == 200
    assert alive.json() == {"status": "alive", "service": "terra-cortex"}

    monkeypatch.setattr(cortex.supervisor, "fatal_reason", "KAFKA_CONSUMER_TASK_STOPPED")
    fatal = client.get("/health/live")

    assert fatal.status_code == 503
    assert fatal.headers["content-type"] == "application/json"
    assert fatal.json() == {
        "status": "fatal",
        "service": "terra-cortex",
        "reason": "KAFKA_CONSUMER_TASK_STOPPED",
    }


def test_readiness_is_503_until_runtime_components_are_up(client, cortex, monkeypatch):
    not_ready = client.get("/health/ready")

    assert not_ready.status_code == 503
    assert not_ready.headers["content-type"] == "application/json"
    body = not_ready.json()
    assert body["status"] == "not_ready"
    assert body["service"] == "terra-cortex"
    assert body["components"] == {name: "down" for name in READINESS_COMPONENTS}
    assert len(body["reasons"]) == len(READINESS_COMPONENTS)

    _mark_runtime_ready(monkeypatch, cortex)
    ready = client.get("/health/ready")

    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "service": "terra-cortex",
        "components": {name: "up" for name in READINESS_COMPONENTS},
    }


def test_metrics_keep_prometheus_exposition_content_type(client, cortex, monkeypatch):
    down = client.get("/metrics")

    assert down.status_code == 200
    assert down.headers["content-type"] == CONTENT_TYPE_LATEST
    assert "# TYPE terra_cortex_ready gauge" in down.text
    assert "terra_cortex_ready 0.0" in down.text
    assert "terra_cortex_events_processed_total" in down.text

    _mark_runtime_ready(monkeypatch, cortex)

    assert "terra_cortex_ready 1.0" in client.get("/metrics").text


def test_legacy_health_root_and_info_payloads(client):
    health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert health.json()["kafka_consumer_running"] is False

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["service"] == "terra-cortex"

    info = client.get("/info")
    assert info.status_code == 200
    assert info.json()["kafka"]["consumer_group"] == "terra-cortex-group"


def test_kafka_delivery_and_deduplication_status(client):
    delivery = client.get("/api/kafka/delivery")

    assert delivery.status_code == 200
    assert delivery.json()["enable_auto_commit"] is False
    assert delivery.json()["isolation_level"] == "read_committed"
    assert delivery.json()["consumer_task_running"] is False

    dedupe = client.get("/api/kafka/deduplication")
    assert dedupe.status_code == 200
    assert dedupe.json()["enabled"] is True
    assert dedupe.json()["restore"]["completed"] is False


def test_handlers_report_uninitialized_components_instead_of_failing(client):
    trend = client.get("/api/trends/farm-1/temperature", params={"window": "6h"})
    assert trend.status_code == 200
    assert trend.json() == {"error": "Trend analyzer not initialized"}

    ingest = client.post(
        "/api/knowledge/ingest", params={"title": "Night heating", "content": "Close vents."}
    )
    assert ingest.status_code == 200
    assert ingest.json() == {"error": "Knowledge collector not initialized"}


def test_invalid_requests_are_rejected_with_pydantic_validation_errors(client):
    bad_query = client.get("/api/trends/farm-1/temperature/daily", params={"days": "seven"})

    assert bad_query.status_code == 422
    [error] = bad_query.json()["detail"]
    assert error["loc"] == ["query", "days"]
    assert error["type"] == "int_parsing"

    missing = client.post("/api/knowledge/ingest")

    assert missing.status_code == 422
    assert {
        (tuple(error["loc"]), error["type"]) for error in missing.json()["detail"]
    } == {(("query", "title"), "missing"), (("query", "content"), "missing")}


def test_unknown_route_and_wrong_method_responses(client):
    missing = client.get("/does-not-exist")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}

    wrong_method = client.post("/health/ready")
    assert wrong_method.status_code == 405
    assert wrong_method.json() == {"detail": "Method Not Allowed"}


def test_lifespan_starts_and_stops_the_runtime_exactly_once(cortex, monkeypatch):
    legacy = cortex.legacy
    calls = []

    class FakeCollector:
        def get_stats(self):
            return {}

        async def start_auto_collection(self):
            calls.append("collector-start")

        async def close(self):
            calls.append("collector-close")

    async def fake_start_kafka():
        calls.append("kafka-start")
        _mark_runtime_ready(monkeypatch, cortex)

    async def fake_stop_kafka():
        calls.append("kafka-stop")

    disabled = SimpleNamespace(enabled=False, get_stats=lambda: {})
    for name in (
        "local_analyzer",
        "cloud_advisor",
        "weather_provider",
        "crop_provider",
        "trend_analyzer",
        "knowledge_collector",
    ):
        monkeypatch.setattr(legacy, name, None)
    monkeypatch.setattr(legacy, "LocalAnalyzer", lambda: SimpleNamespace(get_stats=lambda: {}))
    monkeypatch.setattr(legacy, "CloudAdvisor", lambda: disabled)
    monkeypatch.setattr(legacy, "get_weather_provider", lambda: disabled)
    monkeypatch.setattr(legacy, "get_crop_profile_provider", lambda: disabled)
    monkeypatch.setattr(
        legacy, "get_timeseries_analyzer", lambda: SimpleNamespace(get_config=lambda: {})
    )
    monkeypatch.setattr(legacy, "get_knowledge_collector", FakeCollector)
    monkeypatch.setattr(legacy, "start_kafka", fake_start_kafka)
    monkeypatch.setattr(legacy, "stop_kafka", fake_stop_kafka)

    with TestClient(cortex.app) as client:
        assert calls == ["kafka-start", "collector-start"]
        assert client.get("/health/ready").status_code == 200

    assert calls == ["kafka-start", "collector-start", "collector-close", "kafka-stop"]
