#!/usr/bin/env bash
# 1023: daily WAL-G base backup, then keep the newest 7 (7 days). Cron 04:30 UTC,
# after backup.sh and the S3 copy (docs/LIGHTSAIL.md). The pg_dump backup stays
# the primary copy; this is the point-in-time path. Runbook: docs/OPERATIONS.md.
# A failed backup-push stops here: nothing is deleted and no ping is sent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

docker compose exec -T walg wal-g backup-push /var/lib/postgresql/data
docker compose exec -T walg wal-g delete retain FULL 7 --confirm

if [ -n "${UBYHOST_WALG_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_WALG_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: base backup succeeded but the ping to UBYHOST_WALG_BACKUP_PING_URL failed" >&2
fi
echo "WAL-G base backup done; kept the newest 7."
