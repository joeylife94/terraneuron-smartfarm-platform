#!/usr/bin/env python3
"""Bounded synthetic proof for stale PROCESSING outbox claim recovery after Terra-Ops restart."""

import importlib.util
import json
import pathlib
import subprocess
import time
import uuid
from typing import Any, Dict

TEST_DIR = pathlib.Path(__file__).parent

cl_spec = importlib.util.spec_from_file_location(
    "command_lifecycle", TEST_DIR / "command-lifecycle-test.py"
)
if cl_spec is None or cl_spec.loader is None:
    raise RuntimeError("could not load command lifecycle helpers")
cl = importlib.util.module_from_spec(cl_spec)
cl_spec.loader.exec_module(cl)

outbox_spec = importlib.util.spec_from_file_location(
    "outbox_recovery", TEST_DIR / "outbox-kafka-publication-recovery-test.py"
)
if outbox_spec is None or outbox_spec.loader is None:
    raise RuntimeError("could not load outbox recovery helpers")
outbox = importlib.util.module_from_spec(outbox_spec)
outbox_spec.loader.exec_module(outbox)


def mysql(sql: str) -> str:
    result = subprocess.run(
        [
            *outbox.COMPOSE,
            "exec", "-T", "-e", "MYSQL_PWD=root", "mysql",
            "mysql", "-N", "-B", "-uroot", "terra_ops", "-e", sql,
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"mysql command failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    return result.stdout.strip()


def inject_stale_processing(plan_id: str, command_id: str) -> Dict[str, Any]:
    escaped_plan = plan_id.replace("'", "''")
    escaped_command = command_id.replace("'", "''")
    mysql(
        "UPDATE command_outbox "
        "SET status='PROCESSING', locked_at=DATE_SUB(UTC_TIMESTAMP(6), INTERVAL 120 SECOND), "
        "next_attempt_at=UTC_TIMESTAMP(6) "
        f"WHERE plan_id='{escaped_plan}' AND command_id='{escaped_command}';"
    )
    row = outbox.query_outbox(plan_id)
    if row.get("status") != "PROCESSING" or row.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"failed to establish stale PROCESSING claim: {row}")
    stale_count = mysql(
        "SELECT COUNT(*) FROM command_outbox "
        f"WHERE plan_id='{escaped_plan}' AND command_id='{escaped_command}' "
        "AND status='PROCESSING' "
        "AND locked_at <= DATE_SUB(UTC_TIMESTAMP(6), INTERVAL 60 SECOND);"
    )
    if stale_count != "1":
        raise cl.CommandLifecycleFailure(
            f"expected exactly one stale PROCESSING claim before restart, count={stale_count!r}"
        )
    return row


def wait_for_service(service: str, url: str) -> None:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest = ""
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--max-time", "5", url],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        latest = result.stdout
        if result.returncode == 0:
            return
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    logs = outbox.compose("logs", "--tail=120", service, check=False).stdout
    raise cl.CommandLifecycleFailure(
        f"{service} did not become ready after restart; latest={latest!r}; logs={logs}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-stale-outbox-{run_id}"
    asset_id = f"fan-stale-outbox-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-stale-outbox-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/13] Authenticate operator")
    token = cl.login()

    print("[2/13] Publish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/13] Publish action plan and require PENDING")
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
            "reasoning": "Synthetic stale command outbox claim recovery proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/13] Stop Kafka before approval")
    result = outbox.compose("stop", "kafka", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop Kafka: {result.stdout}")

    print("[5/13] Approve and require persisted retry with stable command identity")
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "Stale outbox claim recovery proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval while Kafka unavailable")
    persisted = outbox.wait_for_command_id(plan_id, token)
    command_id = persisted.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"approved plan omitted commandId: {persisted}")
    retry = outbox.wait_for_retry_state(plan_id, command_id)

    print("[6/13] Stop Terra-Ops and inject one stale PROCESSING claim")
    result = outbox.compose("stop", "terra-ops", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop Terra-Ops: {result.stdout}")
    stale = inject_stale_processing(plan_id, command_id)
    if stale.get("attempts", 0) < retry.get("attempts", 0):
        raise cl.CommandLifecycleFailure(
            f"stale-claim setup regressed attempts: before={retry} stale={stale}"
        )

    print("[7/13] Start MQTT command capture before broker/service recovery")
    command_capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)

    print("[8/13] Restart Kafka and require readiness")
    result = outbox.compose("up", "-d", "kafka", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to restart Kafka: {result.stdout}")
    outbox.wait_for_kafka_ready()

    print("[9/13] Restart Terra-Ops and require readiness")
    result = outbox.compose("up", "-d", "terra-ops", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to restart Terra-Ops: {result.stdout}")
    wait_for_service("terra-ops", "http://localhost:8080/actuator/health")

    print("[10/13] Require stale claim recovery to publish the same outbox command")
    published = outbox.wait_for_published_outbox(plan_id, command_id)
    if published.get("attempts", 0) < stale.get("attempts", 0):
        raise cl.CommandLifecycleFailure(
            f"recovered outbox regressed attempts: stale={stale} published={published}"
        )
    plan_after_recovery = cl.response_json(
        cl.fetch_plan(plan_id, token), "stale outbox recovery plan query"
    )
    if plan_after_recovery.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(
            f"plan command identity changed after stale-claim recovery: {plan_after_recovery}"
        )
    if plan_after_recovery.get("status") == "DISPATCH_FAILED":
        raise cl.CommandLifecycleFailure(
            f"stale-claim recovery ended in DISPATCH_FAILED: {plan_after_recovery}"
        )

    print("[11/13] Capture recovered MQTT command with original correlation")
    command = outbox.capture_command(command_capture)
    if command.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(
            f"recovered MQTT command replaced commandId: expected={command_id} actual={command}"
        )
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise cl.CommandLifecycleFailure(f"recovered MQTT command correlation mismatch: {command}")

    print("[12/13] Publish correctly correlated synthetic terminal ACK")
    ack_reported_at = cl.now_rfc3339()
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "running",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "EXECUTED",
        "reportedAt": ack_reported_at,
    })
    consumed = cl.wait_for_device_reported_at(farm_id, asset_id, ack_reported_at)
    if consumed.get("lastCommandId") != command_id:
        raise cl.CommandLifecycleFailure(f"terminal ACK correlation mismatch: {consumed}")

    print("[13/13] Require same persisted plan to converge to EXECUTED")
    terminal = outbox.wait_for_executed(plan_id, token, command_id)
    final_outbox = outbox.query_outbox(plan_id)
    if final_outbox.get("status") != "PUBLISHED" or final_outbox.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"terminal success changed outbox truth: {final_outbox}")

    print(
        "PASS stale PROCESSING outbox claim recovered after bounded Terra-Ops restart "
        "with stable persisted command identity; synthetic software evidence only"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
