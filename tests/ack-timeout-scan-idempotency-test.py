#!/usr/bin/env python3
"""Bounded synthetic proof that repeated ACK-timeout scans are idempotent."""

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


def fetch_audit(plan_id: str, token: str) -> List[Dict[str, Any]]:
    response = cl.requests.get(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/audit",
        headers=cl.auth_headers(token),
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    payload = cl.response_json(response, "plan audit query")
    if not isinstance(payload, list):
        raise cl.CommandLifecycleFailure(f"plan audit response was not a list: {payload}")
    return payload


def timeout_rows(rows: List[Dict[str, Any]], command_id: str) -> List[Dict[str, Any]]:
    return [
        row for row in rows
        if row.get("eventType") == "COMMAND_TIMEOUT"
        and row.get("entityType") == "command"
        and row.get("entityId") == command_id
    ]


def lifecycle_snapshot(plan: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "status", "commandId", "dispatchedAt", "deliveredAt", "executedAt",
        "ackDeadlineAt", "executionResult", "executionError",
    )
    return {key: plan.get(key) for key in keys}


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-timeout-idem-{run_id}"
    asset_id = f"fan-timeout-idem-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-timeout-idem-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

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

    print("[3/8] Publish approval-required action plan")
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
            "reasoning": "Synthetic ACK timeout scan idempotency proof",
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
    command_capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "ACK timeout scan idempotency proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval")
    command = capture_command(command_capture)
    command_id = command.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")

    print("[5/8] Observe DELIVERED then first ACK_TIMEOUT")
    wait_for_status(plan_id, token, "DELIVERED")
    timed_out = wait_for_status(plan_id, token, "ACK_TIMEOUT")
    if timed_out.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"ACK_TIMEOUT changed command correlation: {timed_out}")
    if timed_out.get("executionResult") != "DEVICE_ACK_TIMEOUT":
        raise cl.CommandLifecycleFailure(f"unexpected timeout result: {timed_out}")

    print("[6/8] Snapshot timeout lifecycle and audit evidence")
    before_snapshot = lifecycle_snapshot(timed_out)
    before_rows = timeout_rows(fetch_audit(plan_id, token), command_id)
    if len(before_rows) != 1:
        raise cl.CommandLifecycleFailure(
            f"expected exactly one COMMAND_TIMEOUT audit row after first timeout, got {len(before_rows)}: {before_rows}"
        )

    print("[7/8] Allow multiple additional timeout scan cycles")
    time.sleep(2.0)

    print("[8/8] Verify timeout state and audit row are idempotent")
    after = cl.response_json(cl.fetch_plan(plan_id, token), "post-repeat timeout plan query")
    after_snapshot = lifecycle_snapshot(after)
    if after_snapshot != before_snapshot:
        raise cl.CommandLifecycleFailure(
            f"repeated timeout scans mutated lifecycle: before={before_snapshot} after={after_snapshot}"
        )
    after_rows = timeout_rows(fetch_audit(plan_id, token), command_id)
    if len(after_rows) != 1:
        raise cl.CommandLifecycleFailure(
            f"repeated timeout scans duplicated COMMAND_TIMEOUT audit evidence: {after_rows}"
        )

    print("PASS repeated ACK timeout scans preserve one bounded timeout transition and one audit row")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
