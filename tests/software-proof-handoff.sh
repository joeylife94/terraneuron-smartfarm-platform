#!/usr/bin/env bash
set -euo pipefail

# TerraNeuron bounded software Proof handoff smoke.
# This script proves only the current synthetic Compose software boundary.
# It does NOT establish physical-device truth, production safety certification,
# production MQTT identity/TLS, HA/DR/load/fault-injection maturity, manufacturer
# adapter truth, or unattended autonomous-control readiness.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE=(docker compose)
KEEP_STACK="${TERRANEURON_HANDOFF_KEEP_STACK:-0}"

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
  local attempts="${3:-60}"
  local sleep_seconds="${4:-5}"

  echo "[handoff] waiting for ${service}: ${url}"
  for ((attempt=1; attempt<=attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 5 "${url}" >/dev/null; then
      echo "[handoff] ${service} ready"
      return 0
    fi
    sleep "${sleep_seconds}"
  done

  echo "[handoff] ${service} readiness failed"
  "${COMPOSE[@]}" logs --tail=120 "${service}" || true
  return 1
}

echo "[handoff] validating Compose configuration"
"${COMPOSE[@]}" config --quiet

echo "[handoff] starting bounded software Proof stack"
"${COMPOSE[@]}" up -d --build \
  redis zookeeper kafka mysql influxdb mosquitto \
  terra-sense terra-ops

echo "[handoff] waiting for MySQL"
for attempt in {1..60}; do
  if "${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent >/dev/null 2>&1; then
    echo "[handoff] mysql ready"
    break
  fi
  if [[ "${attempt}" -eq 60 ]]; then
    echo "[handoff] mysql readiness failed"
    "${COMPOSE[@]}" logs --tail=120 mysql || true
    exit 1
  fi
  sleep 2
done

wait_for_http terra-sense http://localhost:8081/actuator/health
wait_for_http terra-ops http://localhost:8080/actuator/health

echo "[handoff] executing bounded command lifecycle software Proof"
python3 tests/command-lifecycle-test.py

echo "[handoff] PASS — bounded Compose software Proof reproduced"
echo "[handoff] non-claims remain authoritative; see STATUS.md"
