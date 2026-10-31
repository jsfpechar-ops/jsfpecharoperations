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

# PostgreSQL dump (brief 0464): into the newest snapshot folder, age-encrypted, never plaintext.
if [ -n "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
  RECIPIENT="${UBYHOST_BACKUP_AGE_RECIPIENT:-}"
  if [ -z "${RECIPIENT}" ]; then
    if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
      echo "Refusing to write an unencrypted PostgreSQL dump in production." >&2
      echo "Set UBYHOST_BACKUP_AGE_RECIPIENT to a public age1... recipient." >&2
      exit 1
    fi
    echo "WARNING: no UBYHOST_BACKUP_AGE_RECIPIENT, PostgreSQL dump skipped" >&2
  else
    command -v age >/dev/null 2>&1 || { echo "The 'age' binary is missing on the host." >&2; exit 1; }
    NEWEST="$(docker compose exec -T ubyhost sh -c 'ls -1 /data/backups | sort | tail -1')"
    [ -n "${NEWEST}" ] || { echo "No snapshot folder to hold the PostgreSQL dump." >&2; exit 1; }
    docker compose exec -T postgres pg_dump -U ubyhost -Fc ubyhost \
      | age -r "${RECIPIENT}" \
      | docker compose exec -T ubyhost sh -c "cat > /data/backups/${NEWEST}/ubyhost-pg.dump.age"
    echo "PostgreSQL dump bytes: $(docker compose exec -T ubyhost sh -c "wc -c < /data/backups/${NEWEST}/ubyhost-pg.dump.age" | tr -d '\r')"
  fi
fi

# Optional dead-man switch (e.g. healthchecks.io). Only reached on success,
# because set -e stops the script on any failure above.
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
echo "Copy backups off-server periodically (S3, Google Drive, etc.)."
