#!/bin/bash
# Start NIKA stack inside the Ubuntu container (no build).
set -euo pipefail

NIKA_ROOT="${NIKA_ROOT:-/home/nika/nika_cw}"
VENV="${NIKA_VENV:-/opt/nika-venv}"
LOG_DIR="${LOG_DIR:-/home/nika/logs}"
export LD_LIBRARY_PATH="${NIKA_ROOT}/bin:${NIKA_ROOT}/bin/extensions${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HOME="${HOME:-/home/nika}"

mkdir -p "$LOG_DIR"
cd "$NIKA_ROOT"
# shellcheck disable=SC1091
source scripts/set_vars.sh

ensure_venv() {
  if [ ! -x "$VENV/bin/python3" ]; then
    echo "[entrypoint] creating venv at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$NIKA_ROOT/sc-web/requirements.txt"
    "$VENV/bin/pip" install -q -r "$NIKA_ROOT/problem-solver/py/requirements.txt"
  fi
}

wait_port() {
  local port="$1" name="$2" tries="${3:-60}"
  for _ in $(seq 1 "$tries"); do
    if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
      echo "[entrypoint] $name is up on :$port"
      return 0
    fi
    sleep 1
  done
  echo "[entrypoint] WARNING: $name did not open :$port in time" >&2
  return 1
}

ensure_venv

echo "[entrypoint] starting sc-server"
nohup "$BINARY_PATH/sc-server" -c "$CONFIG_PATH" >"$LOG_DIR/sc-server.log" 2>&1 &
wait_port 8090 sc-server || true
if grep -q "Can't load module" "$LOG_DIR/sc-server.log" 2>/dev/null; then
  echo "[entrypoint] ERROR: some extensions failed to load:" >&2
  grep "Can't load module" "$LOG_DIR/sc-server.log" >&2 || true
fi

echo "[entrypoint] starting sc-web"
(
  cd "$NIKA_ROOT/sc-web"
  nohup "$VENV/bin/python3" server/app.py \
    --server_host=localhost \
    --public_url=ws://localhost:8090/ws_json \
    >"$LOG_DIR/sc-web.log" 2>&1 &
)
wait_port 8000 sc-web || true

echo "[entrypoint] starting py-agents"
nohup "$VENV/bin/python3" "$NIKA_ROOT/problem-solver/py/server.py" --host=localhost \
  >"$LOG_DIR/py-agents.log" 2>&1 &

echo "[entrypoint] starting UI (yarn)"
(
  cd "$NIKA_ROOT/interface"
  nohup yarn start >"$LOG_DIR/ui.log" 2>&1 &
)
wait_port 3033 ui 120 || true

echo "[entrypoint] stack is running (3033 UI, 8000 sc-web, 8090 sc-server)"
touch "$LOG_DIR/sc-server.log" "$LOG_DIR/sc-web.log" "$LOG_DIR/ui.log" "$LOG_DIR/py-agents.log"
exec tail -F "$LOG_DIR/sc-server.log" "$LOG_DIR/sc-web.log" "$LOG_DIR/ui.log" "$LOG_DIR/py-agents.log"
