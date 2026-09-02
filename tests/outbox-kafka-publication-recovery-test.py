#!/usr/bin/env python3
"""Bounded synthetic proof for command-outbox publication recovery after Kafka outage."""

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

COMPOSE: List[str] = [
    "docker", "compose",
    "-f", "docker-compose.yml",
    "-f", "docker-compose.override.yml",
    "-f", "docker-compose.e2e-recovery.yml",
]


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def wait_for_kafka_ready() -> None:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest = ""
    while time.monotonic() < deadline:
        result = compose(
            "exec", "-T", "kafka",
            "kafka-topics", "--bootstrap-server", "localhost:9092", "--list",
            check=False,
        )
        latest = result.stdout
        if result.returncode == 0:
            return
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    logs = compose("logs", "--tail=120", "kafka", check=False).stdout
    raise cl.CommandLifecycleFailure(
        f"kafka did not become ready after restart; latest={latest}; logs={logs}"
    )


def query_outbox(plan_id: str) -> Dict[str, Any]:
    sql = (
        "SELECT status,attempts,command_id,"
        "COALESCE(DATE_FORMAT(published_at,'%Y-%m-%dT%H:%i:%s.%fZ'),''),"
        "COALESCE(last_error,'') "
        "FROM command_outbox WHERE plan_id='" + plan_id.replace("'", "''") + "';"
    )
    result = compose(
        "exec", "-T", "mysql",
        "mysql", "-N", "-B", "-uroot", "-proot", "terra_ops", "-e", sql,
        check=False,
    )
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"outbox query failed: {result.stdout}")
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        return {}
    if len(rows) != 1:
        raise cl.CommandLifecycleFailure(f"expected one outbox row for {plan_id}, got {rows}")
    parts = rows[0].split("\t", 4)
    if len(parts) != 5:
        raise cl.CommandLifecycleFailure(f"unexpected outbox row shape: {rows[0]!r}")
    status, attempts, command_id, published_at, last_error = parts
    return {
        "status": status,
        "attempts": int(attempts),
        "commandId": command_id,
        "publishedAt": published_at,
        "lastError": last_error,
    }


def wait_for_retry_state(plan_id: str, command_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = query_outbox(plan_id)
        if latest:
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    f"outbox command identity changed before recovery: expected={command_id} actual={latest}"
                )
            if latest.get("status") == "DEAD":
                raise cl.CommandLifecycleFailure(f"outbox reached DEAD before Kafka recovery: {latest}")
            if latest.get("attempts", 0) >= 1 and latest.get("status") == "PENDING":
                if not latest.get("lastError"):
                    raise cl.CommandLifecycleFailure(
                        f"outbox retry state omitted persisted failure evidence: {latest}"
                    )
                return latest
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for persisted outbox retry state; latest={latest}"
    )


def wait_for_published_outbox(plan_id: str, command_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = query_outbox(plan_id)
        if latest:
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    f"outbox command identity changed during recovery: expected={command_id} actual={latest}"
                )
            if latest.get("status") == "DEAD":
                raise cl.CommandLifecycleFailure(f"outbox reached DEAD during Kafka recovery: {latest}")
            if latest.get("status") == "PUBLISHED":
                if not latest.get("publishedAt"):
                    raise cl.CommandLifecycleFailure(f"PUBLISHED outbox omitted publishedAt: {latest}")
                return latest
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for PUBLISHED outbox after Kafka recovery; latest={latest}"
    )


def wait_for_command_id(plan_id: str, token: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), "outbox recovery plan query")
        if latest.get("commandId"):
            if latest.get("status") in {
                "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
                "EXECUTION_FAILED", "FAILED", "EXPIRED",
            }:
                raise cl.CommandLifecycleFailure(
                    f"plan entered terminal failure before Kafka recovery: {latest}"
                )
            return latest
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(f"timed out waiting for persisted commandId; latest={latest}")


def capture_command(process: subprocess.Popen[str]) -> Dict[str, Any]:
    try:
        stdout, stderr = process.communicate(timeout=cl.POLL_TIMEOUT_SECONDS + 20)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        raise cl.CommandLifecycleFailure(
            f"timed out waiting for recovered MQTT command: stdout={stdout!r} stderr={stderr!r}"
        ) from exc
    if process.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"recovered MQTT command capture failed with {process.returncode}: {stderr}"
        )
    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise cl.CommandLifecycleFailure(f"recovered MQTT command was invalid JSON: {stdout!r}") from exc


def wait_for_executed(plan_id: str, token: str, command_id: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), "outbox recovery terminal plan query")
        status = latest.get("status")
        if status == "EXECUTED":
            if latest.get("commandId") != command_id:
                raise cl.CommandLifecycleFailure(
                    f"terminal plan commandId changed: expected={command_id} actual={latest}"
                )
            return latest
        if status in {
            "REJECTED", "SAFETY_BLOCKED", "DISPATCH_FAILED", "DELIVERY_FAILED",
            "EXECUTION_FAILED", "FAILED", "EXPIRED",
        }:
            raise cl.CommandLifecycleFailure(
                f"outbox recovery entered terminal failure state: {latest}"
            )
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for EXECUTED after outbox recovery; latest={latest}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-outbox-{run_id}"
    asset_id = f"fan-outbox-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-outbox-{run_id}"
    command_topic = f"terra/devices/{farm_id}/{asset_id}/command"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"

    print("[1/11] Authenticate operator")
    token = cl.login()

    print("[2/11] Publish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/11] Publish action plan while Kafka is available and verify PENDING")
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
            "reasoning": "Synthetic command outbox Kafka publication recovery proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/11] Start MQTT command capture, then stop only Kafka broker")
    command_capture = cl.start_mqtt_command_capture(command_topic)
    time.sleep(0.5)
    result = compose("stop", "kafka", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop Kafka: {result.stdout}")

    print("[5/11] Approve plan while Kafka is unavailable")
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "Outbox Kafka publication recovery proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval while Kafka unavailable")
    persisted = wait_for_command_id(plan_id, token)
    command_id = persisted.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"approved plan omitted persisted commandId: {persisted}")

    print("[6/11] Require one persisted outbox retry without terminal dispatch failure")
    retry_state = wait_for_retry_state(plan_id, command_id)
    if retry_state.get("attempts", 0) < 1:
        raise cl.CommandLifecycleFailure(f"outbox retry evidence missing: {retry_state}")
    latest_plan = cl.response_json(cl.fetch_plan(plan_id, token), "retry-state plan query")
    if latest_plan.get("status") != "DISPATCHING" or latest_plan.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(
            f"plan did not preserve DISPATCHING command identity during outbox retry: {latest_plan}"
        )

    print("[7/11] Restart Kafka and require broker readiness")
    result = compose("up", "-d", "kafka", check=False)
    if result.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to restart Kafka: {result.stdout}")
    wait_for_kafka_ready()

    print("[8/11] Require same outbox row to become PUBLISHED")
    published = wait_for_published_outbox(plan_id, command_id)
    if published.get("attempts", 0) < retry_state.get("attempts", 0):
        raise cl.CommandLifecycleFailure(
            f"published outbox regressed retry count: before={retry_state} after={published}"
        )

    print("[9/11] Capture recovered MQTT command with original identity")
    command = capture_command(command_capture)
    if command.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(
            f"recovered MQTT command replaced commandId: expected={command_id} actual={command}"
        )
    if (command.get("farmId"), command.get("targetAssetId"), command.get("planId")) != (
        farm_id, asset_id, plan_id
    ):
        raise cl.CommandLifecycleFailure(f"recovered MQTT command identity mismatch: {command}")

    print("[10/11] Publish correctly correlated synthetic terminal ACK")
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

    print("[11/11] Require same persisted plan to converge to terminal success")
    terminal = wait_for_executed(plan_id, token, command_id)
    if terminal.get("executionResult") not in {"DEVICE_CONFIRMED", "DEVICE_CONFIRMED_LATE"}:
        raise cl.CommandLifecycleFailure(f"unexpected terminal result after outbox recovery: {terminal}")
    final_outbox = query_outbox(plan_id)
    if final_outbox.get("status") != "PUBLISHED" or final_outbox.get("commandId") != command_id:
        raise cl.CommandLifecycleFailure(f"terminal success changed outbox truth: {final_outbox}")

    print(
        "PASS command outbox publication recovered after bounded Kafka outage "
        "with stable persisted command identity; synthetic software evidence only"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except cl.CommandLifecycleFailure as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
