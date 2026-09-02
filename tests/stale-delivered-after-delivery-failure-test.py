#!/usr/bin/env python3
"""Bounded proof that stale DELIVERED cannot regress terminal DELIVERY_FAILED."""
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


def wait_for_status(plan_id: str, token: str, expected: set[str]):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(helpers.fetch_plan(plan_id, token), "plan query")
        if latest.get("status") in expected:
            return latest
        if latest.get("status") in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "EXECUTED", "ACK_TIMEOUT", "FAILED", "EXPIRED",
        }:
            raise helpers.CommandLifecycleFailure(f"plan entered unexpected terminal state: {latest}")
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(f"timed out waiting for {expected}; latest={latest}")


def compose(*args: str) -> None:
    completed = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.override.yml", *args],
        cwd=ROOT.parent, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        raise helpers.CommandLifecycleFailure(
            f"docker compose {' '.join(args)} failed: stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-console-producer", "--bootstrap-server", "localhost:9092", "--topic", "terra.control.feedback"],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def dlt_end_offset() -> int:
    topics = helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-topics", "--bootstrap-server", "localhost:9092", "--list"],
    )
    if "terra.control.feedback.DLT" not in topics.splitlines():
        return 0
    completed = subprocess.run(
        ["docker", "exec", "-i", "terraneuron-kafka", "kafka-run-class", "kafka.tools.GetOffsetShell",
         "--bootstrap-server", "localhost:9092", "--topic", "terra.control.feedback.DLT", "--time", "-1"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
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


def wait_for_dlt_increment(before: int) -> int:
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = before
    while time.monotonic() < deadline:
        latest = dlt_end_offset()
        if latest > before:
            return latest
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"stale DELIVERED did not increment terra.control.feedback.DLT; before={before} latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-deliverystale-{run_id}"
    asset_id = f"fan-deliverystale-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-deliverystale-{run_id}"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/9] Authenticate operator and announce synthetic device")
    token = helpers.login()
    helpers.publish_mqtt(status_topic, {
        "farmId": farm_id, "assetId": asset_id, "deviceType": "fan",
        "state": "online", "reportedAt": helpers.now_rfc3339(),
    })
    helpers.wait_for_device_state(farm_id, asset_id)

    print("[2/9] Publish one approval-required plan")
    event = {
        "specversion": "1.0", "type": "terra.cortex.plan.generated", "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()), "time": helpers.now_rfc3339(), "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id, "plan_id": plan_id, "plan_type": "input", "farm_id": farm_id,
            "target_asset_id": asset_id, "target_asset_type": "device", "action_category": "ventilation",
            "action_type": "turn_on", "parameters": {"duration_minutes": 5, "speed_level": "low"},
            "reasoning": "terminal delivery failure stale transport proof", "requires_approval": True,
            "priority": "medium", "generated_at": helpers.now_rfc3339(), "expires_at": helpers.future_rfc3339(10),
        },
    }
    helpers.publish_action_plan(event)
    pending = helpers.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise helpers.CommandLifecycleFailure(f"new plan was not PENDING: {pending}")

    print("[3/9] Stop synthetic MQTT broker before dispatch to force software publish failure")
    compose("stop", "mosquitto")

    print("[4/9] Approve and require terminal MQTT delivery failure")
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token),
        json={"notes": "delivery failure stale transport proof approval"},
        timeout=helpers.REQUEST_TIMEOUT_SECONDS,
    )
    helpers.response_json(approval, "plan approval")
    failed = wait_for_status(plan_id, token, {"DELIVERY_FAILED"})
    command_id = str(failed.get("commandId") or "")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"terminal delivery failure omitted commandId: {failed}")
    if failed.get("executionResult") != "MQTT_DELIVERY_FAILED":
        raise helpers.CommandLifecycleFailure(f"unexpected delivery failure classification: {failed}")
    error = str(failed.get("executionError") or "")
    if not error.startswith("MQTT_PUBLISH_FAILED:"):
        raise helpers.CommandLifecycleFailure(f"unexpected delivery failure evidence: {failed}")
    stable = {key: failed.get(key) for key in STABLE_FIELDS}

    print("[5/9] Restart MQTT broker without restarting Terra-Sense")
    compose("start", "mosquitto")

    print("[6/9] Record DLT end offset before stale transport feedback")
    dlt_before = dlt_end_offset()

    print("[7/9] Publish schema-valid correctly correlated DELIVERED for terminal DELIVERY_FAILED command")
    now = helpers.now_rfc3339()
    publish_feedback({
        "specversion": "1.0", "type": "terra.sense.command.feedback", "source": "//terraneuron/terra-sense",
        "id": str(uuid.uuid4()), "time": now, "datacontenttype": "application/json",
        "data": {
            "trace_id": trace_id, "command_id": command_id, "plan_id": plan_id,
            "farm_id": farm_id, "target_asset_id": asset_id, "status": "DELIVERED",
            "error": "", "timestamp": now,
        },
    })

    print("[8/9] Require stale DELIVERED to traverse configured rejection path")
    dlt_after = wait_for_dlt_increment(dlt_before)
    print(f"  PASS DLT offset advanced from {dlt_before} to {dlt_after}")

    print("[9/9] Verify terminal delivery-failure fields remain unchanged")
    final_plan = helpers.response_json(helpers.fetch_plan(plan_id, token), "final plan query")
    final_fields = {key: final_plan.get(key) for key in STABLE_FIELDS}
    if final_fields != stable:
        raise helpers.CommandLifecycleFailure(
            f"stale DELIVERED mutated terminal delivery failure: before={stable} after={final_fields}"
        )
    print(f"PASS terminal DELIVERY_FAILED truth preserved for command={command_id}")
    print("STALE DELIVERED AFTER DELIVERY FAILURE PROOF PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"STALE DELIVERED AFTER DELIVERY FAILURE PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
