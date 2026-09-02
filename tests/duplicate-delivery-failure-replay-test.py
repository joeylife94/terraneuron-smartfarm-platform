#!/usr/bin/env python3
"""Bounded proof that duplicate terminal DELIVERY_FAILED feedback is idempotent."""

import importlib.util
import json
import subprocess
import sys
import time
import uuid
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


def compose(*args: str) -> None:
    completed = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.override.yml", *args],
        cwd=ROOT.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise helpers.CommandLifecycleFailure(
            f"docker compose {' '.join(args)} failed: stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def wait_for_delivery_failure(plan_id: str, token: str):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(helpers.fetch_plan(plan_id, token), "delivery failure plan query")
        if latest.get("status") == "DELIVERY_FAILED":
            if latest.get("executionResult") != "MQTT_DELIVERY_FAILED":
                raise helpers.CommandLifecycleFailure(f"unexpected delivery failure classification: {latest}")
            error = str(latest.get("executionError") or "")
            if not error.startswith("MQTT_PUBLISH_FAILED:"):
                raise helpers.CommandLifecycleFailure(f"unexpected delivery failure evidence: {latest}")
            if not latest.get("commandId"):
                raise helpers.CommandLifecycleFailure(f"delivery failure omitted commandId: {latest}")
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "EXECUTION_FAILED",
            "EXECUTED", "ACK_TIMEOUT", "FAILED", "EXPIRED",
        }:
            raise helpers.CommandLifecycleFailure(f"plan entered unexpected terminal state: {latest}")
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(f"timed out waiting for DELIVERY_FAILED; latest={latest}")


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-console-producer", "--bootstrap-server", "localhost:9092", "--topic", "terra.control.feedback"],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def feedback_group_lag() -> int | None:
    output = helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-consumer-groups", "--bootstrap-server", "localhost:9092", "--describe", "--group", "terra-ops-group"],
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
    farm_id = f"farm-deliveryreplay-{run_id}"
    asset_id = f"fan-deliveryreplay-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-deliveryreplay-{run_id}"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/8] Authenticate operator and announce synthetic device")
    token = helpers.login()
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "reportedAt": helpers.now_rfc3339(),
    })
    helpers.wait_for_device_state(farm_id, asset_id)

    print("[2/8] Publish one approval-required plan")
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
            "reasoning": "duplicate terminal delivery failure replay proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": helpers.now_rfc3339(),
            "expires_at": helpers.future_rfc3339(10),
        },
    }
    helpers.publish_action_plan(event)
    pending = helpers.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise helpers.CommandLifecycleFailure(f"new plan was not PENDING: {pending}")

    print("[3/8] Stop bounded MQTT broker before dispatch")
    compose("stop", "mosquitto")

    print("[4/8] Approve and require terminal MQTT delivery failure")
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "duplicate delivery failure replay proof approval"},
        timeout=helpers.REQUEST_TIMEOUT_SECONDS,
    )
    helpers.response_json(approval, "plan approval")
    failed = wait_for_delivery_failure(plan_id, token)
    command_id = str(failed["commandId"])
    original_error = str(failed["executionError"])
    stable = {key: failed.get(key) for key in STABLE_FIELDS}

    print("[5/8] Restart MQTT broker without restarting application services")
    compose("start", "mosquitto")

    print("[6/8] Replay distinct schema-valid correlated FAILED feedback")
    replay_error = "MQTT_PUBLISH_FAILED: duplicate replay must not replace first failure"
    if replay_error == original_error:
        raise helpers.CommandLifecycleFailure("replay error unexpectedly equals original failure evidence")
    publish_feedback({
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
            "error": replay_error,
            "timestamp": helpers.now_rfc3339(),
        },
    })

    print("[7/8] Require Terra-Ops feedback consumer catch-up")
    wait_for_feedback_group_caught_up()

    print("[8/8] Verify duplicate FAILED replay preserved first terminal delivery failure")
    replayed = helpers.response_json(helpers.fetch_plan(plan_id, token), "post-replay plan query")
    after = {key: replayed.get(key) for key in STABLE_FIELDS}
    if after != stable:
        raise helpers.CommandLifecycleFailure(
            f"terminal delivery failure fields changed after duplicate FAILED replay: before={stable} after={after}"
        )
    if replayed.get("status") != "DELIVERY_FAILED" or replayed.get("executionResult") != "MQTT_DELIVERY_FAILED":
        raise helpers.CommandLifecycleFailure(f"terminal delivery failure regressed: {replayed}")
    if replayed.get("executionError") != original_error:
        raise helpers.CommandLifecycleFailure(
            f"first failure evidence was replaced: original={original_error!r} actual={replayed.get('executionError')!r}"
        )

    print(
        "  PASS duplicate terminal delivery-failure replay preserved first failure truth: "
        f"plan={plan_id} command={command_id}"
    )
    print("DUPLICATE DELIVERY FAILURE REPLAY PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"DUPLICATE DELIVERY FAILURE REPLAY PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
