#!/usr/bin/env python3
"""Bounded synthetic proof for terminal ACK recovery across a Terra-Ops restart."""

import importlib.util
import json
import pathlib
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
        [*COMPOSE, *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
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


def wait_for_terra_ops_health() -> None:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest = ""
    while time.monotonic() < deadline:
        try:
            response = cl.requests.get(
                f"{cl.TERRA_OPS_BASE_URL}/actuator/health",
                timeout=cl.REQUEST_TIMEOUT_SECONDS,
            )
            latest = f"status={response.status_code} body={response.text[:500]}"
            if response.ok:
                return
        except cl.requests.RequestException as exc:
            latest = repr(exc)
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    logs = compose("logs", "--tail=120", "terra-ops", check=False).stdout
    raise cl.CommandLifecycleFailure(
        f"terra-ops did not become healthy after restart; latest={latest}; logs={logs}"
    )


def wait_for_recovered_terminal(
    plan_id: str, token: str, command_id: str
) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(
            cl.fetch_plan(plan_id, token), "restart recovery action plan query"
        )
        status = latest.get("status")
        if status == "EXECUTED":
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    f"recovered plan commandId mismatch: expected={command_id} actual={latest.get('commandId')}"
                )
            return latest
        if status in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "FAILED", "EXPIRED",
        }:
            raise cl.CommandLifecycleFailure(
                f"restart recovery entered terminal failure state: {latest}"
            )
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for restart ACK recovery; latest={latest}"
    )


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


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-restart-{run_id}"
    asset_id = f"fan-restart-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-restart-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/10] Authenticate operator")
    token = cl.login()

    print("[2/10] Publish synthetic online device state")
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
            "reasoning": "Synthetic Terra-Ops restart ACK recovery proof",
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
        json={"notes": "restart ACK recovery proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval")
    command = capture_command(command_capture)
    command_id = command.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise cl.CommandLifecycleFailure(f"MQTT command identity mismatch: {command}")

    print("[5/10] Observe DELIVERED with stable command correlation")
    delivered = wait_for_status(plan_id, token, "DELIVERED")
    if delivered.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"DELIVERED changed command correlation: {delivered}")

    print("[6/10] Stop only Terra-Ops")
    result = compose("stop", "terra-ops", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop terra-ops: {result.stdout}")

    print("[7/10] Publish correlated terminal ACK while Terra-Ops is down")
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
        raise cl.CommandLifecycleFailure(f"Terra-Sense ACK correlation mismatch: {consumed_state}")

    print("[8/10] Restart Terra-Ops and require health readiness")
    result = compose("up", "-d", "terra-ops", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to restart terra-ops: {result.stdout}")
    wait_for_terra_ops_health()

    print("[9/10] Verify queued ACK recovers the persisted same plan")
    recovered = wait_for_recovered_terminal(plan_id, token, command_id)
    if recovered.get("executionResult") not in {"DEVICE_CONFIRMED", "DEVICE_CONFIRMED_LATE"}:
        raise cl.CommandLifecycleFailure(f"restart ACK recovery result mismatch: {recovered}")

    print("[10/10] Replay terminal ACK after restart and verify idempotency")
    replay = dict(ack)
    replay_reported_at = cl.now_rfc3339()
    replay["reportedAt"] = replay_reported_at
    cl.publish_mqtt(status_topic, replay)
    replay_state = cl.wait_for_device_reported_at(farm_id, asset_id, replay_reported_at)
    if replay_state.get("lastCommandId") != command_id or replay_state.get("lastCommandStatus") != "EXECUTED":
        raise cl.CommandLifecycleFailure(f"replayed restart ACK state mismatch: {replay_state}")
    time.sleep(cl.POLL_INTERVAL_SECONDS * 2)
    terminal = cl.response_json(cl.fetch_plan(plan_id, token), "restart ACK replay plan query")
    if terminal.get("status") != "EXECUTED" or terminal.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"replayed restart ACK regressed terminal plan: {terminal}")
    if terminal.get("executionResult") != recovered.get("executionResult"):
        raise cl.CommandLifecycleFailure(
            f"replayed restart ACK changed execution result: before={recovered} after={terminal}"
        )

    print("PASS terminal ACK recovery across Terra-Ops restart remains bounded synthetic software evidence")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
