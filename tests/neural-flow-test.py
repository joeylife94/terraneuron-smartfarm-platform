#!/usr/bin/env python3
"""Authoritative TerraNeuron HTTP -> Kafka -> Cortex -> MySQL E2E test."""

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List

import requests

TERRA_SENSE_URL = os.getenv(
    "TERRA_SENSE_URL",
    "http://localhost:8081/api/v1/ingest/sensor-data",
)
TERRA_CORTEX_BASE_URL = os.getenv("TERRA_CORTEX_BASE_URL", "http://localhost:8082")
TERRA_OPS_BASE_URL = os.getenv("TERRA_OPS_BASE_URL", "http://localhost:8080")
TERRA_OPS_API_URL = f"{TERRA_OPS_BASE_URL}/api/v1"

E2E_USERNAME = os.getenv("E2E_USERNAME", "admin")
E2E_PASSWORD = os.getenv("E2E_PASSWORD", "admin123")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("E2E_REQUEST_TIMEOUT_SECONDS", "5"))
POLL_TIMEOUT_SECONDS = float(os.getenv("E2E_POLL_TIMEOUT_SECONDS", "90"))
POLL_INTERVAL_SECONDS = float(os.getenv("E2E_POLL_INTERVAL_SECONDS", "2"))


class E2ETestFailure(RuntimeError):
    pass


def generate_sensor_data(farm_id: str, run_id: str) -> List[Dict]:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        {
            "sensorId": f"e2e-{run_id}-temperature-normal",
            "sensorType": "temperature",
            "value": 25.5,
            "unit": "°C",
            "farmId": farm_id,
            "timestamp": timestamp,
        },
        {
            "sensorId": f"e2e-{run_id}-humidity-normal",
            "sensorType": "humidity",
            "value": 65.0,
            "unit": "%",
            "farmId": farm_id,
            "timestamp": timestamp,
        },
        {
            "sensorId": f"e2e-{run_id}-temperature-anomaly",
            "sensorType": "temperature",
            "value": 35.0,
            "unit": "°C",
            "farmId": farm_id,
            "timestamp": timestamp,
        },
        {
            "sensorId": f"e2e-{run_id}-co2-anomaly",
            "sensorType": "co2",
            "value": 1500.0,
            "unit": "ppm",
            "farmId": farm_id,
            "timestamp": timestamp,
        },
    ]


def response_json(response: requests.Response, operation: str):
    if not response.ok:
        raise E2ETestFailure(
            f"{operation} failed: HTTP {response.status_code} - {response.text}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise E2ETestFailure(
            f"{operation} returned invalid JSON: {response.text}"
        ) from exc


def login() -> str:
    response = requests.post(
        f"{TERRA_OPS_BASE_URL}/api/auth/login",
        json={"username": E2E_USERNAME, "password": E2E_PASSWORD},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    payload = response_json(response, "terra-ops login")
    token = payload.get("access_token")
    if not token:
        raise E2ETestFailure("terra-ops login response did not contain access_token")
    return token


def auth_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def send_sensor_data(data: Dict) -> str:
    response = requests.post(
        TERRA_SENSE_URL,
        json=data,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    payload = response_json(response, f"sensor ingestion for {data['sensorId']}")
    if payload.get("status") != "accepted":
        raise E2ETestFailure(
            f"sensor ingestion acknowledgement was not accepted: {payload}"
        )
    if payload.get("sensorId") != data["sensorId"]:
        raise E2ETestFailure(
            "sensor ingestion acknowledgement identity mismatch: "
            f"expected {data['sensorId']}, got {payload.get('sensorId')}"
        )
    if not payload.get("timestamp"):
        raise E2ETestFailure(
            f"sensor ingestion acknowledgement omitted timestamp: {payload}"
        )
    event_id = payload.get("eventId")
    if not event_id:
        raise E2ETestFailure(
            f"sensor ingestion acknowledgement omitted eventId: {payload}"
        )
    print(
        f"  PASS {data['sensorId']}: "
        f"{data['sensorType']}={data['value']}{data['unit']} eventId={event_id}"
    )
    return event_id


def fetch_farm_insights(farm_id: str, access_token: str) -> List[Dict]:
    response = requests.get(
        f"{TERRA_OPS_API_URL}/insights/farm/{farm_id}",
        headers=auth_headers(access_token),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    payload = response_json(response, "farm insight query")
    if not isinstance(payload, list):
        raise E2ETestFailure(
            f"farm insight query returned {type(payload).__name__}, expected list"
        )
    return payload


def wait_for_insights(
    farm_id: str,
    access_token: str,
    expected_count: int,
    expected_sensor_types: set[str],
) -> List[Dict]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    latest_insights: List[Dict] = []
    while time.monotonic() < deadline:
        latest_insights = fetch_farm_insights(farm_id, access_token)
        observed_types = {
            insight.get("sensorType")
            for insight in latest_insights
            if insight.get("sensorType")
        }
        if (
            len(latest_insights) >= expected_count
            and expected_sensor_types.issubset(observed_types)
        ):
            return latest_insights
        print(
            f"  Waiting: {len(latest_insights)}/{expected_count} insights, "
            f"sensor types={sorted(observed_types)}"
        )
        time.sleep(POLL_INTERVAL_SECONDS)
    raise E2ETestFailure(
        "Timed out waiting for persisted insights: "
        f"received {len(latest_insights)}/{expected_count}, farmId={farm_id}"
    )


def check_deduplication(expected_minimum: int = 1) -> Dict:
    response = requests.get(
        f"{TERRA_CORTEX_BASE_URL}/api/kafka/deduplication",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    payload = response_json(response, "Cortex deduplication status")
    suppressed = payload.get("stats", {}).get("duplicates_suppressed")
    if not isinstance(suppressed, int) or suppressed < expected_minimum:
        raise E2ETestFailure(
            "Cortex did not report duplicate suppression: "
            f"expected >= {expected_minimum}, got {suppressed}"
        )
    return payload


def check_cortex_observability(forbidden_values: List[str]) -> None:
    live_response = requests.get(
        f"{TERRA_CORTEX_BASE_URL}/health/live",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    live = response_json(live_response, "Cortex liveness probe")
    if live.get("status") != "alive":
        raise E2ETestFailure(f"Cortex liveness was not alive: {live}")

    ready_response = requests.get(
        f"{TERRA_CORTEX_BASE_URL}/health/ready",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    ready = response_json(ready_response, "Cortex readiness probe")
    if ready.get("status") != "ready" or set(
        ready.get("components", {}).values()
    ) != {"up"}:
        raise E2ETestFailure(f"Cortex runtime was not fully ready: {ready}")

    metrics_response = requests.get(
        f"{TERRA_CORTEX_BASE_URL}/metrics",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not metrics_response.ok:
        raise E2ETestFailure(
            "Cortex metrics scrape failed: "
            f"HTTP {metrics_response.status_code} - {metrics_response.text}"
        )
    required_metrics = {
        "terra_cortex_events_processed_total",
        "terra_cortex_duplicates_suppressed_total",
        "terra_cortex_events_dead_lettered_total",
        "terra_cortex_kafka_transaction_failures_total",
        "terra_cortex_dedupe_active_markers",
        "terra_cortex_dedupe_marker_follower_up",
        "terra_cortex_dedupe_expiry_sweep_up",
        "terra_cortex_runtime_fatal",
        "terra_cortex_critical_task_failures_total",
        "terra_cortex_process_termination_scheduled",
    }
    missing = [name for name in required_metrics if name not in metrics_response.text]
    if missing:
        raise E2ETestFailure(f"Cortex metrics were missing: {sorted(missing)}")
    leaked = [value for value in forbidden_values if value in metrics_response.text]
    if leaked:
        raise E2ETestFailure("Cortex metrics exposed sensor or event identifiers")


def check_dashboard_summary(access_token: str, expected_minimum: int) -> Dict:
    response = requests.get(
        f"{TERRA_OPS_API_URL}/dashboard/summary",
        headers=auth_headers(access_token),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    summary = response_json(response, "dashboard summary query")
    total_insights = summary.get("totalInsights")
    if not isinstance(total_insights, int) or total_insights < expected_minimum:
        raise E2ETestFailure(
            "dashboard summary totalInsights is inconsistent: "
            f"expected at least {expected_minimum}, got {total_insights}"
        )
    return summary


def run_test() -> None:
    run_id = uuid.uuid4().hex[:12]
    farm_id = f"e2e-farm-{run_id}"
    sensor_data = generate_sensor_data(farm_id, run_id)
    expected_sensor_types = {data["sensorType"] for data in sensor_data}

    print("=" * 72)
    print("TerraNeuron E2E integration test")
    print(f"runId={run_id} farmId={farm_id}")
    print("=" * 72)

    print("\n[1/6] Authenticating against terra-ops")
    access_token = login()
    print(f"  PASS authenticated as {E2E_USERNAME}")

    print("\n[2/6] Sending sensor data and one exact duplicate")
    first_event_id = None
    for data in sensor_data:
        event_id = send_sensor_data(data)
        if first_event_id is None:
            first_event_id = event_id
    duplicate_event_id = send_sensor_data(sensor_data[0])
    if duplicate_event_id != first_event_id:
        raise E2ETestFailure(
            "same sensor measurement produced a different eventId: "
            f"first={first_event_id}, duplicate={duplicate_event_id}"
        )
    print(f"  PASS duplicate reused eventId={duplicate_event_id}")

    print("\n[3/6] Waiting for unique processed insights")
    insights = wait_for_insights(
        farm_id=farm_id,
        access_token=access_token,
        expected_count=len(sensor_data),
        expected_sensor_types=expected_sensor_types,
    )
    time.sleep(POLL_INTERVAL_SECONDS * 2)
    final_insights = fetch_farm_insights(farm_id, access_token)
    if len(final_insights) != len(sensor_data):
        raise E2ETestFailure(
            "duplicate sensor event changed persisted insight count: "
            f"expected {len(sensor_data)}, got {len(final_insights)}"
        )
    print(f"  PASS persisted exactly {len(final_insights)} unique insights")

    print("\n[4/6] Checking Cortex deduplication state")
    dedupe = check_deduplication()
    print(
        "  PASS duplicate suppression: "
        f"topic={dedupe.get('topic')} stats={dedupe.get('stats')}"
    )

    print("\n[5/6] Checking Cortex runtime observability")
    check_cortex_observability(
        [farm_id, first_event_id, duplicate_event_id]
    )
    print("  PASS liveness, readiness, and non-sensitive Prometheus metrics")

    print("\n[6/6] Checking dashboard summary")
    summary = check_dashboard_summary(access_token, expected_minimum=len(insights))
    print(
        "  PASS summary: "
        f"total={summary.get('totalInsights')} "
        f"normal={summary.get('normalInsights')} "
        f"anomaly={summary.get('anomalyInsights')}"
    )

    print("\n" + "=" * 72)
    print("PASS: complete flow with semantic sensor-event deduplication")
    print("=" * 72)


if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        print("\nFAIL: test interrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        sys.exit(1)
