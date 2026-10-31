#!/usr/bin/env bash
# Snapshot SQLite + secrets inside the running container (age-encrypted, time-based retention; see App/scripts/backup_data.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose exec -T ubyhost bash /app/scripts/backup_data.sh
# Optional dead-man switch (e.g. healthchecks.io). Only reached on success,
# because set -e stops the script on any failure above.
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
echo "Copy backups off-server periodically (S3, Google Drive, etc.)."
