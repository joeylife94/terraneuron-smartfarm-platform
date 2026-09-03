#!/usr/bin/env python3
"""D2 bounded Synthetic Farm Operations Pilot.

This is a software/demo scenario only. It does not establish physical-device
truth, manufacturer semantics, production messaging trust, field safety,
unattended autonomous control, HA/DR/load maturity, or certification.
"""

import importlib.util
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("command_lifecycle", ROOT / "command-lifecycle-test.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load command lifecycle proof helpers")
cl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cl)

ARTIFACT_DIR = Path("artifacts")
JSON_ARTIFACT = ARTIFACT_DIR / "synthetic-farm-operations-pilot.json"
MARKDOWN_ARTIFACT = ARTIFACT_DIR / "synthetic-farm-operations-pilot.md"


def response_list(response: Any, operation: str) -> List[Dict[str, Any]]:
    if not response.ok:
        raise cl.CommandLifecycleFailure(
            f"{operation} failed: HTTP {response.status_code} - {response.text}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise cl.CommandLifecycleFailure(
            f"{operation} returned invalid JSON: {response.text}"
        ) from exc
    if not isinstance(payload, list):
        raise cl.CommandLifecycleFailure(
            f"{operation} returned {type(payload).__name__}, expected list"
        )
    if any(not isinstance(row, dict) for row in payload):
        raise cl.CommandLifecycleFailure(f"{operation} returned non-object list rows: {payload}")
    return payload


def fetch_pending(token: str) -> List[Dict[str, Any]]:
    response = cl.requests.get(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/pending",
        headers=cl.auth_headers(token),
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    return response_list(response, "operator pending action list")


def fetch_audit(plan_id: str, token: str) -> List[Dict[str, Any]]:
    response = cl.requests.get(
        f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/audit",
        headers=cl.auth_headers(token),
        timeout=cl.REQUEST_TIMEOUT_SECONDS,
    )
    return response_list(response, "plan audit timeline")


def wait_for_complete_audit(plan_id: str, token: str, command_id: str) -> List[Dict[str, Any]]:
    deadline = time.monotonic() + cl.POLL_TIMEOUT_SECONDS
    latest: List[Dict[str, Any]] = []
    while time.monotonic() < deadline:
        latest = fetch_audit(plan_id, token)
        plan_rows = [r for r in latest if r.get("entityType") == "plan" and r.get("entityId") == plan_id]
        command_rows = [r for r in latest if r.get("entityType") == "command" and r.get("entityId") == command_id]
        event_types = {r.get("eventType") for r in latest}
        if plan_rows and command_rows and "PLAN_APPROVED" in event_types and "COMMAND_EXECUTED" in event_types:
            return latest
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for complete plan/command audit timeline: rows={latest}"
    )


def parse_actor_result(actor: subprocess.Popen[str]) -> Dict[str, Any]:
    try:
        stdout, stderr = actor.communicate(timeout=cl.POLL_TIMEOUT_SECONDS + 20)
    except subprocess.TimeoutExpired as exc:
        actor.kill()
        stdout, stderr = actor.communicate()
        raise cl.CommandLifecycleFailure(
            f"synthetic actor timed out: stdout={stdout!r} stderr={stderr!r}"
        ) from exc
    if actor.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"synthetic actor failed ({actor.returncode}): stdout={stdout!r} stderr={stderr!r}"
        )
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise cl.CommandLifecycleFailure("synthetic actor emitted no result")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise cl.CommandLifecycleFailure(f"synthetic actor result was invalid JSON: {stdout!r}") from exc


def write_evidence(evidence: Dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_ARTIFACT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    audit_lines = []
    for row in evidence["auditTimeline"]:
        audit_lines.append(
            f"- `{row.get('timestamp')}` — `{row.get('entityType')}:{row.get('entityId')}` "
            f"— `{row.get('eventType')}` — {row.get('action')}"
        )
    markdown = f"""# TerraNeuron Synthetic Farm Operations Pilot Evidence

> Bounded software/demo evidence only. This artifact does **not** establish physical-device truth,
> manufacturer semantics, production MQTT identity/TLS, field safety, unattended autonomous control,
> HA/DR/load maturity, certification, or that synthetic/device-reported state equals physical state.

## Scenario

- Farm: `{evidence['identity']['farmId']}`
- Asset: `{evidence['identity']['assetId']}`
- Plan: `{evidence['identity']['planId']}`
- Command: `{evidence['identity']['commandId']}`
- Synthetic starting state: `{evidence['syntheticStartingState'].get('state')}`
- Operator decision boundary: `{evidence['operatorDecision']['statusBeforeApproval']}` → explicit approval
- Terminal software state: `{evidence['terminal']['status']}` / `{evidence['terminal']['executionResult']}`

## Operator-visible decision

The plan was observed in the same pending-action API consumed by the Dashboard action-management surface before approval. Dispatch occurred only after an authenticated explicit approval request.

## Audit timeline

{chr(10).join(audit_lines)}

## Result

`PASS — coherent bounded Synthetic Farm Operations Pilot`
"""
    MARKDOWN_ARTIFACT.write_text(markdown, encoding="utf-8")


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    farm_id = f"farm-pilot-{run_id}"
    asset_id = f"fan-pilot-{run_id}"
    plan_id = f"plan-{run_id}"
    trace_id = f"trace-pilot-{run_id}"

    print("[1/8] Authenticate bounded human operator")
    token = cl.login()

    print("[2/8] Start reusable synthetic MQTT device actor and observe software state")
    actor = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "synthetic-mqtt-device.py"),
            "--farm-id", farm_id,
            "--asset-id", asset_id,
            "--plan-id", plan_id,
            "--device-type", "fan",
            "--timeout-seconds", str(int(cl.POLL_TIMEOUT_SECONDS)),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        starting_state = cl.wait_for_device_state(farm_id, asset_id)
        if starting_state.get("state") != "online":
            raise cl.CommandLifecycleFailure(f"synthetic actor did not announce online state: {starting_state}")
        print(f"  PASS synthetic software state visible for {farm_id}/{asset_id}")

        print("[3/8] Persist one approval-required farm action plan")
        event = {
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
                "reasoning": "Synthetic Farm Operations Pilot: operator-approved ventilation demo",
                "requires_approval": True,
                "priority": "medium",
                "generated_at": cl.now_rfc3339(),
                "expires_at": cl.future_rfc3339(10),
            },
        }
        cl.publish_action_plan(event)
        pending = cl.wait_for_plan(plan_id, token)
        if pending.get("status") != "PENDING":
            raise cl.CommandLifecycleFailure(f"pilot plan was not PENDING: {pending}")

        print("[4/8] Verify the operator-visible pending decision boundary")
        pending_rows = fetch_pending(token)
        visible = next((row for row in pending_rows if row.get("planId") == plan_id), None)
        if visible is None:
            raise cl.CommandLifecycleFailure(
                f"pilot plan was not present in operator pending-action API: {pending_rows}"
            )
        if visible.get("farmId") != farm_id or visible.get("targetAssetId") != asset_id:
            raise cl.CommandLifecycleFailure(f"operator-visible plan identity mismatch: {visible}")
        print("  PASS plan is visible to the operator and still requires explicit approval")

        print("[5/8] Explicitly approve and dispatch through Terra-Ops")
        approval = cl.requests.post(
            f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
            headers=cl.auth_headers(token),
            json={"notes": "D2 Synthetic Farm Operations Pilot explicit operator approval"},
            timeout=cl.REQUEST_TIMEOUT_SECONDS,
        )
        approval_payload = cl.response_json(approval, "pilot action approval")
        if approval_payload.get("planStatus") not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
            raise cl.CommandLifecycleFailure(f"approval did not enter dispatch lifecycle: {approval_payload}")

        print("[6/8] Reuse synthetic device actor for correlated terminal feedback")
        actor_result = parse_actor_result(actor)
        command_id = actor_result.get("commandId")
        expected_identity = (farm_id, asset_id, plan_id)
        actual_identity = (
            actor_result.get("farmId"), actor_result.get("assetId"), actor_result.get("planId")
        )
        if not command_id or actor_result.get("terminalStatus") != "EXECUTED" or actual_identity != expected_identity:
            raise cl.CommandLifecycleFailure(f"synthetic actor correlation mismatch: {actor_result}")

        terminal = cl.wait_for_terminal_plan(plan_id, token, str(command_id))
        if terminal.get("status") != "EXECUTED" or terminal.get("executionResult") != "DEVICE_CONFIRMED":
            raise cl.CommandLifecycleFailure(f"unexpected pilot terminal state: {terminal}")
        if terminal.get("commandId") != command_id:
            raise cl.CommandLifecycleFailure(f"terminal plan changed command identity: {terminal}")
        print(f"  PASS plan={plan_id} command={command_id} reached EXECUTED / DEVICE_CONFIRMED")

        print("[7/8] Verify complete chronological plan + command audit timeline")
        audit = wait_for_complete_audit(plan_id, token, str(command_id))
        unrelated_command_rows = [
            row for row in audit
            if row.get("entityType") == "command" and row.get("entityId") != command_id
        ]
        if unrelated_command_rows:
            raise cl.CommandLifecycleFailure(
                f"audit timeline contained unrelated command rows: {unrelated_command_rows}"
            )
        timestamps = [row.get("timestamp") for row in audit if row.get("timestamp")]
        if timestamps != sorted(timestamps):
            raise cl.CommandLifecycleFailure(f"audit timeline was not chronological: {timestamps}")
        print(f"  PASS audit timeline contains {len(audit)} correlated chronological rows")

        print("[8/8] Emit reusable buyer-facing bounded evidence artifacts")
        evidence = {
            "proofBoundary": "bounded synthetic software/demo only",
            "identity": {
                "farmId": farm_id,
                "assetId": asset_id,
                "planId": plan_id,
                "commandId": command_id,
                "traceId": trace_id,
            },
            "syntheticStartingState": starting_state,
            "operatorDecision": {
                "statusBeforeApproval": pending.get("status"),
                "visibleInPendingActionApi": True,
                "explicitApproval": True,
            },
            "terminal": {
                "status": terminal.get("status"),
                "executionResult": terminal.get("executionResult"),
                "executionError": terminal.get("executionError"),
            },
            "auditTimeline": audit,
            "nonClaims": [
                "physical-device truth",
                "manufacturer semantics",
                "production MQTT identity/auth/TLS",
                "field safety/interlocks",
                "unattended autonomous control",
                "production HA/DR/load maturity",
                "certification",
            ],
        }
        write_evidence(evidence)
        print(f"  PASS wrote {JSON_ARTIFACT} and {MARKDOWN_ARTIFACT}")
        print("SYNTHETIC FARM OPERATIONS PILOT PASS")
        return 0
    finally:
        if actor.poll() is None:
            actor.kill()
            actor.communicate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SYNTHETIC FARM OPERATIONS PILOT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
