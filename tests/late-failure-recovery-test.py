#!/usr/bin/env python3
"""Bounded synthetic proof for delayed FAILED recovery after ACK_TIMEOUT."""

import importlib.util
import json
import pathlib
import subprocess
import sys
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
    raise cl.CommandLifecycleFailure(f"timed out waiting for {expected}; latest={latest}")


def wait_for_late_failure(
    plan_id: str, token: str, command_id: str, expected_error: str
) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), "late failure plan query")
        status = latest.get("status")
        if status == "EXECUTION_FAILED":
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    f"late failure commandId mismatch: expected={command_id} actual={latest.get('commandId')}"
                )
            if latest.get("executionResult") != "DEVICE_EXECUTION_FAILED":
                raise cl.CommandLifecycleFailure(f"late failure result mismatch: {latest}")
            if latest.get("executionError") != expected_error:
                raise cl.CommandLifecycleFailure(
                    f"late failure error mismatch: expected={expected_error!r} actual={latest.get('executionError')!r}"
                )
            if latest.get("ackDeadlineAt") is not None:
                raise cl.CommandLifecycleFailure(f"late failure did not clear ACK deadline: {latest}")
            return latest
        if status in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "FAILED", "EXPIRED", "EXECUTED",
        }:
            raise cl.CommandLifecycleFailure(f"late failure entered wrong terminal state: {latest}")
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(f"timed out waiting for late failure recovery; latest={latest}")


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
    farm_id = f"farm-latefail-{run_id}"
    asset_id = f"fan-latefail-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-latefail-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    device_error = "synthetic delayed motor failure"

    print("[1/8] Authenticate operator")
    token = cl.login()

    print("[2/8] Publish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/8] Publish action plan and verify PENDING")
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
            "reasoning": "Synthetic delayed failure recovery proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/8] Approve and capture MQTT command")
    capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "late failure recovery proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval")
    command = capture_command(capture)
    command_id = command.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise cl.CommandLifecycleFailure(f"MQTT command identity mismatch: {command}")

    print("[5/8] Observe DELIVERED")
    delivered = wait_for_status(plan_id, token, "DELIVERED")
    if delivered.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"DELIVERED changed command correlation: {delivered}")

    print("[6/8] Observe ACK_TIMEOUT while terminal status is withheld")
    timed_out = wait_for_status(plan_id, token, "ACK_TIMEOUT")
    if timed_out.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"ACK_TIMEOUT changed command correlation: {timed_out}")
    if timed_out.get("executionResult") != "DEVICE_ACK_TIMEOUT":
        raise cl.CommandLifecycleFailure(f"unexpected timeout result: {timed_out}")

    print("[7/8] Publish delayed correctly correlated terminal FAILED status")
    reported_at = cl.now_rfc3339()
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "fault",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "FAILED",
        "lastCommandError": device_error,
        "reportedAt": reported_at,
    })
    cl.wait_for_device_reported_at(farm_id, asset_id, reported_at)

    print("[8/8] Verify ACK_TIMEOUT converges to truthful EXECUTION_FAILED")
    recovered = wait_for_late_failure(plan_id, token, str(command_id), device_error)
    print(
        "PASS delayed terminal failure recovered bounded software truth: "
        f"plan={plan_id} command={command_id} status={recovered.get('status')} "
        f"result={recovered.get('executionResult')}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"LATE FAILURE RECOVERY PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
