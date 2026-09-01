#!/usr/bin/env python3
"""Bounded negative-path proof for MQTT terminal ACK identity correlation.

This proves only the implemented synthetic software boundary: a terminal ACK carrying
an otherwise valid commandId from the wrong asset identity cannot complete another
asset's persisted plan, while a subsequent correctly correlated ACK can.
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


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-neg-{run_id}"
    asset_id = f"fan-neg-{run_id}"
    wrong_asset_id = f"heater-neg-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-neg-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    wrong_status_topic = f"terra/devices/{farm_id}/{wrong_asset_id}/status"

    print("[1/7] Authenticate bounded human operator")
    token = helpers.login()

    print("[2/7] Announce synthetic target device state")
    helpers.publish_mqtt(
        status_topic,
        {
            "farmId": farm_id,
            "assetId": asset_id,
            "deviceType": "fan",
            "state": "online",
            "reportedAt": helpers.now_rfc3339(),
        },
    )
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
            "reasoning": "Mismatched MQTT ACK rejection proof",
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
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "mismatched MQTT ACK rejection proof approval"},
        timeout=helpers.REQUEST_TIMEOUT_SECONDS,
    )
    approval_payload = helpers.response_json(approval, "action plan approval")
    approval_status = approval_payload.get("planStatus")
    if approval_status not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
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
        farm_id,
        asset_id,
        plan_id,
    ):
        raise helpers.CommandLifecycleFailure(f"captured command identity mismatch: {command}")
    print(f"  PASS captured commandId={command_id}")

    print("[5/7] Publish terminal ACK from wrong asset identity")
    wrong_reported_at = helpers.now_rfc3339()
    helpers.publish_mqtt(
        wrong_status_topic,
        {
            "farmId": farm_id,
            "assetId": wrong_asset_id,
            "deviceType": "heater",
            "state": "idle",
            "lastCommandId": command_id,
            "lastCommandStatus": "EXECUTED",
            "lastCommandError": None,
            "reportedAt": wrong_reported_at,
        },
    )
    # Allow the asynchronous MQTT -> Terra-Sense path to process the negative ACK.
    time.sleep(max(2.0, helpers.POLL_INTERVAL_SECONDS * 2))
    after_wrong_ack = helpers.response_json(
        helpers.fetch_plan(plan_id, token), "plan query after mismatched ACK"
    )
    if after_wrong_ack.get("status") == "EXECUTED":
        raise helpers.CommandLifecycleFailure(
            f"mismatched asset ACK incorrectly completed plan: {after_wrong_ack}"
        )
    if after_wrong_ack.get("commandId") not in {None, command_id}:
        raise helpers.CommandLifecycleFailure(
            f"plan commandId changed after mismatched ACK: {after_wrong_ack}"
        )
    print(
        "  PASS mismatched ACK did not complete target plan: "
        f"status={after_wrong_ack.get('status')} command={after_wrong_ack.get('commandId')}"
    )

    print("[6/7] Publish correctly correlated terminal ACK")
    helpers.publish_mqtt(
        status_topic,
        {
            "farmId": farm_id,
            "assetId": asset_id,
            "deviceType": "fan",
            "state": "idle",
            "lastCommandId": command_id,
            "lastCommandStatus": "EXECUTED",
            "lastCommandError": None,
            "reportedAt": helpers.now_rfc3339(),
        },
    )

    print("[7/7] Verify same persisted plan reaches EXECUTED / DEVICE_CONFIRMED")
    terminal = helpers.wait_for_terminal_plan(plan_id, token, str(command_id))
    if terminal.get("executionResult") != "DEVICE_CONFIRMED":
        raise helpers.CommandLifecycleFailure(
            f"terminal plan executionResult mismatch: {terminal.get('executionResult')}"
        )
    print(
        "  PASS identity boundary preserved then valid ACK recovered: "
        f"plan={plan_id} command={command_id} status={terminal.get('status')} "
        f"result={terminal.get('executionResult')}"
    )
    print("MISMATCHED MQTT ACK REJECTION PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MISMATCHED MQTT ACK REJECTION PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
