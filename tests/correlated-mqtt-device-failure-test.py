#!/usr/bin/env python3
"""Bounded proof for correlated MQTT terminal device failure propagation.

This proves only the implemented synthetic software boundary: a correctly correlated
terminal FAILED device status is propagated through Terra-Sense/Kafka into Terra-Ops
as truthful execution failure for the same persisted command plan.
"""

import importlib.util
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "command_lifecycle", ROOT / "command-lifecycle-test.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load command lifecycle proof helpers")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


def wait_for_status(plan_id: str, token: str, expected: set[str]):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(
            helpers.fetch_plan(plan_id, token), "action plan status query"
        )
        if latest.get("status") in expected:
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "ACK_TIMEOUT", "FAILED", "EXPIRED",
        }:
            raise helpers.CommandLifecycleFailure(
                f"plan entered unexpected terminal state before device failure proof: {latest}"
            )
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"timed out waiting for status {sorted(expected)}; latest={latest}"
    )


def wait_for_execution_failure(plan_id: str, token: str, command_id: str, error: str):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(
            helpers.fetch_plan(plan_id, token), "execution failure plan query"
        )
        if latest.get("status") == "EXECUTION_FAILED":
            if latest.get("commandId") != command_id:
                raise helpers.CommandLifecycleFailure(
                    f"failed plan commandId mismatch: expected={command_id} actual={latest.get('commandId')}"
                )
            if latest.get("executionResult") != "DEVICE_EXECUTION_FAILED":
                raise helpers.CommandLifecycleFailure(
                    f"executionResult mismatch: {latest.get('executionResult')}"
                )
            if latest.get("executionError") != error:
                raise helpers.CommandLifecycleFailure(
                    f"executionError mismatch: expected={error!r} actual={latest.get('executionError')!r}"
                )
            if latest.get("ackDeadlineAt") is not None:
                raise helpers.CommandLifecycleFailure(
                    f"ACK deadline was not cleared after terminal device failure: {latest}"
                )
            return latest
        if latest.get("status") in {"EXECUTED", "ACK_TIMEOUT", "DELIVERY_FAILED", "FAILED"}:
            raise helpers.CommandLifecycleFailure(
                f"plan reached wrong terminal state for device failure: {latest}"
            )
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"timed out waiting for EXECUTION_FAILED; latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-fail-{run_id}"
    asset_id = f"fan-fail-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-fail-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    device_error = "synthetic motor blocked"

    print("[1/7] Authenticate bounded human operator")
    token = helpers.login()

    print("[2/7] Announce synthetic target device state")
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "reportedAt": helpers.now_rfc3339(),
    })
    helpers.wait_for_device_state(farm_id, asset_id)
    print("  PASS target synthetic device state is available")

    print("[3/7] Publish action plan and verify PENDING persistence")
    event = {
        "specversion": "1.0",
        "type": "terra.cortex.plan.generated",
        "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()),
        "time": helpers.now_rfc3339(),
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
            "reasoning": "Correlated MQTT device failure proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": helpers.now_rfc3339(),
            "expires_at": helpers.future_rfc3339(10),
        },
    }
    helpers.publish_action_plan(event)
    pending = helpers.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise helpers.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")
    print("  PASS action plan persisted as PENDING")

    print("[4/7] Capture dispatch command and approve plan")
    capture = helpers.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "correlated MQTT device failure proof approval"},
        timeout=helpers.REQUEST_TIMEOUT_SECONDS,
    )
    approval_payload = helpers.response_json(approval, "action plan approval")
    if approval_payload.get("planStatus") not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
        raise helpers.CommandLifecycleFailure(
            f"approval did not enter dispatch lifecycle: {approval_payload}"
        )
    try:
        stdout, stderr = capture.communicate(timeout=helpers.POLL_TIMEOUT_SECONDS + 10)
    except Exception:
        capture.kill()
        stdout, stderr = capture.communicate()
        raise
    if capture.returncode != 0:
        raise helpers.CommandLifecycleFailure(
            f"MQTT command capture failed ({capture.returncode}): stdout={stdout!r} stderr={stderr!r}"
        )
    try:
        command = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise helpers.CommandLifecycleFailure(
            f"captured MQTT command was invalid JSON: {stdout!r}"
        ) from exc
    command_id = command.get("commandId")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise helpers.CommandLifecycleFailure(f"captured command identity mismatch: {command}")
    print(f"  PASS captured commandId={command_id}")

    print("[5/7] Wait until software delivery is established")
    delivered = wait_for_status(plan_id, token, {"DELIVERED"})
    if delivered.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(f"DELIVERED plan commandId mismatch: {delivered}")
    print("  PASS plan reached DELIVERED before terminal device failure")

    print("[6/7] Publish correctly correlated terminal FAILED status")
    reported_at = helpers.now_rfc3339()
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "fault",
        "lastCommandId": command_id,
        "lastCommandStatus": "FAILED",
        "lastCommandError": device_error,
        "reportedAt": reported_at,
    })
    helpers.wait_for_device_reported_at(farm_id, asset_id, reported_at)

    print("[7/7] Verify truthful EXECUTION_FAILED persistence")
    failed = wait_for_execution_failure(plan_id, token, str(command_id), device_error)
    print(
        "  PASS correlated device failure persisted truthfully: "
        f"plan={plan_id} command={command_id} status={failed.get('status')} "
        f"result={failed.get('executionResult')} error={failed.get('executionError')!r}"
    )
    print("CORRELATED MQTT DEVICE FAILURE PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CORRELATED MQTT DEVICE FAILURE PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
