#!/usr/bin/env bash
# Quick production health check.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

docker compose ps

echo ""
echo "Internal runtime (not exposed on public /healthz in production):"
if docker compose exec -T ubyhost python -c \
  "from app import config; print('deployment=', config.DEPLOYMENT); print('ubyport_env=', config.UBYPORT_ENV); print('endpoint=', config.endpoint_for()); print('scheduler=', config.ENABLE_SCHEDULER); print('role=', config.ROLE); print('guest_pin=', config.GUEST_PIN_REQUIRED); print('public_base_url=', config.PUBLIC_BASE_URL); print('data_dir=', config.DATA_DIR)" \
  2>/dev/null; then
  :
else
  echo "(ubyhost not running — start with ./scripts/deploy.sh)"
fi

echo ""
echo "Background worker (WP06):"
if docker compose exec -T worker python -c \
  "import os, time; print('worker.alive age (s)=', int(time.time() - os.path.getmtime('/data/worker.alive')))" \
  2>/dev/null; then
  :
else
  echo "(worker not running or not alive — ./scripts/logs.sh worker)"
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
