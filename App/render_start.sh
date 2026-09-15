#!/usr/bin/env bash
# Render entrypoint: mock UbyPort (staging only) + UbyHost web app (foreground).
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  PYTHON="python3"
fi

PORT="${PORT:-10000}"
UBYPORT_ENV="${UBYHOST_UBYPORT_ENV:-mock}"
export UBYHOST_UBYPORT_ENV="${UBYPORT_ENV}"

if [ -z "${UBYHOST_PUBLIC_BASE_URL:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
  export UBYHOST_PUBLIC_BASE_URL="${RENDER_EXTERNAL_URL}"
fi

MOCK_PID=""

cleanup() {
  if [ -n "${MOCK_PID}" ] && kill -0 "${MOCK_PID}" 2>/dev/null; then
    kill "${MOCK_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [ "${UBYPORT_ENV}" = "prod" ]; then
  echo "FATAL: UBYHOST_UBYPORT_ENV=prod is not allowed on Render." >&2
  echo "Live reporting runs only on AWS Lightsail. Staging must stay mock." >&2
  exit 1
fi

if [ "${UBYPORT_ENV}" = "mock" ]; then
  export UBYHOST_MOCK_URL="${UBYHOST_MOCK_URL:-http://127.0.0.1:8081/ws_uby/ws_uby.svc}"
  echo "Starting mock UbyPort on port 8081 (demo only — nothing sent to the police)."
  "$PYTHON" -m mock_ubyport.server &
  MOCK_PID=$!
  sleep 1.5
else
  echo "UbyPort target: ${UBYPORT_ENV} (no mock server — reports go to the police endpoint)."
fi

echo "UbyHost listening on 0.0.0.0:${PORT} (deployment=${UBYHOST_DEPLOYMENT:-unset})"
exec "$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
