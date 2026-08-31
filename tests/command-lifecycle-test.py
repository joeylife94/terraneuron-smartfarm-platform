#!/usr/bin/env python3
"""Executable TerraNeuron command-lifecycle proof.

This integration test reuses the Compose stack and proves one physical-device
command path across service boundaries:

MQTT device state -> Kafka action plan -> human approval -> approval-time safety
-> transactional outbox -> Kafka command -> pre-dispatch safety -> MQTT command
-> MQTT terminal ACK -> Kafka feedback -> terminal Terra-Ops plan state.

It is a bounded software proof. It does not claim physical-device or production
safety certification.
"""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests

TERRA_OPS_BASE_URL = os.getenv("TERRA_OPS_BASE_URL", "http://localhost:8080")
TERRA_SENSE_BASE_URL = os.getenv("TERRA_SENSE_BASE_URL", "http://localhost:8081")
E2E_USERNAME = os.getenv("E2E_USERNAME", "admin")
E2E_PASSWORD = os.getenv("E2E_PASSWORD", "admin123")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("E2E_REQUEST_TIMEOUT_SECONDS", "5"))
POLL_TIMEOUT_SECONDS = float(os.getenv("E2E_POLL_TIMEOUT_SECONDS", "90"))
POLL_INTERVAL_SECONDS = float(os.getenv("E2E_POLL_INTERVAL_SECONDS", "1"))


class CommandLifecycleFailure(RuntimeError):
    pass


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def future_rfc3339(minutes: int) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(minutes=minutes))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def response_json(response: requests.Response, operation: str) -> Dict[str, Any]:
    if not response.ok:
        raise CommandLifecycleFailure(
            f"{operation} failed: HTTP {response.status_code} - {response.text}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise CommandLifecycleFailure(
            f"{operation} returned invalid JSON: {response.text}"
        ) from exc
    if not isinstance(payload, dict):
        raise CommandLifecycleFailure(
            f"{operation} returned {type(payload).__name__}, expected object"
        )
    return payload


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login() -> str:
    response = requests.post(
        f"{TERRA_OPS_BASE_URL}/api/auth/login",
        json={"username": E2E_USERNAME, "password": E2E_PASSWORD},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    payload = response_json(response, "terra-ops login")
    token = payload.get("access_token")
    if not token:
        raise CommandLifecycleFailure("terra-ops login omitted access_token")
    return str(token)


def run_container_command(container: str, args: list[str], stdin: str | None = None) -> str:
    completed = subprocess.run(
        ["docker", "exec", "-i", container, *args],
        input=stdin,
        text=True,
        capture_output=True,
        timeout=POLL_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise CommandLifecycleFailure(
            f"docker exec {container} {' '.join(args)} failed with "
            f"{completed.returncode}: stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    return completed.stdout.strip()


def publish_mqtt(topic: str, payload: Dict[str, Any]) -> None:
    run_container_command(
        "terraneuron-mosquitto",
        [
            "mosquitto_pub",
            "-h",
            "localhost",
            "-p",
            "1883",
            "-q",
            "1",
            "-t",
            topic,
            "-m",
            json.dumps(payload, separators=(",", ":")),
        ],
    )


def start_mqtt_command_capture(topic: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            "terraneuron-mosquitto",
            "mosquitto_sub",
            "-h",
            "localhost",
            "-p",
            "1883",
            "-q",
            "1",
            "-t",
            topic,
            "-C",
            "1",
            "-W",
            str(int(POLL_TIMEOUT_SECONDS)),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def publish_action_plan(event: Dict[str, Any]) -> None:
    run_container_command(
        "terraneuron-kafka",
        [
            "kafka-console-producer",
            "--bootstrap-server",
            "localhost:9092",
            "--topic",
            "action-plans",
        ],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def fetch_plan(plan_id: str, token: str) -> requests.Response:
    return requests.get(
        f"{TERRA_OPS_BASE_URL}/api/actions/{plan_id}",
        headers=auth_headers(token),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def wait_for_plan(plan_id: str, token: str) -> Dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = fetch_plan(plan_id, token)
        if response.status_code == 200:
            return response_json(response, "action plan query")
        if response.status_code != 404:
            raise CommandLifecycleFailure(
                f"action plan query failed: HTTP {response.status_code} - {response.text}"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
    raise CommandLifecycleFailure(f"timed out waiting for action plan {plan_id}")


def fetch_device_state(farm_id: str, asset_id: str) -> Dict[str, Any]:
    response = requests.get(
        f"{TERRA_SENSE_BASE_URL}/api/v1/devices/status/{farm_id}/{asset_id}",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response_json(response, "device state query")


def wait_for_device_state(farm_id: str, asset_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        payload = fetch_device_state(farm_id, asset_id)
        if payload.get("state") == "online" and payload.get("deviceType") == "fan":
            return payload
        time.sleep(POLL_INTERVAL_SECONDS)
    raise CommandLifecycleFailure(
        f"timed out waiting for shared device state {farm_id}/{asset_id}"
    )


def wait_for_device_reported_at(
    farm_id: str, asset_id: str, expected_reported_at: str
) -> Dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = fetch_device_state(farm_id, asset_id)
        if latest.get("reportedAt") == expected_reported_at:
            return latest
        time.sleep(POLL_INTERVAL_SECONDS)
    raise CommandLifecycleFailure(
        "timed out waiting for replayed ACK consumption in shared device state: "
        f"expected reportedAt={expected_reported_at} latest={latest}"
    )


def wait_for_terminal_plan(plan_id: str, token: str, command_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = fetch_plan(plan_id, token)
        latest = response_json(response, "terminal action plan query")
        if latest.get("status") == "EXECUTED":
            if latest.get("commandId") != command_id:
                raise CommandLifecycleFailure(
                    "terminal plan commandId mismatch: "
                    f"expected={command_id} actual={latest.get('commandId')}"
                )
            return latest
        if latest.get("status") in {
            "REJECTED",
            "SAFETY_BLOCKED",
            "DISPATCH_FAILED",
            "DELIVERY_FAILED",
            "EXECUTION_FAILED",
            "ACK_TIMEOUT",
            "FAILED",
            "EXPIRED",
        }:
            raise CommandLifecycleFailure(
                f"command lifecycle entered terminal failure state: {latest}"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
    raise CommandLifecycleFailure(
        f"timed out waiting for EXECUTED plan; latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-proof-{run_id}"
    asset_id = f"fan-proof-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-proof-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/8] Authenticate human operator")
    token = login()

    print("[2/8] Publish fresh physical-device state and verify shared registry")
    publish_mqtt(
        status_topic,
        {
            "farmId": farm_id,
            "assetId": asset_id,
            "deviceType": "fan",
            "state": "online",
            "maintenanceMode": False,
            "reportedAt": now_rfc3339(),
        },
    )
    state = wait_for_device_state(farm_id, asset_id)
    print(f"  PASS device state accepted: state={state.get('state')} type={state.get('deviceType')}")

    print("[3/8] Publish action-plan CloudEvent and verify PENDING persistence")
    event = {
        "specversion": "1.0",
        "type": "terra.cortex.plan.generated",
        "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()),
        "time": now_rfc3339(),
        "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id,
            "plan_id": plan_id,
            "plan_type": "input",
            "farm_id": farm_id,
            "target_asset_id": asset_id,
            "target_asset_type": "device",
            "action_category": "ventilation",
            "action_type": "turn_on",
            "parameters": {"duration_minutes": 5, "speed_level": "low"},
            "reasoning": "Bounded executable command-lifecycle proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": now_rfc3339(),
            "expires_at": future_rfc3339(10),
        },
    }
    publish_action_plan(event)
    pending = wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")
    print("  PASS action plan persisted as PENDING")

    print("[4/8] Approve plan; require approval-time safety to pass and command to queue")
    command_capture = start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = requests.post(
        f"{TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=auth_headers(token),
        json={"notes": "command lifecycle proof approval"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    approval_payload = response_json(approval, "action plan approval")
    approval_status = approval_payload.get("planStatus")
    if approval_status not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
        raise CommandLifecycleFailure(
            "approval-time safety did not enter an approved dispatch state: "
            f"{approval_payload}"
        )
    print(
        "  PASS human approval + approval-time safety -> "
        f"{approval_status}/outbox lifecycle"
    )

    print("[5/8] Capture MQTT command after Kafka dispatch and pre-dispatch safety")
    try:
        stdout, stderr = command_capture.communicate(timeout=POLL_TIMEOUT_SECONDS + 10)
    except subprocess.TimeoutExpired as exc:
        command_capture.kill()
        stdout, stderr = command_capture.communicate()
        raise CommandLifecycleFailure(
            f"timed out waiting for MQTT command: stdout={stdout!r} stderr={stderr!r}"
        ) from exc
    if command_capture.returncode != 0:
        raise CommandLifecycleFailure(
            f"MQTT command capture failed with {command_capture.returncode}: {stderr}"
        )
    try:
        command = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise CommandLifecycleFailure(f"MQTT command was invalid JSON: {stdout!r}") from exc
    command_id = command.get("commandId")
    if not command_id:
        raise CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")
    expected_identity = (farm_id, asset_id, plan_id)
    actual_identity = (
        command.get("farmId"),
        command.get("targetAssetId"),
        command.get("planId"),
    )
    if actual_identity != expected_identity:
        raise CommandLifecycleFailure(
            f"MQTT command identity mismatch: expected={expected_identity} actual={actual_identity}"
        )
    print(f"  PASS MQTT command observed: commandId={command_id}")

    print("[6/8] Publish correlated terminal device ACK")
    ack = {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "running",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "EXECUTED",
        "reportedAt": now_rfc3339(),
    }
    publish_mqtt(status_topic, ack)

    print("[7/8] Verify ACK feedback reaches Terra-Ops terminal lifecycle")
    terminal = wait_for_terminal_plan(plan_id, token, command_id)
    if terminal.get("executionResult") != "DEVICE_CONFIRMED":
        raise CommandLifecycleFailure(
            f"terminal plan executionResult mismatch: {terminal.get('executionResult')}"
        )
    print(
        "  PASS complete command lifecycle: "
        f"plan={plan_id} command={command_id} status={terminal.get('status')}"
    )

    print("[8/8] Replay terminal ACK and verify idempotent terminal state")
    duplicate_ack = dict(ack)
    replay_reported_at = now_rfc3339()
    duplicate_ack["reportedAt"] = replay_reported_at
    publish_mqtt(status_topic, duplicate_ack)
    replay_state = wait_for_device_reported_at(farm_id, asset_id, replay_reported_at)
    if replay_state.get("lastCommandId") != command_id:
        raise CommandLifecycleFailure(
            "replayed ACK shared state changed command correlation: "
            f"expected={command_id} actual={replay_state.get('lastCommandId')}"
        )
    if replay_state.get("lastCommandStatus") != "EXECUTED":
        raise CommandLifecycleFailure(
            "replayed ACK shared state changed terminal command status: "
            f"{replay_state.get('lastCommandStatus')}"
        )
    replayed = response_json(fetch_plan(plan_id, token), "duplicate ACK plan query")
    if replayed.get("status") != "EXECUTED":
        raise CommandLifecycleFailure(
            f"duplicate terminal ACK regressed plan status: {replayed}"
        )
    if replayed.get("commandId") != command_id:
        raise CommandLifecycleFailure(
            "duplicate terminal ACK changed commandId: "
            f"expected={command_id} actual={replayed.get('commandId')}"
        )
    if replayed.get("executionResult") != "DEVICE_CONFIRMED":
        raise CommandLifecycleFailure(
            "duplicate terminal ACK changed executionResult: "
            f"{replayed.get('executionResult')}"
        )
    print(
        "  PASS duplicate terminal ACK consumed and remains idempotent: "
        f"plan={plan_id} command={command_id} status={replayed.get('status')}"
    )
    print("COMMAND LIFECYCLE GOLDEN PATH PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CommandLifecycleFailure as exc:
        print(f"COMMAND LIFECYCLE GOLDEN PATH FAIL: {exc}", flush=True)
        raise SystemExit(1)
