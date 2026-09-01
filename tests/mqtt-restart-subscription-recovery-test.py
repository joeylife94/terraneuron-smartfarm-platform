#!/usr/bin/env python3
"""Bounded synthetic proof for MQTT reconnect/subscription recovery across broker restart."""

import importlib.util
import json
import pathlib
import socket
import subprocess
import time
import uuid
from typing import Any, Dict, List

MODULE_PATH = pathlib.Path(__file__).with_name("command-lifecycle-test.py")
spec = importlib.util.spec_from_file_location("command_lifecycle", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load command lifecycle helpers")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)

COMPOSE: List[str] = [
    "docker", "compose",
    "-f", "docker-compose.yml",
    "-f", "docker-compose.override.yml",
    "-f", "docker-compose.e2e-recovery.yml",
]


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, *args], check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def wait_for_status(plan_id: str, token: str, expected: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), f"wait for {expected}")
        if latest.get("status") == expected:
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "FAILED", "EXPIRED", "EXECUTED", "ACK_TIMEOUT",
        }:
            raise cl.CommandLifecycleFailure(
                f"plan reached {latest.get('status')} before {expected}: {latest}"
            )
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(f"timed out waiting for {expected}; latest={latest}")


def capture_command(process: subprocess.Popen[str]) -> Dict[str, Any]:
    try:
        stdout, stderr = process.communicate(timeout=cl.POLL_TIMEOUT_SECONDS + 10)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        raise cl.CommandLifecycleFailure(
            f"timed out waiting for MQTT command: stdout={stdout!r} stderr={stderr!r}"
        ) from exc
    if process.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"MQTT command capture failed with {process.returncode}: {stderr}"
        )
    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise cl.CommandLifecycleFailure(f"MQTT command was invalid JSON: {stdout!r}") from exc


def wait_for_mosquitto_ready() -> None:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 1883), timeout=2):
                return
        except OSError:
            time.sleep(cl.POLL_INTERVAL_SECONDS)
    logs = compose("logs", "--tail=120", "mosquitto", check=False).stdout
    raise cl.CommandLifecycleFailure(f"mosquitto did not become ready after restart; logs={logs}")


def wait_for_terra_sense_mqtt_connected() -> None:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            response = cl.requests.get(
                f"{cl.TERRA_SENSE_BASE_URL}/api/v1/devices/mqtt/stats",
                timeout=cl.REQUEST_TIMEOUT_SECONDS,
            )
            latest = cl.response_json(response, "Terra-Sense MQTT stats")
            if latest.get("mqtt_connected") is True:
                return
        except Exception:
            pass
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"Terra-Sense did not report MQTT reconnected after broker restart; latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-mqtt-{run_id}"
    asset_id = f"fan-mqtt-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-mqtt-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/10] Authenticate operator")
    token = cl.login()

    print("[2/10] Establish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/10] Publish action plan and verify PENDING")
    cl.publish_action_plan({
        "specversion": "1.0",
        "type": "terra.cortex.plan.generated",
        "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()),
        "time": cl.now_rfc3339(),
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
            "reasoning": "Synthetic MQTT restart subscription recovery proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/10] Approve and capture MQTT command")
    command_capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "MQTT restart subscription recovery proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval")
    command = capture_command(command_capture)
    command_id = command.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")

    print("[5/10] Observe DELIVERED with stable command correlation")
    delivered = wait_for_status(plan_id, token, "DELIVERED")
    if delivered.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"DELIVERED changed command correlation: {delivered}")

    print("[6/10] Stop only Mosquitto; keep Terra-Sense running")
    result = compose("stop", "mosquitto", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop mosquitto: {result.stdout}")
    time.sleep(max(2.0, cl.POLL_INTERVAL_SECONDS * 2))

    print("[7/10] Restart Mosquitto and require broker plus client reconnect readiness")
    result = compose("up", "-d", "mosquitto", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to restart mosquitto: {result.stdout}")
    wait_for_mosquitto_ready()
    wait_for_terra_sense_mqtt_connected()

    print("[8/10] Publish terminal ACK after reconnect and prove restored subscription consumption")
    ack_reported_at = cl.now_rfc3339()
    ack = {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "running",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "EXECUTED",
        "reportedAt": ack_reported_at,
    }
    cl.publish_mqtt(status_topic, ack)
    consumed_state = cl.wait_for_device_reported_at(farm_id, asset_id, ack_reported_at)
    if consumed_state.get("lastCommandId") != command_id:
        raise cl.CommandLifecycleFailure(f"restored MQTT subscription correlation mismatch: {consumed_state}")

    print("[9/10] Verify same persisted plan reaches EXECUTED")
    terminal = cl.wait_for_terminal_plan(plan_id, token)
    if terminal.get("status") != "EXECUTED" or terminal.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"MQTT reconnect ACK did not reconcile same plan: {terminal}")

    print("[10/10] Replay terminal ACK and verify terminal-state idempotency")
    replay = dict(ack)
    replay_reported_at = cl.now_rfc3339()
    replay["reportedAt"] = replay_reported_at
    cl.publish_mqtt(status_topic, replay)
    replay_state = cl.wait_for_device_reported_at(farm_id, asset_id, replay_reported_at)
    if replay_state.get("lastCommandId") != command_id or replay_state.get("lastCommandStatus") != "EXECUTED":
        raise cl.CommandLifecycleFailure(f"replayed MQTT ACK state mismatch: {replay_state}")
    time.sleep(cl.POLL_INTERVAL_SECONDS * 2)
    replay_terminal = cl.response_json(cl.fetch_plan(plan_id, token), "MQTT replay plan query")
    if replay_terminal.get("status") != "EXECUTED" or replay_terminal.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"replayed MQTT ACK regressed terminal plan: {replay_terminal}")
    if replay_terminal.get("executionResult") != terminal.get("executionResult"):
        raise cl.CommandLifecycleFailure(
            f"replayed MQTT ACK changed execution result: before={terminal} after={replay_terminal}"
        )

    print("PASS MQTT reconnect/subscription recovery remains bounded synthetic software evidence")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
