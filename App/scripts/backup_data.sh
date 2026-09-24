#!/usr/bin/env bash
# Snapshot the SQLite database and secret key to a timestamped folder.
# Run on the server (cron weekly) or copy backups off-site after each run.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${UBYHOST_DATA_DIR:-${ROOT}/data}"
BACKUP_ROOT="${UBYHOST_BACKUP_DIR:-${DATA_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"
suffix=0
while [ -e "${DEST}" ]; do
  suffix=$((suffix + 1))
  DEST="${BACKUP_ROOT}/${STAMP}-${suffix}"
done

mkdir -p "${DEST}"
chmod 700 "${BACKUP_ROOT}" "${DEST}" 2>/dev/null || true

DB="${UBYHOST_DB:-${DATA_DIR}/ubyhost.db}"
if [ ! -f "${DB}" ]; then
  echo "No database at ${DB}" >&2
  exit 1
fi

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "${DB}" ".backup '${DEST}/ubyhost.db'"
else
  cp -a "${DB}" "${DEST}/ubyhost.db"
fi

for extra in secret_key initial_admin_credentials; do
  if [ -f "${DATA_DIR}/${extra}" ]; then
    cp -a "${DATA_DIR}/${extra}" "${DEST}/${extra}"
  fi
done

# Production keeps the key in .env rather than in a file, and a backup without
# it cannot be decrypted anywhere but on the machine that made it. Write it
# alongside the snapshot when it was supplied through the environment.
if [ ! -f "${DEST}/secret_key" ] && [ -n "${UBYHOST_SECRET_KEY:-}" ]; then
  printf '%s\n' "${UBYHOST_SECRET_KEY}" > "${DEST}/secret_key"
  chmod 600 "${DEST}/secret_key"
fi

if [ ! -f "${DEST}/secret_key" ]; then
  echo "WARNING: no secret key in ${DEST}. This backup cannot be decrypted" \
    "off-site. Set UBYHOST_SECRET_KEY for the backup, or copy data/secret_key" \
    "into ${DATA_DIR}." >&2
fi

echo "Backup written to ${DEST}"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d | sort -r | tail -n +11 | xargs -r rm -rf
echo "Kept the 10 most recent backups under ${BACKUP_ROOT}"
