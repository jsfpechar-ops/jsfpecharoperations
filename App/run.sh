#!/usr/bin/env bash
# Start UbyHost, and the mock UbyPort server too when no real credentials are configured.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Creating the virtual environment..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

export UBYHOST_UBYPORT_ENV="${UBYHOST_UBYPORT_ENV:-mock}"
export UBYHOST_PUBLIC_BASE_URL="${UBYHOST_PUBLIC_BASE_URL:-http://127.0.0.1:8080}"
if [ "$UBYHOST_UBYPORT_ENV" = "mock" ]; then
  export UBYHOST_ICAL_ALLOW_PRIVATE="${UBYHOST_ICAL_ALLOW_PRIVATE:-1}"
fi
# Single process: web app and background scheduler together (WP06). The
# Lightsail stack runs them as separate containers instead.
export UBYHOST_ROLE="${UBYHOST_ROLE:-all}"
PORT="${PORT:-8080}"

cleanup() {
  if [ -n "${MOCK_PID:-}" ] && kill -0 "$MOCK_PID" 2>/dev/null; then
    kill "$MOCK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [ "$UBYHOST_UBYPORT_ENV" = "mock" ]; then
  echo "Starting the mock UbyPort server on port 8081 (nothing is sent to the police)."
  "$PYTHON" -m mock_ubyport.server &
  MOCK_PID=$!
  sleep 1.5
fi

echo "UbyHost is starting on http://127.0.0.1:${PORT}"
exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
