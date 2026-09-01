#!/usr/bin/env python3
"""Bounded proof that stale DELIVERED feedback cannot overwrite terminal device failure.

This proves only the implemented synthetic software boundary. It establishes one
out-of-order feedback invariant in the running software path and does not claim
physical-device truth or production messaging guarantees.
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
                f"plan entered unexpected terminal state: {latest}"
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
            assert_failure_truth(latest, command_id, error)
            return latest
        if latest.get("status") in {"EXECUTED", "ACK_TIMEOUT", "DELIVERY_FAILED", "FAILED"}:
            raise helpers.CommandLifecycleFailure(
                f"plan reached wrong terminal state: {latest}"
            )
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"timed out waiting for EXECUTION_FAILED; latest={latest}"
    )


def assert_failure_truth(plan: dict, command_id: str, error: str) -> None:
    if plan.get("status") != "EXECUTION_FAILED":
        raise helpers.CommandLifecycleFailure(f"terminal status regressed: {plan}")
    if plan.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(
            f"commandId changed: expected={command_id} actual={plan.get('commandId')}"
        )
    if plan.get("executionResult") != "DEVICE_EXECUTION_FAILED":
        raise helpers.CommandLifecycleFailure(
            f"executionResult changed: {plan.get('executionResult')}"
        )
    if plan.get("executionError") != error:
        raise helpers.CommandLifecycleFailure(
            f"executionError changed: expected={error!r} actual={plan.get('executionError')!r}"
        )
    if plan.get("ackDeadlineAt") is not None:
        raise helpers.CommandLifecycleFailure(
            f"ACK deadline unexpectedly restored after terminal failure: {plan}"
        )


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        [
            "kafka-console-producer",
            "--bootstrap-server",
            "localhost:9092",
            "--topic",
            "terra.control.feedback",
        ],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def feedback_group_lag() -> int | None:
    output = helpers.run_container_command(
        "terraneuron-kafka",
        [
            "kafka-consumer-groups",
            "--bootstrap-server",
            "localhost:9092",
            "--describe",
            "--group",
            "terra-ops-group",
        ],
    )
    total = 0
    found = False
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("GROUP") or line.startswith("Consumer group"):
            continue
        parts = line.split()
        if len(parts) < 6 or parts[1] != "terra.control.feedback":
            continue
        found = True
        lag = parts[5]
        if lag == "-":
            return None
        total += int(lag)
    return total if found else None


def wait_for_feedback_group_caught_up() -> None:
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            last = feedback_group_lag()
        except Exception:
            last = None
        if last == 0:
            return
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"terra-ops-group did not catch up on terra.control.feedback; last lag={last}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-order-{run_id}"
    asset_id = f"fan-order-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-order-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    device_error = "synthetic motor blocked before stale delivery"

    print("[1/8] Authenticate bounded human operator")
    token = helpers.login()

    print("[2/8] Announce synthetic target device state")
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "reportedAt": helpers.now_rfc3339(),
    })
    helpers.wait_for_device_state(farm_id, asset_id)
    print("  PASS synthetic device state available")

    print("[3/8] Publish action plan and verify PENDING persistence")
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
            "reasoning": "Stale DELIVERED ordering proof",
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

    print("[4/8] Capture real outbound command and approve plan")
    capture = helpers.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "stale DELIVERED ordering proof approval"},
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
    command = json.loads(stdout.strip())
    command_id = command.get("commandId")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"captured MQTT command omitted commandId: {command}")
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise helpers.CommandLifecycleFailure(f"captured command identity mismatch: {command}")
    print(f"  PASS captured commandId={command_id}")

    print("[5/8] Establish software delivery, then publish correlated terminal FAILED")
    delivered = wait_for_status(plan_id, token, {"DELIVERED"})
    if delivered.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(f"DELIVERED plan commandId mismatch: {delivered}")
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

    print("[6/8] Verify terminal device failure is persisted")
    wait_for_execution_failure(plan_id, token, str(command_id), device_error)
    print("  PASS plan reached EXECUTION_FAILED with original failure truth")

    print("[7/8] Publish schema-valid stale DELIVERED feedback and wait for consumer catch-up")
    stale = {
        "specversion": "1.0",
        "type": "terra.sense.command.feedback",
        "source": "//terraneuron/terra-sense",
        "id": str(uuid.uuid4()),
        "time": helpers.now_rfc3339(),
        "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id,
            "command_id": command_id,
            "plan_id": plan_id,
            "farm_id": farm_id,
            "target_asset_id": asset_id,
            "status": "DELIVERED",
            "error": "",
            "timestamp": helpers.now_rfc3339(),
        },
    }
    publish_feedback(stale)
    wait_for_feedback_group_caught_up()
    print("  PASS terra-ops-group consumed through current terra.control.feedback end offset")

    print("[8/8] Verify stale transport feedback did not regress terminal failure")
    final_plan = helpers.response_json(
        helpers.fetch_plan(plan_id, token), "final action plan query"
    )
    assert_failure_truth(final_plan, str(command_id), device_error)
    print(
        "  PASS terminal failure truth preserved after stale DELIVERED: "
        f"plan={plan_id} command={command_id} status={final_plan.get('status')}"
    )
    print("STALE DELIVERED AFTER DEVICE FAILURE PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"STALE DELIVERED AFTER DEVICE FAILURE PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
