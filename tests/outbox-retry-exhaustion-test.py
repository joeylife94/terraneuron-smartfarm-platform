#!/usr/bin/env python3
"""Bounded synthetic proof for terminal outbox retry exhaustion."""

import importlib.util
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


def query_outbox(plan_id: str) -> Dict[str, Any]:
    sql = (
        "SELECT status,attempts,command_id,COALESCE(last_error,'') "
        "FROM command_outbox WHERE plan_id='" + plan_id.replace("'", "''") + "';"
    )
    result = subprocess.run(
        [
            *COMPOSE,
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
            f"outbox query failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise cl.CommandLifecycleFailure(f"expected one outbox row for {plan_id}, got {rows}")
    parts = rows[0].split("\t", 3)
    if len(parts) != 4:
        raise cl.CommandLifecycleFailure(f"unexpected outbox row shape: {rows[0]!r}")
    status, attempts, command_id, last_error = parts
    return {
        "status": status,
        "attempts": int(attempts),
        "commandId": command_id,
        "lastError": last_error,
    }


def wait_for_command_id(plan_id: str, token: str) -> Dict[str, Any]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = cl.response_json(cl.fetch_plan(plan_id, token), "retry exhaustion plan query")
        if latest.get("commandId"):
            return latest
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(f"timed out waiting for persisted commandId; latest={latest}")


def wait_for_dead(plan_id: str, token: str, command_id: str, expected_attempts: int) -> tuple[Dict[str, Any], Dict[str, Any]]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest_outbox: Dict[str, Any] = {}
    latest_plan: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest_outbox = query_outbox(plan_id)
        latest_plan = cl.response_json(cl.fetch_plan(plan_id, token), "terminal retry exhaustion plan query")
        if latest_outbox.get("commandId") != command_id:
            raise cl.CommandLifecycleFailure(
                f"outbox command identity changed: expected={command_id} actual={latest_outbox}"
            )
        if latest_plan.get("commandId") != command_id:
            raise cl.CommandLifecycleFailure(
                f"plan command identity changed: expected={command_id} actual={latest_plan}"
            )
        if latest_outbox.get("status") == "DEAD":
            if latest_outbox.get("attempts") != expected_attempts:
                raise cl.CommandLifecycleFailure(
                    f"DEAD attempts did not equal configured limit {expected_attempts}: {latest_outbox}"
                )
            if not latest_outbox.get("lastError"):
                raise cl.CommandLifecycleFailure(f"DEAD outbox omitted persisted error: {latest_outbox}")
            if latest_plan.get("status") != "DISPATCH_FAILED":
                raise cl.CommandLifecycleFailure(f"DEAD outbox did not fail owning plan: {latest_plan}")
            if latest_plan.get("executionResult") != "OUTBOX_DEAD_LETTER":
                raise cl.CommandLifecycleFailure(f"unexpected terminal result: {latest_plan}")
            if not latest_plan.get("executionError"):
                raise cl.CommandLifecycleFailure(f"terminal plan omitted error evidence: {latest_plan}")
            return latest_outbox, latest_plan
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for terminal outbox failure; outbox={latest_outbox} plan={latest_plan}"
    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-outbox-dead-{run_id}"
    asset_id = f"fan-outbox-dead-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-outbox-dead-{run_id}"
    status_topic = f"terra/devices/{farm_id}/{asset_id}/status"
    expected_attempts = 2

    print("[1/8] Authenticate operator")
    token = cl.login()

    print("[2/8] Publish synthetic online device state")
    cl.publish_mqtt(status_topic, {
        "farmId": farm_id,
        "assetId": asset_id,
        "deviceType": "fan",
        "state": "online",
        "maintenanceMode": False,
        "reportedAt": cl.now_rfc3339(),
    })
    cl.wait_for_device_state(farm_id, asset_id)

    print("[3/8] Publish action plan and require PENDING")
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
            "reasoning": "Synthetic outbox retry exhaustion proof",
            "requires_approval": True,
            "priority": "medium",
            "generated_at": cl.now_rfc3339(),
            "expires_at": cl.future_rfc3339(10),
        },
    })
    pending = cl.wait_for_plan(plan_id, token)
    if pending.get("status") != "PENDING":
        raise cl.CommandLifecycleFailure(f"new action plan was not PENDING: {pending}")

    print("[4/8] Stop Kafka before approval")
    stopped = compose("stop", "kafka", check=False)
    if stopped.returncode != 0:
        raise cl.CommandLifecycleFailure(f"failed to stop Kafka: {stopped.stdout}")

    print("[5/8] Approve plan while Kafka is unavailable")
    approval = cl.requests.post(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
        headers=cl.auth_headers(token),
        json={"notes": "Outbox retry exhaustion proof"},
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    cl.response_json(approval, "action plan approval while Kafka unavailable")
    persisted = wait_for_command_id(plan_id, token)
    command_id = persisted.get("commandId")
    if not command_id:
        raise cl.CommandLifecycleFailure(f"approved plan omitted commandId: {persisted}")

    print("[6/8] Require configured retry exhaustion to durable terminal failure")
    terminal_outbox, terminal_plan = wait_for_dead(plan_id, token, command_id, expected_attempts)
    terminal_snapshot = {
        "outbox": terminal_outbox.copy(),
        "planStatus": terminal_plan.get("status"),
        "executionResult": terminal_plan.get("executionResult"),
        "executionError": terminal_plan.get("executionError"),
        "commandId": terminal_plan.get("commandId"),
    }

    print("[7/8] Wait across additional publisher scan cycles and require no resurrection/rewrite")
    time.sleep(4)
    after_outbox = query_outbox(plan_id)
    after_plan = cl.response_json(cl.fetch_plan(plan_id, token), "post-terminal retry exhaustion plan query")
    after_snapshot = {
        "outbox": after_outbox.copy(),
        "planStatus": after_plan.get("status"),
        "executionResult": after_plan.get("executionResult"),
        "executionError": after_plan.get("executionError"),
        "commandId": after_plan.get("commandId"),
    }
    if after_snapshot != terminal_snapshot:
        raise cl.CommandLifecycleFailure(
            f"terminal outbox/plan truth changed after further scans: before={terminal_snapshot} after={after_snapshot}"
        )

    print("[8/8] PASS bounded outbox retry exhaustion proof")
    print({"planId": plan_id, "commandId": command_id, "attempts": after_outbox.get("attempts")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
