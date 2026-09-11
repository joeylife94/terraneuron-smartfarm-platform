#!/usr/bin/env python3
"""D3 bounded authenticated device messaging pilot.

Synthetic software evidence only. This does not establish production PKI,
physical-device identity, manufacturer semantics, field safety, production MQTT
infrastructure, unattended autonomous control, HA/DR/load maturity, or certification.
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cl = load("command_lifecycle", ROOT / "command-lifecycle-test.py")
d2 = load("synthetic_pilot", ROOT / "synthetic-farm-operations-pilot.py")

ARTIFACT = Path("artifacts/d3-authenticated-device-messaging.json")
CAFILE = "/mosquitto/config/d3-certs/ca.crt"
HOST = "localhost"
PORT = "8883"
FARM_ID = "farm-d3"
ASSET_A = "device-a"
ASSET_B = "device-b"


def mqtt_command(username: str | None, password: str | None, topic: str, payload: Dict[str, Any]) -> subprocess.CompletedProcess[str]:
    command = [
        "docker", "exec", "-i", "terraneuron-mosquitto", "mosquitto_pub",
        "-h", HOST, "-p", PORT, "--cafile", CAFILE,
        "-V", "mqttv5", "-q", "1", "-t", topic,
        "-m", json.dumps(payload, separators=(",", ":")),
    ]
    if username:
        command += ["-u", username, "-P", password or ""]
    return subprocess.run(command, text=True, capture_output=True, check=False)


def require_denied(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode == 0:
        raise cl.CommandLifecycleFailure(
            f"{label} unexpectedly succeeded: stdout={result.stdout!r} stderr={result.stderr!r}"
        )


def wait_for_unknown_device_state(farm_id: str, asset_id: str) -> Dict[str, Any]:
    deadline = time.time() + cl.POLL_TIMEOUT_SECONDS
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        last = cl.fetch_device_state(farm_id, asset_id)
        if last.get("state") == "unknown":
            return last
        time.sleep(cl.POLL_INTERVAL_SECONDS)
    raise cl.CommandLifecycleFailure(
        f"timed out waiting for rejected device state invalidation; last={last}"
    )


def main() -> int:
    bridge_password = os.environ["D3_BRIDGE_PASSWORD"]
    device_a_password = os.environ["D3_DEVICE_A_PASSWORD"]
    device_b_password = os.environ["D3_DEVICE_B_PASSWORD"]
    plan_id = f"plan-d3-{uuid.uuid4().hex[:10]}"
    trace_id = f"trace-d3-{uuid.uuid4().hex[:10]}"
    topic_a_status = f"terra/devices/{FARM_ID}/{ASSET_A}/status"

    print("[1/9] Prove unauthenticated MQTT publication is denied")
    require_denied(
        mqtt_command(None, None, topic_a_status, {"farmId": FARM_ID, "assetId": ASSET_A, "state": "online"}),
        "unauthenticated device publication",
    )

    print("[2/9] Prove device B cannot impersonate device A topic")
    require_denied(
        mqtt_command("device-b", device_b_password, topic_a_status, {"farmId": FARM_ID, "assetId": ASSET_A, "state": "online"}),
        "cross-device topic publication",
    )

    print("[3/9] Prove topic/payload identity mismatch is rejected by Terra-Sense")
    baseline = mqtt_command(
        "device-a",
        device_a_password,
        topic_a_status,
        {
            "farmId": FARM_ID,
            "assetId": ASSET_A,
            "deviceType": "fan",
            "state": "online",
            "maintenanceMode": False,
            "reportedAt": cl.now_rfc3339(),
        },
    )
    if baseline.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"authorized baseline probe could not reach broker: {baseline.stderr!r}"
        )
    baseline_state = cl.wait_for_device_state(FARM_ID, ASSET_A)
    if baseline_state.get("state") != "online":
        raise cl.CommandLifecycleFailure(
            f"authorized baseline state was not observed before mismatch probe: {baseline_state}"
        )

    mismatch = mqtt_command(
        "device-a",
        device_a_password,
        topic_a_status,
        {
            "farmId": FARM_ID,
            "assetId": ASSET_B,
            "deviceType": "fan",
            "state": "online",
            "maintenanceMode": False,
            "reportedAt": cl.now_rfc3339(),
        },
    )
    if mismatch.returncode != 0:
        raise cl.CommandLifecycleFailure(
            f"authorized mismatch probe could not reach broker: {mismatch.stderr!r}"
        )
    wait_for_unknown_device_state(FARM_ID, ASSET_A)

    print("[4/9] Start authenticated TLS synthetic device A actor")
    actor = subprocess.Popen(
        [
            sys.executable, str(ROOT / "synthetic-mqtt-device.py"),
            "--farm-id", FARM_ID,
            "--asset-id", ASSET_A,
            "--plan-id", plan_id,
            "--device-type", "fan",
            "--timeout-seconds", str(int(cl.POLL_TIMEOUT_SECONDS)),
            "--host", HOST,
            "--port", PORT,
            "--username", "device-a",
            "--password", device_a_password,
            "--cafile", CAFILE,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        starting_state = cl.wait_for_device_state(FARM_ID, ASSET_A)
        if starting_state.get("assetId") != ASSET_A:
            raise cl.CommandLifecycleFailure(f"authenticated device identity mismatch: {starting_state}")

        print("[5/9] Persist operator-visible approval-required plan")
        token = cl.login()
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
                "farm_id": FARM_ID,
                "target_asset_id": ASSET_A,
                "target_asset_type": "device",
                "action_category": "ventilation",
                "action_type": "turn_on",
                "parameters": {"duration_minutes": 5, "speed_level": "low"},
                "reasoning": "D3 bounded authenticated messaging pilot",
                "requires_approval": True,
                "priority": "medium",
                "generated_at": cl.now_rfc3339(),
                "expires_at": cl.future_rfc3339(10),
            },
        }
        cl.publish_action_plan(event)
        pending = cl.wait_for_plan(plan_id, token)
        if pending.get("status") != "PENDING":
            raise cl.CommandLifecycleFailure(f"D3 plan was not PENDING: {pending}")
        visible = next((row for row in d2.fetch_pending(token) if row.get("planId") == plan_id), None)
        if visible is None:
            raise cl.CommandLifecycleFailure("D3 plan was not operator-visible before approval")

        print("[6/9] Explicitly approve through existing software safety gates")
        approval = cl.requests.post(
            f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
            headers=cl.auth_headers(token),
            json={"notes": "D3 explicit operator approval"},
            timeout=cl.REQUEST_TIMEOUT_SECONDS,
        )
        approved = cl.response_json(approval, "D3 action approval")
        if approved.get("planStatus") not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
            raise cl.CommandLifecycleFailure(f"D3 approval did not enter dispatch lifecycle: {approved}")

        print("[7/9] Prove authenticated command delivery and correlated terminal ACK")
        actor_result = d2.parse_actor_result(actor)
        command_id = actor_result.get("commandId")
        if (
            not command_id
            or actor_result.get("terminalStatus") != "EXECUTED"
            or actor_result.get("transport") != "authenticated-tls"
        ):
            raise cl.CommandLifecycleFailure(f"D3 actor result mismatch: {actor_result}")
        terminal = cl.wait_for_terminal_plan(plan_id, token, str(command_id))
        if terminal.get("executionResult") != "DEVICE_CONFIRMED":
            raise cl.CommandLifecycleFailure(f"D3 terminal result mismatch: {terminal}")

        print("[8/9] Verify chronological operator audit evidence")
        audit = d2.wait_for_complete_audit(plan_id, token, str(command_id))
        event_types = {row.get("eventType") for row in audit}
        if "PLAN_APPROVED" not in event_types or "COMMAND_EXECUTED" not in event_types:
            raise cl.CommandLifecycleFailure(f"D3 audit missing lifecycle evidence: {event_types}")

        print("[9/9] Emit bounded public-safe evidence")
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        evidence = {
            "proofBoundary": "synthetic software-only authenticated MQTT pilot",
            "transport": {"tls": True, "brokerAuth": True, "productionPki": False},
            "authorization": {
                "unauthenticatedDenied": True,
                "crossDeviceImpersonationDenied": True,
                "topicPayloadIdentityMismatchRejected": True,
            },
            "operatorJourney": {
                "pendingBeforeApproval": True,
                "explicitApproval": True,
                "existingSoftwareSafetyGatesPreserved": True,
                "terminalStatus": terminal.get("status"),
                "executionResult": terminal.get("executionResult"),
            },
            "identity": {
                "farmId": FARM_ID,
                "assetId": ASSET_A,
                "planId": plan_id,
                "commandId": command_id,
            },
            "auditEventTypes": sorted(str(value) for value in event_types if value),
            "nonClaims": [
                "production PKI/provisioning/rotation",
                "physical-device identity or actuator truth",
                "manufacturer semantics",
                "field-network security or field safety",
                "production MQTT infrastructure",
                "unattended autonomous control",
                "production HA/DR/load maturity",
                "certification",
            ],
        }
        ARTIFACT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print("D3 AUTHENTICATED DEVICE MESSAGING PILOT PASS")
        return 0
    finally:
        if actor.poll() is None:
            actor.kill()
            actor.communicate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"D3 AUTHENTICATED DEVICE MESSAGING PILOT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
