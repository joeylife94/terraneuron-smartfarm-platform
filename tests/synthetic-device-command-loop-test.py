#!/usr/bin/env python3
"""Bounded proof for the reusable synthetic MQTT device actor."""

import importlib.util
import json
import subprocess
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
    farm_id = f"farm-synth-{run_id}"
    asset_id = f"fan-synth-{run_id}"
    # Keep the executable proof inside the repository's accepted action-plan
    # contract: plan_id must match ^plan-[a-z0-9]+$.
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-synth-{run_id}"

    print("[1/6] Authenticate bounded human operator")
    token = helpers.login()

    print("[2/6] Start independent synthetic MQTT device actor")
    actor = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "synthetic-mqtt-device.py"),
            "--farm-id",
            farm_id,
            "--asset-id",
            asset_id,
            "--plan-id",
            plan_id,
            "--device-type",
            "fan",
            "--timeout-seconds",
            str(int(helpers.POLL_TIMEOUT_SECONDS)),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        state = helpers.wait_for_device_state(farm_id, asset_id)
        print(
            "  PASS synthetic actor announced state: "
            f"state={state.get('state')} type={state.get('deviceType')}"
        )

        print("[3/6] Publish action plan and verify PENDING persistence")
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
                "reasoning": "Reusable synthetic MQTT device actor proof",
                "requires_approval": True,
                "priority": "medium",
                "generated_at": helpers.now_rfc3339(),
                "expires_at": helpers.future_rfc3339(10),
            },
        }
        helpers.publish_action_plan(event)
        pending = helpers.wait_for_plan(plan_id, token)
        if pending.get("status") != "PENDING":
            raise helpers.CommandLifecycleFailure(
                f"new action plan was not PENDING: {pending}"
            )
        print("  PASS action plan persisted as PENDING")

        print("[4/6] Approve plan and dispatch toward synthetic actor")
        approval = helpers.requests.post(
            f"{helpers.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
            headers=helpers.auth_headers(token),
            json={"notes": "synthetic device actor proof approval"},
            timeout=helpers.REQUEST_TIMEOUT_SECONDS,
        )
        approval_payload = helpers.response_json(approval, "action plan approval")
        approval_status = approval_payload.get("planStatus")
        if approval_status not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
            raise helpers.CommandLifecycleFailure(
                f"approval did not enter dispatch lifecycle: {approval_payload}"
            )

        print("[5/6] Verify actor consumed command and emitted correlated EXECUTED ACK")
        try:
            stdout, stderr = actor.communicate(timeout=helpers.POLL_TIMEOUT_SECONDS + 20)
        except subprocess.TimeoutExpired as exc:
            actor.kill()
            stdout, stderr = actor.communicate()
            raise helpers.CommandLifecycleFailure(
                f"synthetic actor timed out: stdout={stdout!r} stderr={stderr!r}"
            ) from exc
        if actor.returncode != 0:
            raise helpers.CommandLifecycleFailure(
                f"synthetic actor failed ({actor.returncode}): stdout={stdout!r} stderr={stderr!r}"
            )
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise helpers.CommandLifecycleFailure("synthetic actor emitted no result")
        try:
            actor_result = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise helpers.CommandLifecycleFailure(
                f"synthetic actor result was invalid JSON: {stdout!r}"
            ) from exc
        command_id = actor_result.get("commandId")
        if not command_id or actor_result.get("terminalStatus") != "EXECUTED":
            raise helpers.CommandLifecycleFailure(
                f"synthetic actor result omitted terminal correlation: {actor_result}"
            )
        expected_identity = (farm_id, asset_id, plan_id)
        actual_identity = (
            actor_result.get("farmId"),
            actor_result.get("assetId"),
            actor_result.get("planId"),
        )
        if actual_identity != expected_identity:
            raise helpers.CommandLifecycleFailure(
                f"synthetic actor result identity mismatch: expected={expected_identity} actual={actual_identity}"
            )
        print(f"  PASS actor returned correlated commandId={command_id}")

        print("[6/6] Verify same persisted plan reaches EXECUTED / DEVICE_CONFIRMED")
        terminal = helpers.wait_for_terminal_plan(plan_id, token, str(command_id))
        if terminal.get("executionResult") != "DEVICE_CONFIRMED":
            raise helpers.CommandLifecycleFailure(
                f"terminal plan executionResult mismatch: {terminal.get('executionResult')}"
            )
        print(
            "  PASS reusable synthetic command loop: "
            f"plan={plan_id} command={command_id} status={terminal.get('status')} "
            f"result={terminal.get('executionResult')}"
        )
        print("SYNTHETIC MQTT DEVICE HARNESS PROOF PASS")
        return 0
    finally:
        if actor.poll() is None:
            actor.kill()
            actor.communicate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SYNTHETIC MQTT DEVICE HARNESS PROOF FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
