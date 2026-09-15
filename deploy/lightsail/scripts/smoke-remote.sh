#!/usr/bin/env bash
# Public HTTP smoke after a Lightsail deploy.
# Usage:
#   ./scripts/smoke-remote.sh
#   ./scripts/smoke-remote.sh https://ubyhost.com
# Does not require host credentials. Production /healthz omits env labels
# (see docs/SECURITY.md); confirm those with ./scripts/status.sh on the VM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

BASE="${1:-${UBYHOST_PUBLIC_BASE_URL:-}}"
if [ -z "${BASE}" ]; then
  echo "Pass a base URL or set UBYHOST_PUBLIC_BASE_URL in .env" >&2
  exit 1
fi
BASE="${BASE%/}"

fail=0
check() {
  local path="$1"
  local expect="${2:-200}"
  local url="${BASE}${path}"
  local code
  code="$(curl -sS -o /tmp/ubyhost-smoke-body -w '%{http_code}' -L --max-time 20 "${url}" || echo "000")"
  if [ "${code}" != "${expect}" ]; then
    echo "FAIL ${url} → HTTP ${code} (expected ${expect})" >&2
    fail=1
    return
  fi
  echo "OK   ${url} → ${code}"
}

echo "==> Smoke ${BASE}"
check "/healthz" 200
python3 - <<'PY'
import json, sys
from pathlib import Path
body = Path("/tmp/ubyhost-smoke-body").read_text()
try:
    data = json.loads(body)
except json.JSONDecodeError:
    print("FAIL /healthz is not JSON", file=sys.stderr)
    sys.exit(1)
if data.get("status") not in ("ok", "degraded"):
    print(f"FAIL /healthz status={data.get('status')!r}", file=sys.stderr)
    sys.exit(1)
if data.get("data_dir_writable") is False:
    print("FAIL data_dir_writable is false", file=sys.stderr)
    sys.exit(1)
print("OK   /healthz JSON", json.dumps({k: data[k] for k in data}))
PY

check "/login" 200
check "/legal" 200
check "/privacy" 200

if [ "${fail}" -ne 0 ]; then
  echo "Public smoke failed." >&2
  exit 1
fi
echo "Public smoke passed."
