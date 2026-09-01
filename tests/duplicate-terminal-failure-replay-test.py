#!/usr/bin/env python3
"""Bounded proof that replayed correlated terminal FAILED feedback is idempotent.

This proves only the implemented synthetic software boundary. It does not claim
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
            f"ACK deadline unexpectedly present after terminal failure: {plan}"
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


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        [
            "kafka-console-producer",
            "--bootstrap-server", "localhost:9092",
            "--topic", "terra.control.feedback",
        ],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def feedback_group_lag() -> int | None:
    output = helpers.run_container_command(
        "terraneuron-kafka",
        [
            "kafka-consumer-groups",
            "--bootstrap-server", "localhost:9092",
            "--describe",
            "--group", "terra-ops-group",
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
        current_offset, log_end_offset, lag = parts[3], parts[4], parts[5]
        if lag == "-":
            if current_offset == "-" and log_end_offset == "0":
                continue
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
    farm_id = f"farm-failreplay-{run_id}"
    asset_id = f"fan-failreplay-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-failreplay-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    device_error = "synthetic replayed motor blocked"

    print("[1/9] Authenticate bounded human operator")
    token = helpers.login()

    print("[2/9] Announce synthetic target device state")
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "reportedAt": helpers.now_rfc3339(),
    })
    helpers.wait_for_device_state(farm_id, asset_id)

    print("[3/9] Publish action plan and verify PENDING persistence")
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
            "reasoning": "Duplicate terminal FAILED replay proof",
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

    print("[4/9] Capture real outbound command and approve plan")
    capture = helpers.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "duplicate terminal FAILED replay proof approval"},
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
    command_id = str(command.get("commandId") or "")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"MQTT command omitted commandId: {command}")
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise helpers.CommandLifecycleFailure(f"captured command identity mismatch: {command}")

    print("[5/9] Wait until software delivery is established")
    delivered = wait_for_status(plan_id, token, {"DELIVERED"})
    if delivered.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(f"DELIVERED plan commandId mismatch: {delivered}")

    print("[6/9] Publish first correctly correlated terminal FAILED status")
    first_reported_at = helpers.now_rfc3339()
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "fault",
        "lastCommandId": command_id,
        "lastCommandStatus": "FAILED",
        "lastCommandError": device_error,
        "reportedAt": first_reported_at,
    })
    helpers.wait_for_device_reported_at(farm_id, asset_id, first_reported_at)

    print("[7/9] Capture original persisted terminal failure truth")
    first_failed = wait_for_execution_failure(plan_id, token, command_id, device_error)
    stable_fields = {
        key: first_failed.get(key)
        for key in (
            "status", "commandId", "deliveredAt", "executedAt",
            "executionResult", "executionError", "ackDeadlineAt",
        )
    }

    print("[8/9] Replay schema-valid terminal FAILED directly through Terra-Ops Kafka consumer")
    replay = {
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
            "status": "FAILED",
            "error": device_error,
            "timestamp": helpers.now_rfc3339(),
        },
    }
    publish_feedback(replay)
    wait_for_feedback_group_caught_up()

    print("[9/9] Verify duplicate FAILED replay did not rewrite terminal truth")
    replayed = helpers.response_json(
        helpers.fetch_plan(plan_id, token), "post-replay plan query"
    )
    assert_failure_truth(replayed, command_id, device_error)
    replay_fields = {key: replayed.get(key) for key in stable_fields}
    if replay_fields != stable_fields:
        raise helpers.CommandLifecycleFailure(
            f"terminal failure fields changed after duplicate FAILED replay: before={stable_fields} after={replay_fields}"
        )

    print(
        "  PASS duplicate terminal FAILED replay preserved terminal truth: "
        f"plan={plan_id} command={command_id} fields={stable_fields}"
    )
    print("DUPLICATE TERMINAL FAILURE REPLAY PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"DUPLICATE TERMINAL FAILURE REPLAY PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
