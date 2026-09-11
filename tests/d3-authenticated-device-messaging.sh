#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

RUNTIME="${ROOT_DIR}/.d3-runtime"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.d3.yml)
KEEP_STACK="${TERRANEURON_D3_KEEP_STACK:-0}"
export JWT_SECRET="${JWT_SECRET:-DEMO_ONLY_D3_JWT_SECRET_32_CHARS_MIN}"
export E2E_POLL_TIMEOUT_SECONDS="${E2E_POLL_TIMEOUT_SECONDS:-90}"
export E2E_POLL_INTERVAL_SECONDS="${E2E_POLL_INTERVAL_SECONDS:-1}"
export D3_BRIDGE_PASSWORD="${D3_BRIDGE_PASSWORD:-$(openssl rand -hex 16)}"
export D3_DEVICE_A_PASSWORD="${D3_DEVICE_A_PASSWORD:-$(openssl rand -hex 16)}"
export D3_DEVICE_B_PASSWORD="${D3_DEVICE_B_PASSWORD:-$(openssl rand -hex 16)}"

cleanup() {
  local code=$?
  if [[ "${KEEP_STACK}" != "1" ]]; then
    "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
  fi
  rm -rf "${RUNTIME}"
  exit "${code}"
}
trap cleanup EXIT

wait_for_http() {
  local service="$1" url="$2"
  for attempt in {1..60}; do
    if curl --fail --silent --show-error --max-time 5 "${url}" >/dev/null; then
      echo "[d3] ${service} ready"
      return 0
    fi
    sleep 5
  done
  "${COMPOSE[@]}" logs --tail=150 "${service}" || true
  return 1
}

rm -rf "${RUNTIME}"
mkdir -p "${RUNTIME}/certs"

openssl req -x509 -newkey rsa:2048 -nodes -days 2 \
  -keyout "${RUNTIME}/certs/ca.key" -out "${RUNTIME}/certs/ca.crt" \
  -subj "/CN=TerraNeuron D3 Synthetic CA" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes \
  -keyout "${RUNTIME}/certs/server.key" -out "${RUNTIME}/certs/server.csr" \
  -subj "/CN=mosquitto" >/dev/null 2>&1
cat > "${RUNTIME}/certs/server.ext" <<'EOF'
subjectAltName=DNS:mosquitto,DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -days 2 -sha256 \
  -in "${RUNTIME}/certs/server.csr" \
  -CA "${RUNTIME}/certs/ca.crt" -CAkey "${RUNTIME}/certs/ca.key" -CAcreateserial \
  -out "${RUNTIME}/certs/server.crt" -extfile "${RUNTIME}/certs/server.ext" >/dev/null 2>&1
chmod 0644 "${RUNTIME}/certs/server.key" "${RUNTIME}/certs/server.crt" "${RUNTIME}/certs/ca.crt"

keytool -importcert -noprompt -alias terraneuron-d3-ca \
  -file "${RUNTIME}/certs/ca.crt" -keystore "${RUNTIME}/truststore.p12" \
  -storetype PKCS12 -storepass changeit >/dev/null

touch "${RUNTIME}/passwords"
docker run --rm -v "${RUNTIME}:/work" eclipse-mosquitto:2.0 sh -ec '
  mosquitto_passwd -b /work/passwords terra-sense-bridge "$D3_BRIDGE_PASSWORD"
  mosquitto_passwd -b /work/passwords device-a "$D3_DEVICE_A_PASSWORD"
  mosquitto_passwd -b /work/passwords device-b "$D3_DEVICE_B_PASSWORD"
' \
  -e D3_BRIDGE_PASSWORD -e D3_DEVICE_A_PASSWORD -e D3_DEVICE_B_PASSWORD
chmod 0644 "${RUNTIME}/passwords"

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up -d --build redis zookeeper kafka mysql influxdb mosquitto terra-sense terra-ops

for attempt in {1..60}; do
  if "${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

wait_for_http terra-sense http://localhost:8081/actuator/health
wait_for_http terra-ops http://localhost:8080/actuator/health

mkdir -p artifacts
rm -f artifacts/d3-authenticated-device-messaging.json
python3 tests/d3-authenticated-device-messaging.py
test -s artifacts/d3-authenticated-device-messaging.json

echo "[d3] PASS — bounded authenticated device messaging pilot"
