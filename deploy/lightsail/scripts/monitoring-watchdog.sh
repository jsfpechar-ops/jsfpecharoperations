#!/usr/bin/env bash
# Monitoring watchdog (brief 0425 follow-up): is the observability stack alive?
# Run from cron, e.g. every 15 minutes:
#   */15 * * * * cd /opt/ubyhost/deploy/lightsail && ./scripts/monitoring-watchdog.sh
# Prints one line per check, no tokens. Exit 0 = all good, 1 = something is wrong.
# If UBYHOST_HEARTBEAT_MONITORING_URL is set in .env, pings <url> on success and
# <url>/fail on any failure (healthchecks.io semantics, like the filing watchdog).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

failures=0
fail() {
  echo "FAIL: $1"
  failures=$((failures + 1))
}
ok() {
  echo "ok:   $1"
}

# 1. Are the monitoring containers running?
for svc in alloy node-exporter cadvisor; do
  state="$(docker compose ps --format '{{.State}}' "${svc}" 2>/dev/null | head -1)"
  if [ "${state}" = "running" ]; then
    ok "${svc} running"
  else
    fail "${svc} not running (state: ${state:-absent})"
  fi
done

# 2. Fresh data in Grafana Cloud Prometheus? (up query, must have results <5 min old)
if [ -n "${GRAFANA_PROM_URL:-}" ] && [ -n "${GRAFANA_PROM_USER:-}" ] && [ -n "${GRAFANA_PROM_TOKEN:-}" ]; then
  query_url="${GRAFANA_PROM_URL%/push}/api/v1/query"
  result="$(curl -sS -m 15 -u "${GRAFANA_PROM_USER}:${GRAFANA_PROM_TOKEN}" \
    --data-urlencode 'query=up' "${query_url}" 2>/dev/null || echo '')"
  if echo "${result}" | grep -q '"status":"success"'; then
    if echo "${result}" | grep -q '"job":"node"' && echo "${result}" | grep -q '"job":"cadvisor"'; then
      ok "Grafana Cloud Prometheus has node and cadvisor series"
    else
      fail "Grafana Cloud Prometheus query worked but node/cadvisor series missing (remote-write broken?)"
    fi
  else
    fail "Grafana Cloud Prometheus query failed (auth, URL, or network)"
  fi
else
  fail "GRAFANA_PROM_URL / GRAFANA_PROM_USER / GRAFANA_PROM_TOKEN not set in .env"
fi

# 3. Recent push errors in the alloy log? (401/404 spam means data is not arriving)
since="15m"
errors="$(docker logs --since "${since}" ubyhost-alloy-1 2>&1 | grep -c 'level=error' || true)"
if [ "${errors}" -eq 0 ]; then
  ok "no alloy errors in the last ${since}"
else
  fail "${errors} alloy error lines in the last ${since} (docker logs --since ${since} ubyhost-alloy-1)"
fi

# Heartbeat (healthchecks.io semantics), only touched when the watchdog itself ran fully.
heartbeat="${UBYHOST_HEARTBEAT_MONITORING_URL:-}"
if [ -n "${heartbeat}" ]; then
  if [ "${failures}" -eq 0 ]; then
    curl -fsS -m 10 --retry 2 -o /dev/null "${heartbeat}" || true
  else
    curl -fsS -m 10 --retry 2 -o /dev/null "${heartbeat}/fail" || true
  fi
fi

if [ "${failures}" -eq 0 ]; then
  echo "monitoring: OK"
  exit 0
fi
echo "monitoring: ${failures} check(s) failed"
exit 1
