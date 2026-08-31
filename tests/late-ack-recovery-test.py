#!/usr/bin/env python3
"""Bounded synthetic proof for late terminal ACK recovery after ACK_TIMEOUT."""

import importlib.util
import json
import pathlib
import subprocess
import time
import uuid
from typing import Any, Dict

MODULE_PATH = pathlib.Path(__file__).with_name("command-lifecycle-test.py")
spec = importlib.util.spec_from_file_location("command_lifecycle", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load command lifecycle helpers")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


def wait_for_status(plan_id: str, token: str, expected: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), f"wait for {expected}")
        if latest.get("status") == expected:
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "FAILED", "EXPIRED", "EXECUTED",
        }:
            raise cl.CommandLifecycleFailure(
                f"plan reached {latest.get('status')} before {expected}: {latest}"
            )
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for {expected}; latest={latest}"
    )


def wait_for_recovered_terminal(
    plan_id: str, token: str, command_id: str
) -> Dict[str, Any]:
    """Poll through ACK_TIMEOUT until the delayed ACK recovery becomes EXECUTED."""
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(
            cl.fetch_plan(plan_id, token), "late recovery action plan query"
        )
        status = latest.get("status")
        if status == "EXECUTED":
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    "recovered plan commandId mismatch: "
                    f"expected={command_id} actual={latest.get('commandId')}"
                )
            return latest
        if status in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "FAILED", "EXPIRED",
        }:
            raise cl.CommandLifecycleFailure(
                f"late recovery entered terminal failure state: {latest}"
            )
        # ACK_TIMEOUT is the expected pre-recovery state for this proof.
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for late ACK recovery; latest={latest}"
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
        payload = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise cl.CommandLifecycleFailure(f"MQTT command was invalid JSON: {stdout!r}") from exc
    return payload


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-late-{run_id}"
    asset_id = f"fan-late-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-late-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/9] Authenticate operator")
    token = cl.login()

    print("[2/9] Publish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/9] Publish action plan and verify PENDING")
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
            "reasoning": "Synthetic late ACK recovery proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/9] Approve and capture MQTT command")
    command_capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "late ACK recovery proof"},
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

    print("[5/9] Observe DELIVERED before withholding terminal ACK")
    wait_for_status(plan_id, token, "DELIVERED")

    print("[6/9] Observe ACK_TIMEOUT from scheduled timeout scanner")
    timed_out = wait_for_status(plan_id, token, "ACK_TIMEOUT")
    if timed_out.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"ACK_TIMEOUT changed command correlation: {timed_out}")
    if timed_out.get("executionResult") != "DEVICE_ACK_TIMEOUT":
        raise cl.CommandLifecycleFailure(f"unexpected timeout result: {timed_out}")

    print("[7/9] Publish delayed correlated terminal ACK")
    late_reported_at = cl.now_rfc3339()
    ack = {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "running",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "EXECUTED",
        "reportedAt": late_reported_at,
    }
    cl.publish_mqtt(status_topic, ack)
    cl.wait_for_device_reported_at(farm_id, asset_id, late_reported_at)

    print("[8/9] Verify ACK_TIMEOUT recovers to EXECUTED / DEVICE_CONFIRMED_LATE")
    recovered = wait_for_recovered_terminal(plan_id, token, command_id)
    if recovered.get("executionResult") != "DEVICE_CONFIRMED_LATE":
        raise cl.CommandLifecycleFailure(f"late ACK recovery result mismatch: {recovered}")

    print("[9/9] Replay delayed ACK and verify terminal idempotency")
    replay = dict(ack)
    replay_reported_at = cl.now_rfc3339()
    replay["reportedAt"] = replay_reported_at
    cl.publish_mqtt(status_topic, replay)
    replay_state = cl.wait_for_device_reported_at(farm_id, asset_id, replay_reported_at)
    if replay_state.get("lastCommandId") != command_id or replay_state.get("lastCommandStatus") != "EXECUTED":
        raise cl.CommandLifecycleFailure(f"replayed late ACK state mismatch: {replay_state}")
    terminal = cl.response_json(cl.fetch_plan(plan_id, token), "late ACK replay plan query")
    if terminal.get("status") != "EXECUTED" or terminal.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"replayed late ACK regressed terminal plan: {terminal}")
    if terminal.get("executionResult") != "DEVICE_CONFIRMED_LATE":
        raise cl.CommandLifecycleFailure(f"replayed late ACK changed recovery result: {terminal}")

    print("PASS late terminal ACK recovery remains bounded synthetic software evidence")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
