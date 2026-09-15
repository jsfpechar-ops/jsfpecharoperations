#!/usr/bin/env bash
# Restore ubyhost.db (and secret_key if present) from a snapshot on the volume.
#
# Usage (from deploy/lightsail):
#   ./scripts/restore.sh                  # interactive: latest /data/backups stamp
#   ./scripts/restore.sh 20260915T030000Z
#   RESTORE_CONFIRM=yes ./scripts/restore.sh 20260915T030000Z
#
# Always stop the app first so SQLite is not written during the copy.
# Container files are owned by uid 10001 (see Dockerfile).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

STAMP="${1:-}"
CONFIRM="${RESTORE_CONFIRM:-}"

list_stamps() {
  docker compose exec -T ubyhost sh -c 'ls -1 /data/backups 2>/dev/null | sort -r' || true
}

if [ -z "${STAMP}" ]; then
  echo "Available stamps on volume (newest first):"
  list_stamps
  echo ""
  read -r -p "Stamp to restore (or empty to abort): " STAMP
fi

if [ -z "${STAMP}" ]; then
  echo "No stamp given — abort." >&2
  exit 1
fi

if [ "${CONFIRM}" != "yes" ]; then
  echo "This replaces /data/ubyhost.db with backups/${STAMP}/ubyhost.db"
  echo "Host login cookies stay valid only if secret_key is restored too."
  read -r -p "Type yes to continue: " CONFIRM
fi
if [ "${CONFIRM}" != "yes" ]; then
  echo "Aborted." >&2
  exit 1
fi

echo "==> Stopping ubyhost (Caddy stays up and will 502 until restart)"
docker compose stop ubyhost

echo "==> Restoring ${STAMP}"
docker compose run --rm --user 0 --no-deps --entrypoint bash ubyhost -lc "
  set -euo pipefail
  SRC=/data/backups/${STAMP}
  if [ ! -f \"\${SRC}/ubyhost.db\" ]; then
    echo \"Missing \${SRC}/ubyhost.db\" >&2
    ls -la /data/backups >&2 || true
    exit 1
  fi
  cp -a \"\${SRC}/ubyhost.db\" /data/ubyhost.db
  if [ -f \"\${SRC}/secret_key\" ]; then
    cp -a \"\${SRC}/secret_key\" /data/secret_key
  fi
  chown 10001:10001 /data/ubyhost.db
  [ -f /data/secret_key ] && chown 10001:10001 /data/secret_key
  chmod 600 /data/ubyhost.db /data/secret_key 2>/dev/null || true
  echo Restored from \${SRC}
"

echo "==> Starting ubyhost"
docker compose up -d ubyhost

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    echo "Restore complete. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "ubyhost did not become healthy — run ./scripts/logs.sh ubyhost" >&2
exit 1
