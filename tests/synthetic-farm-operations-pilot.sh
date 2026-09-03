#!/usr/bin/env bash
set -euo pipefail

# One-command D2 Synthetic Farm Operations Pilot.
# Bounded software/demo evidence only. This does NOT establish physical-device
# truth, manufacturer semantics, production MQTT identity/TLS, field safety,
# unattended autonomous control, HA/DR/load maturity, or certification.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE=(docker compose)
KEEP_STACK="${TERRANEURON_PILOT_KEEP_STACK:-0}"
export JWT_SECRET="${JWT_SECRET:-DEMO_ONLY_LOCAL_PILOT_JWT_SECRET_32_CHARS_MIN}"
export E2E_POLL_TIMEOUT_SECONDS="${E2E_POLL_TIMEOUT_SECONDS:-90}"
export E2E_POLL_INTERVAL_SECONDS="${E2E_POLL_INTERVAL_SECONDS:-1}"

cleanup() {
  local exit_code=$?
  if [[ "${KEEP_STACK}" != "1" ]]; then
    "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT

wait_for_http() {
  local service="$1"
  local url="$2"
  for attempt in {1..60}; do
    if curl --fail --silent --show-error --max-time 5 "${url}" >/dev/null; then
      echo "[pilot] ${service} ready"
      return 0
    fi
    sleep 5
  done
  echo "[pilot] ${service} readiness failed"
  "${COMPOSE[@]}" logs --tail=120 "${service}" || true
  return 1
}

echo "[pilot] validating Compose configuration"
"${COMPOSE[@]}" config --quiet

echo "[pilot] starting bounded synthetic operations stack"
"${COMPOSE[@]}" up -d --build \
  redis zookeeper kafka mysql influxdb mosquitto \
  terra-sense terra-ops

for attempt in {1..60}; do
  if "${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent >/dev/null 2>&1; then
    echo "[pilot] mysql ready"
    break
  fi
  if [[ "${attempt}" -eq 60 ]]; then
    echo "[pilot] mysql readiness failed"
    "${COMPOSE[@]}" logs --tail=120 mysql || true
    exit 1
  fi
  sleep 2
done

wait_for_http terra-sense http://localhost:8081/actuator/health
wait_for_http terra-ops http://localhost:8080/actuator/health

mkdir -p artifacts
rm -f artifacts/synthetic-farm-operations-pilot.json artifacts/synthetic-farm-operations-pilot.md

echo "[pilot] executing coherent synthetic farm operations scenario"
python3 tests/synthetic-farm-operations-pilot.py

test -s artifacts/synthetic-farm-operations-pilot.json
test -s artifacts/synthetic-farm-operations-pilot.md

echo "[pilot] PASS — coherent bounded Synthetic Farm Operations Pilot reproduced"
echo "[pilot] evidence: artifacts/synthetic-farm-operations-pilot.{json,md}"
echo "[pilot] non-claims remain authoritative; see STATUS.md"
