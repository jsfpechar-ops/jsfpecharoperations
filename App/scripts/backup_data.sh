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

echo "Backup written to ${DEST}"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d | sort -r | tail -n +11 | xargs -r rm -rf
echo "Kept the 10 most recent backups under ${BACKUP_ROOT}"
