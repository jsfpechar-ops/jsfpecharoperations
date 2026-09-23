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
skipped=0

# A Cloudflare managed challenge is served by the edge, not by the origin: the
# request never reaches the app. Such a response therefore says nothing about
# the app in either direction and must not be reported as a pass *or* as a
# failure. Production challenges /login, /admin* and /l/* this way.
is_cloudflare_challenge() {
  local headers="$1"
  local code="$2"
  [ "${code}" = "403" ] || return 1
  grep -qi '^cf-mitigated:[[:space:]]*challenge' "${headers}" && return 0
  # Some edge responses carry only the Cloudflare banner plus the interstitial.
  grep -qi '^server:[[:space:]]*cloudflare' "${headers}" \
    && grep -qi 'Just a moment' /tmp/ubyhost-smoke-body
}

check() {
  local path="$1"
  local expect="${2:-200}"
  local url="${BASE}${path}"
  local headers code
  headers="$(mktemp "${TMPDIR:-/tmp}/ubyhost-smoke-headers.XXXXXX")"
  code="$(curl -sS -o /tmp/ubyhost-smoke-body -D "${headers}" -w '%{http_code}' -L --max-time 20 "${url}" || echo "000")"
  if [ "${code}" = "${expect}" ]; then
    echo "OK   ${url} → ${code}"
  elif is_cloudflare_challenge "${headers}" "${code}"; then
    echo "SKIP ${url} → ${code} (Cloudflare challenge; origin not reached)"
    skipped=$((skipped + 1))
  else
    echo "FAIL ${url} → HTTP ${code} (expected ${expect})" >&2
    fail=1
  fi
  rm -f "${headers}"
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
if [ "${skipped}" -ne 0 ]; then
  echo "Public smoke passed (${skipped} check(s) skipped: Cloudflare challenge, origin not reached)."
else
  echo "Public smoke passed."
fi
