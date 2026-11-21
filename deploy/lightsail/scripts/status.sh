#!/usr/bin/env bash
# Quick health check: containers, the internal runtime labels, the public site.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# 1999: lib-docker.sh tells these scripts whether the checkout still has the
# Python app (before 1782) or only the Go service. Sourced when present; without
# it (a trimmed fixture tree) the old Python layout is assumed, exactly as
# before, so nothing here is a new hard dependency.
if [ -f ./scripts/lib-docker.sh ]; then
  # shellcheck disable=SC1091
  source ./scripts/lib-docker.sh
else
  app_is_python() { return 0; }
  app_service() { printf 'ubyhost\n'; }
  app_running_service() { printf 'ubyhost\n'; }
  app_run() { docker compose run --rm --no-deps -T ubyhost "$@"; }
fi

docker compose ps

echo ""
echo "Internal runtime (not exposed on public /healthz in production):"
APP_SVC="$(app_running_service)"
if [ -z "${APP_SVC}" ]; then
  echo "(no app container running — start with ./scripts/deploy.sh)"
elif app_is_python; then
  docker compose exec -T "${APP_SVC}" python -c \
    "from app import config; print('deployment=', config.DEPLOYMENT); print('ubyport_env=', config.UBYPORT_ENV); print('endpoint=', config.endpoint_for()); print('scheduler=', config.ENABLE_SCHEDULER); print('role=', config.ROLE); print('guest_pin=', config.GUEST_PIN_REQUIRED); print('public_base_url=', config.PUBLIC_BASE_URL); print('data_dir=', config.DATA_DIR)" \
    2>/dev/null || echo "(ubyhost not answering — ./scripts/logs.sh)"
else
  # 1999: the Go service is the app in a Go-only stack. It prints the same
  # labels, plus the build it runs, from its own /healthz and /version.
  # Its /healthz is {status, version, data_dir_writable, database_ok}: the
  # deployment/ubyport_env labels are a Python-app detail that production hides
  # anyway, so staging is checked against the deployed commit instead.
  docker compose exec -T "${APP_SVC}" wget -qO- http://127.0.0.1:8081/healthz || \
    echo "(ubyhost-go not answering — ./scripts/logs.sh)"
  echo ""
  echo "deployed_sha=$(cat .deployed-sha 2>/dev/null || echo unknown)"
  echo "go_slot=$(cat .go-slot 2>/dev/null || echo a)"
fi

# 1999: only a checkout with the Python services has the separate worker.
if docker compose config --services 2>/dev/null | grep -qx 'worker'; then
  echo ""
  echo "Background worker (WP06):"
  if docker compose exec -T worker python -c \
    "import os, time; print('worker.alive age (s)=', int(time.time() - os.path.getmtime('/data/worker.alive')))" \
    2>/dev/null; then
    :
  else
    echo "(worker not running or not alive — ./scripts/logs.sh worker)"
  fi
fi

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
  if [ -n "${UBYHOST_PUBLIC_BASE_URL:-}" ]; then
    echo ""
    echo "Public healthz (production omits deployment/ubyport_env labels):"
    curl -fsS "${UBYHOST_PUBLIC_BASE_URL%/}/healthz" || true
    echo ""
  fi
fi

echo "Disk:"
df -h / /var/lib/docker 2>/dev/null || df -h /
