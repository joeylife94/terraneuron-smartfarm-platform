#!/usr/bin/env python3
"""D4 bounded synthetic device integration conformance pilot.

Synthetic software evidence only. This verifies repository-owned adapter/model
identity, declared capability admission, authenticated MQTT transport reuse,
command identity, and correlated terminal ACK. It does not validate any real
manufacturer, hardware, physical actuator truth, field safety, provisioning,
production PKI, unattended control, HA/DR/load maturity, or certification.
"""

import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
ARTIFACT = Path("artifacts/d4-device-integration-conformance.json")
CAFILE = "/mosquitto/config/d3-certs/ca.crt"
HOST = "localhost"
PORT = "8883"
FARM_ID = "farm-d3"
ASSET_ID = "device-a"
ADAPTER_ID = "terraneuron-synthetic-conformance-v1"
MODEL_ID = "tn-synth-climate-01"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cl = load("command_lifecycle", ROOT / "command-lifecycle-test.py")
d2 = load("synthetic_pilot", ROOT / "synthetic-farm-operations-pilot.py")


def main() -> int:
    device_password = os.environ["D3_DEVICE_A_PASSWORD"]
    plan_id = f"plan-d4{uuid.uuid4().hex[:10]}"
    trace_id = f"trace-d4-{uuid.uuid4().hex[:10]}"

    print("[1/6] Start authenticated synthetic adapter/model actor")
    actor = subprocess.Popen(
        [
            sys.executable, str(ROOT / "synthetic-mqtt-device.py"),
            "--farm-id", FARM_ID,
            "--asset-id", ASSET_ID,
            "--plan-id", plan_id,
            "--device-type", "heater",
            "--adapter-id", ADAPTER_ID,
            "--model-id", MODEL_ID,
            "--timeout-seconds", str(int(cl.POLL_TIMEOUT_SECONDS)),
            "--host", HOST,
            "--port", PORT,
            "--username", "device-a",
            "--password", device_password,
            "--cafile", CAFILE,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        print("[2/6] Observe adapter/model identity through MQTT-ingested device state")
        starting_state = cl.wait_for_device_state(FARM_ID, ASSET_ID)
        attributes: Dict[str, Any] = starting_state.get("attributes") or {}
        if attributes.get("adapterId") != ADAPTER_ID or attributes.get("modelId") != MODEL_ID:
            raise cl.CommandLifecycleFailure(
                f"D4 adapter/model identity was not preserved through MQTT state ingestion: {starting_state}"
            )

        print("[3/6] Persist schema-valid approval-required heating plan")
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
                "target_asset_id": ASSET_ID,
                "target_asset_type": "device",
                "action_category": "heating",
                "action_type": "turn_on",
                "parameters": {},
                "reasoning": "D4 repository-owned synthetic adapter conformance pilot",
                "requires_approval": True,
                "priority": "medium",
                "generated_at": cl.now_rfc3339(),
                "expires_at": cl.future_rfc3339(10),
            },
        }
        cl.publish_action_plan(event)
        pending = cl.wait_for_plan(plan_id, token)
        if pending.get("status") != "PENDING":
            raise cl.CommandLifecycleFailure(f"D4 plan was not PENDING before approval: {pending}")

        print("[4/6] Approve through existing software safety/capability path")
        approval = cl.requests.post(
            f"{cl.TERRA_OPS_BASE_URL}/api/actions/{plan_id}/approve",
            headers=cl.auth_headers(token),
            json={"notes": "D4 explicit operator approval"},
            timeout=cl.REQUEST_TIMEOUT_SECONDS,
        )
        approved = cl.response_json(approval, "D4 action approval")
        if approved.get("planStatus") not in {"APPROVED", "DISPATCHING", "DISPATCHED", "DELIVERED"}:
            raise cl.CommandLifecycleFailure(f"D4 approval did not enter dispatch lifecycle: {approved}")

        print("[5/6] Verify authenticated delivery, stable identity, and terminal ACK")
        actor_result = d2.parse_actor_result(actor)
        command_id = actor_result.get("commandId")
        if (
            not command_id
            or actor_result.get("terminalStatus") != "EXECUTED"
            or actor_result.get("transport") != "authenticated-tls"
            or actor_result.get("adapterId") != ADAPTER_ID
            or actor_result.get("modelId") != MODEL_ID
        ):
            raise cl.CommandLifecycleFailure(f"D4 actor result mismatch: {actor_result}")
        terminal = cl.wait_for_terminal_plan(plan_id, token, str(command_id))
        if terminal.get("executionResult") != "DEVICE_CONFIRMED":
            raise cl.CommandLifecycleFailure(f"D4 terminal result mismatch: {terminal}")
        audit = d2.wait_for_complete_audit(plan_id, token, str(command_id))
        event_types = {row.get("eventType") for row in audit}
        if "PLAN_APPROVED" not in event_types or "COMMAND_EXECUTED" not in event_types:
            raise cl.CommandLifecycleFailure(f"D4 audit missing lifecycle evidence: {event_types}")

        print("[6/6] Emit bounded machine-readable conformance evidence")
        ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT.write_text(
            json.dumps(
                {
                    "proofBoundary": "repository-owned synthetic device integration conformance",
                    "adapterId": ADAPTER_ID,
                    "modelId": MODEL_ID,
                    "declaredContract": {
                        "actionCategory": "heating",
                        "actionTypes": ["turn_on", "turn_off", "adjust"],
                        "adjustParameters": ["target_temperature"],
                    },
                    "verified": {
                        "adapterModelIdentityPreservedThroughMqttState": True,
                        "supportedSchemaValidActionAdmitted": True,
                        "authenticatedTlsMessagingPreserved": True,
                        "commandIdentityPreserved": True,
                        "terminalAckCorrelated": True,
                        "operatorAuditObserved": True,
                    },
                    "identity": {
                        "farmId": FARM_ID,
                        "assetId": ASSET_ID,
                        "planId": plan_id,
                        "commandId": str(command_id),
                    },
                    "nonClaims": [
                        "real manufacturer semantics",
                        "real hardware or physical actuator truth",
                        "physical safety/interlocks/E-stop",
                        "production provisioning/PKI/secrets lifecycle",
                        "unattended autonomous control",
                        "production HA/DR/load/public deployment",
                        "certification",
                    ],
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print("D4 PASS — bounded synthetic adapter/model integration conformance")
        return 0
    finally:
        if actor.poll() is None:
            actor.kill()
            actor.communicate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"D4 CONFORMANCE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
