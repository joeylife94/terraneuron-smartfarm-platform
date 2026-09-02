#!/usr/bin/env python3
"""Bounded proof that real command feedback cannot cross persisted farm/asset ownership."""
import importlib.util, json, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("command_lifecycle", ROOT / "command-lifecycle-test.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load command lifecycle proof helpers")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)

STABLE_FIELDS = (
    "status", "commandId", "deliveredAt", "executedAt",
    "executionResult", "executionError", "ackDeadlineAt",
)


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-console-producer", "--bootstrap-server", "localhost:9092", "--topic", "terra.control.feedback"],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def feedback_event(trace_id: str, command_id: str, plan_id: str, farm_id: str, asset_id: str) -> dict:
    now = helpers.now_rfc3339()
    return {
        "specversion": "1.0",
        "type": "terra.sense.command.feedback",
        "source": "//terraneuron/terra-sense",
        "id": str(uuid.uuid4()),
        "time": now,
        "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id,
            "command_id": command_id,
            "plan_id": plan_id,
            "farm_id": farm_id,
            "target_asset_id": asset_id,
            "status": "EXECUTED",
            "error": "",
            "timestamp": now,
        },
    }


def wait_for_status(plan_id: str, token: str, expected: set[str]):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(helpers.fetch_plan(plan_id, token), "plan query")
        if latest.get("status") in expected:
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "ACK_TIMEOUT", "FAILED", "EXPIRED",
        }:
            raise helpers.CommandLifecycleFailure(f"plan entered unexpected terminal state: {latest}")
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(f"timed out waiting for {expected}; latest={latest}")


def dlt_end_offset() -> int:
    topics = helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-topics", "--bootstrap-server", "localhost:9092", "--list"],
    )
    if "terra.control.feedback.DLT" not in topics.splitlines():
        return 0

    completed = subprocess.run(
        [
            "docker", "exec", "-i", "terraneuron-kafka",
            "kafka-run-class", "kafka.tools.GetOffsetShell",
            "--bootstrap-server", "localhost:9092",
            "--topic", "terra.control.feedback.DLT",
            "--time", "-1",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise helpers.CommandLifecycleFailure(
            f"failed to read DLT end offset: stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )

    total = 0
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        try:
            total += int(line.rsplit(":", 1)[1])
        except ValueError as exc:
            raise helpers.CommandLifecycleFailure(f"unparseable DLT offset line: {line!r}") from exc
    return total


def wait_for_dlt_increment(before: int, label: str) -> int:
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = before
    while time.monotonic() < deadline:
        latest = dlt_end_offset()
        if latest > before:
            return latest
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"{label} feedback did not increment terra.control.feedback.DLT; before={before} latest={latest}"
    )


def assert_plan_unchanged(plan_id: str, token: str, stable: dict, label: str) -> None:
    current = helpers.response_json(helpers.fetch_plan(plan_id, token), f"post-{label} plan query")
    current_fields = {key: current.get(key) for key in STABLE_FIELDS}
    if current_fields != stable:
        raise helpers.CommandLifecycleFailure(
            f"{label} feedback mutated target plan: before={stable} after={current_fields}"
        )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-ownermis-{run_id}"
    asset_id = f"fan-ownermis-{run_id}"
    wrong_farm_id = f"farm-wrong-{run_id}"
    wrong_asset_id = f"fan-wrong-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-ownermis-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/9] Authenticate operator and announce synthetic device")
    token = helpers.login()
    helpers.publish_mqtt(
        status_topic,
        {"farmId": farm_id, "assetId": asset_id, "deviceType": "fan", "state": "online", "reportedAt": helpers.now_rfc3339()},
    )
    helpers.wait_for_device_state(farm_id, asset_id)

    print("[2/9] Publish one approval-required plan")
    event = {
        "specversion": "1.0", "type": "terra.cortex.plan.generated", "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()), "time": helpers.now_rfc3339(), "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id, "plan_id": plan_id, "plan_type": "input", "farm_id": farm_id,
            "target_asset_id": asset_id, "target_asset_type": "device", "action_category": "ventilation",
            "action_type": "turn_on", "parameters": {"duration_minutes": 5, "speed_level": "low"},
            "reasoning": "mismatched farm and asset feedback ownership proof", "requires_approval": True,
            "priority": "medium", "generated_at": helpers.now_rfc3339(), "expires_at": helpers.future_rfc3339(10),
        },
    }
    helpers.publish_action_plan(event)
    pending = helpers.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise helpers.CommandLifecycleFailure(f"new plan was not PENDING: {pending}")

    print("[3/9] Capture actual dispatched command")
    capture = helpers.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "mismatched owner proof approval"},
        timeout=helpers.REQUEST_TIMEOUT_SECONDS,
    )
    helpers.response_json(approval, "plan approval")
    stdout, stderr = capture.communicate(timeout=helpers.POLL_TIMEOUT_SECONDS + 10)
    if capture.returncode != 0:
        raise helpers.CommandLifecycleFailure(f"command capture failed: stdout={stdout!r} stderr={stderr!r}")
    command = json.loads(stdout.strip())
    command_id = str(command.get("commandId") or "")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"captured command omitted commandId: {command}")

    print("[4/9] Establish stable DELIVERED baseline")
    delivered = wait_for_status(plan_id, token, {"DELIVERED"})
    if delivered.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(f"DELIVERED command mismatch: {delivered}")
    stable = {key: delivered.get(key) for key in STABLE_FIELDS}
    dlt_before = dlt_end_offset()

    print("[5/9] Reject feedback with wrong farm_id")
    publish_feedback(feedback_event(trace_id, command_id, plan_id, wrong_farm_id, asset_id))
    dlt_after_farm = wait_for_dlt_increment(dlt_before, "wrong-farm")
    assert_plan_unchanged(plan_id, token, stable, "wrong-farm")
    print(f"DLT offset advanced for wrong farm from {dlt_before} to {dlt_after_farm}")

    print("[6/9] Reject feedback with wrong target_asset_id")
    publish_feedback(feedback_event(trace_id, command_id, plan_id, farm_id, wrong_asset_id))
    dlt_after_asset = wait_for_dlt_increment(dlt_after_farm, "wrong-asset")
    assert_plan_unchanged(plan_id, token, stable, "wrong-asset")
    print(f"DLT offset advanced for wrong asset from {dlt_after_farm} to {dlt_after_asset}")

    print("[7/9] Publish correctly correlated terminal feedback for same command")
    publish_feedback(feedback_event(trace_id, command_id, plan_id, farm_id, asset_id))

    print("[8/9] Verify original plan completes with original commandId")
    executed = wait_for_status(plan_id, token, {"EXECUTED"})
    if executed.get("commandId") != command_id or executed.get("executionResult") != "DEVICE_CONFIRMED":
        raise helpers.CommandLifecycleFailure(f"correct feedback did not complete original plan: {executed}")

    print("[9/9] Report bounded proof result")
    print(f"PASS wrong farm and asset ownership were rejected without mutation; command={command_id}")
    print("MISMATCHED OWNER FEEDBACK REJECTION PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MISMATCHED OWNER FEEDBACK REJECTION PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
