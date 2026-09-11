#!/usr/bin/env python3
"""Reusable synthetic MQTT device actor for bounded TerraNeuron software Proof.

The actor announces synthetic device state, subscribes to exactly one configured
command topic, validates command identity/correlation fields, and emits one
correlated terminal EXECUTED status/ACK.

This is synthetic software evidence only. It does not model actuator physics,
manufacturer semantics, safety interlocks, emergency-stop behavior, or physical
state truth.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connection_args(args: argparse.Namespace) -> list[str]:
    values = ["-h", args.host, "-p", str(args.port)]
    if args.username:
        values += ["-u", args.username, "-P", args.password or ""]
    if args.cafile:
        values += ["--cafile", args.cafile]
    return values


def run_mosquitto(command: str, args: argparse.Namespace, extra: list[str]) -> str:
    completed = subprocess.run(
        ["docker", "exec", "-i", "terraneuron-mosquitto", command, *connection_args(args), *extra],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"mosquitto command failed ({completed.returncode}): "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    return completed.stdout.strip()


def publish(topic: str, payload: Dict[str, Any], args: argparse.Namespace) -> None:
    run_mosquitto(
        "mosquitto_pub",
        args,
        ["-q", "1", "-t", topic, "-m", json.dumps(payload, separators=(",", ":"))],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--farm-id", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--device-type", default="fan")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--cafile", default="")
    args = parser.parse_args()

    command_topic = f"terra/devices/{args.farm_id}/{args.asset_id}/command"
    status_topic = f"terra/devices/{args.farm_id}/{args.asset_id}/status"

    subscriber = subprocess.Popen(
        [
            "docker", "exec", "-i", "terraneuron-mosquitto", "mosquitto_sub",
            *connection_args(args),
            "-q", "1", "-t", command_topic, "-C", "1", "-W", str(args.timeout_seconds),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    publish(
        status_topic,
        {
            "farmId": args.farm_id,
            "assetId": args.asset_id,
            "deviceType": args.device_type,
            "state": "online",
            "maintenanceMode": False,
            "reportedAt": now_rfc3339(),
        },
        args,
    )

    try:
        stdout, stderr = subscriber.communicate(timeout=args.timeout_seconds + 10)
    except subprocess.TimeoutExpired as exc:
        subscriber.kill()
        stdout, stderr = subscriber.communicate()
        raise RuntimeError(
            f"timed out waiting for synthetic command: stdout={stdout!r} stderr={stderr!r}"
        ) from exc

    if subscriber.returncode != 0:
        raise RuntimeError(
            f"synthetic command subscription failed ({subscriber.returncode}): {stderr}"
        )

    try:
        command = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"synthetic command was invalid JSON: {stdout!r}") from exc

    required = {
        "commandId": command.get("commandId"),
        "farmId": command.get("farmId"),
        "targetAssetId": command.get("targetAssetId"),
        "planId": command.get("planId"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"synthetic command omitted required fields {missing}: {command}")

    expected_identity = (args.farm_id, args.asset_id, args.plan_id)
    actual_identity = (
        str(required["farmId"]),
        str(required["targetAssetId"]),
        str(required["planId"]),
    )
    if actual_identity != expected_identity:
        raise RuntimeError(
            f"synthetic command identity mismatch: expected={expected_identity} actual={actual_identity}"
        )

    command_id = str(required["commandId"])
    ack = {
        "farmId": args.farm_id,
        "assetId": args.asset_id,
        "deviceType": args.device_type,
        "state": "running",
        "maintenanceMode": False,
        "lastCommandId": command_id,
        "lastCommandStatus": "EXECUTED",
        "reportedAt": now_rfc3339(),
    }
    publish(status_topic, ack, args)

    print(
        json.dumps(
            {
                "synthetic": True,
                "farmId": args.farm_id,
                "assetId": args.asset_id,
                "planId": args.plan_id,
                "commandId": command_id,
                "terminalStatus": "EXECUTED",
                "transport": "authenticated-tls" if args.cafile else "default",
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SYNTHETIC DEVICE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
