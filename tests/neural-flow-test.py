#!/usr/bin/env python3
"""
TerraNeuron E2E integration test.

The test sends uniquely identifiable sensor data and verifies the complete flow:
1. HTTP -> terra-sense API
2. terra-sense -> Kafka (raw-sensor-data)
3. terra-cortex -> analysis -> Kafka (processed-insights)
4. terra-ops -> MySQL persistence
5. Authenticated terra-ops API query

Any failed request, missing insight, timeout, or authentication error exits non-zero.
"""

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
TERRA_OPS_BASE_URL = os.getenv("TERRA_OPS_BASE_URL", "http://localhost:8080")
TERRA_OPS_API_URL = f"{TERRA_OPS_BASE_URL}/api/v1"

E2E_USERNAME = os.getenv("E2E_USERNAME", "admin")
E2E_PASSWORD = os.getenv("E2E_PASSWORD", "admin123")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("E2E_REQUEST_TIMEOUT_SECONDS", "5"))
POLL_TIMEOUT_SECONDS = float(os.getenv("E2E_POLL_TIMEOUT_SECONDS", "90"))
POLL_INTERVAL_SECONDS = float(os.getenv("E2E_POLL_INTERVAL_SECONDS", "2"))


class E2ETestFailure(RuntimeError):
    """Raised when an E2E assertion fails."""


def generate_sensor_data(farm_id: str, run_id: str) -> List[Dict]:
    """Generate sensor readings isolated to this test run."""
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
    """Require a successful response and return its JSON body."""
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
    """Authenticate against terra-ops and return an access token."""
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


def send_sensor_data(data: Dict) -> None:
    """Send one sensor reading and validate its acknowledgement identity."""
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
    print(
        f"  PASS {data['sensorId']}: "
        f"{data['sensorType']}={data['value']}{data['unit']}"
    )


def fetch_farm_insights(farm_id: str, access_token: str) -> List[Dict]:
    """Fetch insights for the unique farm used by this run."""
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
    """Poll until all expected insights are persisted or timeout expires."""
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

    observed_types = sorted(
        {
            insight.get("sensorType")
            for insight in latest_insights
            if insight.get("sensorType")
        }
    )
    raise E2ETestFailure(
        "Timed out waiting for persisted insights: "
        f"received {len(latest_insights)}/{expected_count}, "
        f"sensor types={observed_types}, farmId={farm_id}"
    )


def check_dashboard_summary(access_token: str, expected_minimum: int) -> Dict:
    """Verify the authenticated dashboard summary is queryable and coherent."""
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
    """Run authoritative E2E assertions."""
    run_id = uuid.uuid4().hex[:12]
    farm_id = f"e2e-farm-{run_id}"
    sensor_data = generate_sensor_data(farm_id, run_id)
    expected_sensor_types = {data["sensorType"] for data in sensor_data}

    print("=" * 72)
    print("TerraNeuron E2E integration test")
    print(f"runId={run_id} farmId={farm_id}")
    print("=" * 72)

    print("\n[1/4] Authenticating against terra-ops")
    access_token = login()
    print(f"  PASS authenticated as {E2E_USERNAME}")

    print("\n[2/4] Sending sensor data")
    for data in sensor_data:
        send_sensor_data(data)

    print("\n[3/4] Waiting for processed insights")
    insights = wait_for_insights(
        farm_id=farm_id,
        access_token=access_token,
        expected_count=len(sensor_data),
        expected_sensor_types=expected_sensor_types,
    )
    print(f"  PASS persisted {len(insights)} insights for this run")

    print("\n[4/4] Checking dashboard summary")
    summary = check_dashboard_summary(access_token, expected_minimum=len(insights))
    print(
        "  PASS summary: "
        f"total={summary.get('totalInsights')} "
        f"normal={summary.get('normalInsights')} "
        f"anomaly={summary.get('anomalyInsights')}"
    )

    print("\n" + "=" * 72)
    print("PASS: complete HTTP -> Kafka -> Cortex -> Kafka -> MySQL -> API flow")
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
