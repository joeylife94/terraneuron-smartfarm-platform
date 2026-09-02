#!/usr/bin/env python3
"""Bounded proof that a real commandId cannot be acknowledged under a different plan_id."""
import importlib.util, json, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("command_lifecycle", ROOT / "command-lifecycle-test.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load command lifecycle proof helpers")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


def publish_feedback(event: dict) -> None:
    helpers.run_container_command(
        "terraneuron-kafka",
        ["kafka-console-producer", "--bootstrap-server", "localhost:9092", "--topic", "terra.control.feedback"],
        stdin=json.dumps(event, separators=(",", ":")) + "\n",
    )


def wait_for_status(plan_id: str, token: str, expected: set[str]):
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = {}
    while time.monotonic() < deadline:
        latest = helpers.response_json(helpers.fetch_plan(plan_id, token), "plan query")
        if latest.get("status") in expected:
            return latest
        if latest.get("status") in {"REJECTED","SAFETY_BLOCKED","DISPATCH_FAILED","DELIVERY_FAILED","EXECUTION_FAILED","ACK_TIMEOUT","FAILED","EXPIRED"}:
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


def wait_for_dlt_increment(before: int) -> int:
    deadline = time.monotonic() + helpers.POLL_TIMEOUT_SECONDS
    latest = before
    while time.monotonic() < deadline:
        latest = dlt_end_offset()
        if latest > before:
            return latest
        time.sleep(helpers.POLL_INTERVAL_SECONDS)
    raise helpers.CommandLifecycleFailure(
        f"mismatched feedback did not increment terra.control.feedback.DLT; before={before} latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-planmis-{run_id}"
    asset_id = f"fan-planmis-{run_id}"
    plan_id = f"plan-{run_id}"
    wrong_plan_id = f"plan-wrong{run_id}"
    trace_id = f"trace-planmis-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/8] Authenticate operator and announce synthetic device")
    token = helpers.login()
    helpers.publish_mqtt(status_topic, {"farmId":farm_id,"assetId":asset_id,"deviceType":"fan","state":"online","reportedAt":helpers.now_rfc3339()})
    helpers.wait_for_device_state(farm_id, asset_id)

    print("[2/8] Publish one approval-required plan")
    event = {
        "specversion":"1.0","type":"terra.cortex.plan.generated","source":"//terraneuron/terra-cortex",
        "id":str(uuid.uuid4()),"time":helpers.now_rfc3339(),"datacontenttype":"application/json",
        "data":{"trace_id":trace_id,"plan_id":plan_id,"plan_type":"input","farm_id":farm_id,
        "target_asset_id":asset_id,"target_asset_type":"device","action_category":"ventilation","action_type":"turn_on",
        "parameters":{"duration_minutes":5,"speed_level":"low"},"reasoning":"mismatched plan feedback proof",
        "requires_approval":True,"priority":"medium","generated_at":helpers.now_rfc3339(),"expires_at":helpers.future_rfc3339(10)}
    }
    helpers.publish_action_plan(event)
    pending = helpers.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise helpers.CommandLifecycleFailure(f"new plan was not PENDING: {pending}")

    print("[3/8] Capture actual dispatched command")
    capture = helpers.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    approval = helpers.requests.post(
        f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=helpers.auth_headers(token), json={"notes":"mismatched plan proof approval"}, timeout=helpers.REQUEST_TIMEOUT_SECONDS)
    helpers.response_json(approval, "plan approval")
    stdout, stderr = capture.communicate(timeout=helpers.POLL_TIMEOUT_SECONDS + 10)
    if capture.returncode != 0:
        raise helpers.CommandLifecycleFailure(f"command capture failed: stdout={stdout!r} stderr={stderr!r}")
    command = json.loads(stdout.strip())
    command_id = str(command.get("commandId") or "")
    if not command_id:
        raise helpers.CommandLifecycleFailure(f"captured command omitted commandId: {command}")

    print("[4/8] Establish DELIVERED baseline")
    delivered = wait_for_status(plan_id, token, {"DELIVERED"})
    if delivered.get("commandId") != command_id:
        raise helpers.CommandLifecycleFailure(f"DELIVERED command mismatch: {delivered}")
    stable = {k: delivered.get(k) for k in ("status","commandId","deliveredAt","executedAt","executionResult","executionError","ackDeadlineAt")}
    dlt_before = dlt_end_offset()

    print("[5/8] Publish schema-valid feedback with real commandId but wrong plan_id")
    bad = {"specversion":"1.0","type":"terra.sense.command.feedback","source":"//terraneuron/terra-sense","id":str(uuid.uuid4()),
           "time":helpers.now_rfc3339(),"datacontenttype":"application/json","data":{"trace_id":trace_id,"command_id":command_id,
           "plan_id":wrong_plan_id,"farm_id":farm_id,"target_asset_id":asset_id,"status":"EXECUTED","error":"","timestamp":helpers.now_rfc3339()}}
    publish_feedback(bad)

    print("[6/8] Prove rejected feedback reached configured failure path")
    dlt_after = wait_for_dlt_increment(dlt_before)
    after_bad = helpers.response_json(helpers.fetch_plan(plan_id, token), "post-mismatch plan query")
    after_fields = {k: after_bad.get(k) for k in stable}
    if after_fields != stable:
        raise helpers.CommandLifecycleFailure(f"mismatched plan feedback mutated target plan: before={stable} after={after_fields}")
    print(f"DLT offset advanced from {dlt_before} to {dlt_after}")

    print("[7/8] Publish correctly correlated terminal feedback for same command")
    good = {"specversion":"1.0","type":"terra.sense.command.feedback","source":"//terraneuron/terra-sense","id":str(uuid.uuid4()),
            "time":helpers.now_rfc3339(),"datacontenttype":"application/json","data":{"trace_id":trace_id,"command_id":command_id,
            "plan_id":plan_id,"farm_id":farm_id,"target_asset_id":asset_id,"status":"EXECUTED","error":"","timestamp":helpers.now_rfc3339()}}
    publish_feedback(good)

    print("[8/8] Verify original plan completes with original commandId")
    executed = wait_for_status(plan_id, token, {"EXECUTED"})
    if executed.get("commandId") != command_id or executed.get("executionResult") != "DEVICE_CONFIRMED":
        raise helpers.CommandLifecycleFailure(f"correct feedback did not complete original plan: {executed}")
    print(f"PASS mismatched plan identity was rejected without mutation; command={command_id}")
    print("MISMATCHED PLAN FEEDBACK REJECTION PROOF PASS")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MISMATCHED PLAN FEEDBACK REJECTION PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
