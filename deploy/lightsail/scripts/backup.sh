#!/usr/bin/env bash
# Snapshot secrets (+ SQLite when not on PostgreSQL) and optional pg_dump into /data/backups.
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

data_sh() {
  if docker compose --profile go ps -q --status running ubyhost-go 2>/dev/null | grep -q .; then
    docker compose --profile go exec -T ubyhost-go sh -c "$1"
  elif docker compose config --services 2>/dev/null | grep -qx ubyhost \
    && docker compose ps -q --status running ubyhost 2>/dev/null | grep -q .; then
    docker compose exec -T ubyhost sh -c "$1"
  else
    echo "Refusing backup: ubyhost-go must be running (Go-only stack has no ubyhost container)." >&2
    return 1
  fi
}

run_backup_snapshot() {
  if docker compose config --services 2>/dev/null | grep -qx ubyhost; then
    docker compose exec -T ubyhost bash /app/scripts/backup_data.sh
    return
  fi
  # shellcheck source=scripts/backup_snapshot.sh
  # shellcheck disable=SC1091
  source "${ROOT}/scripts/backup_snapshot.sh"
}

# Brief 1020: in production on PostgreSQL, never take or prune a snapshot while postgres is down.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -n "${UBYHOST_DATABASE_URL:-}" ] \
  && [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
  echo "Refusing to finish: the postgres container is not running in production, so no PostgreSQL dump can be taken." >&2
  exit 1
fi

run_backup_snapshot

# PostgreSQL dump (brief 0464): into the newest snapshot folder, age-encrypted, never plaintext.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "Refusing to finish: UBYHOST_DATABASE_URL is unset in production, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
  if [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
    echo "Refusing to finish: the postgres container stopped during the backup, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
fi

if [ -n "${UBYHOST_DATABASE_URL:-}" ] && [ -n "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
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
    NEWEST="$(data_sh 'ls -1 /data/backups | sort | tail -1')"
    [ -n "${NEWEST}" ] || { echo "No snapshot folder to hold the PostgreSQL dump." >&2; exit 1; }
    data_sh "rm -f /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp"
    docker compose exec -T postgres pg_dump -U ubyhost -Fc ubyhost --exclude-table-data=ruian_address \
      | age -r "${RECIPIENT}" \
      | data_sh "cat > /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp && mv /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp /data/backups/${NEWEST}/ubyhost-pg.dump.age"
    echo "PostgreSQL dump bytes: $(data_sh "wc -c < /data/backups/${NEWEST}/ubyhost-pg.dump.age" | tr -d '\r')"
  fi
fi

if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
echo "Copy backups off-server periodically (S3, Google Drive, etc.)."
