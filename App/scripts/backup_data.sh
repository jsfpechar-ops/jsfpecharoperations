#!/usr/bin/env bash
# Snapshot the SQLite database and secret key to a timestamped folder, then
# encrypt the snapshot with age when a recipient is configured.
#
# In production a recipient is **required**: a backup that carries the key
# beside an unencrypted database is as readable as the plaintext was. Outside
# production the plaintext layout is kept, so local development still works.
#
# Env:
#   UBYHOST_BACKUP_AGE_RECIPIENT   public age1... recipient (required in production)
#   UBYHOST_BACKUP_RETENTION_DAYS  time-based retention window (default 30)
#   UBYHOST_DEPLOYMENT             production makes the recipient mandatory
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

DEPLOYMENT="${UBYHOST_DEPLOYMENT:-local}"
RECIPIENT="${UBYHOST_BACKUP_AGE_RECIPIENT:-}"
RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"

# Fail closed: in production, never write a snapshot that carries its own key
# in the clear. Nothing is created, so there is no half-written snapshot.
if [ -z "${RECIPIENT}" ] && [ "${DEPLOYMENT}" = "production" ]; then
  echo "Refusing to write an unencrypted backup in production." >&2
  echo "Set UBYHOST_BACKUP_AGE_RECIPIENT to a public age1... recipient." >&2
  exit 1
fi

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

ENCRYPTED="false"
if [ -n "${RECIPIENT}" ]; then
  if ! command -v age >/dev/null 2>&1; then
    echo "UBYHOST_BACKUP_AGE_RECIPIENT is set but the 'age' binary is missing." >&2
    rm -rf "${DEST}"
    exit 1
  fi

  # Tar the snapshot, encrypt it, then delete every plaintext file from the
  # snapshot directory. `rm -f` under `umask 077` is deliberate: `shred` cannot
  # be trusted on an overlay filesystem.
  files=()
  for name in ubyhost.db secret_key initial_admin_credentials; do
    [ -f "${DEST}/${name}" ] && files+=("${name}")
  done
  tar -C "${DEST}" -cf "${DEST}/ubyhost-backup.tar" "${files[@]}"
  age -r "${RECIPIENT}" -o "${DEST}/ubyhost-backup.tar.age" "${DEST}/ubyhost-backup.tar"
  rm -f "${DEST}/ubyhost-backup.tar" "${DEST}/ubyhost.db" \
    "${DEST}/secret_key" "${DEST}/initial_admin_credentials"
  ENCRYPTED="true"
fi

echo "Backup written to ${DEST} (encrypted: ${ENCRYPTED})"

# Retention is by time, not by count: a snapshot older than the window is
# removed, but the newest one is always kept even if it is older than the
# window (so a host that stopped backing up does not lose their last copy).
newest="$(find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -n 1)"
cutoff="$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%dT%H%M%SZ)"
for dir in "${BACKUP_ROOT}"/*/; do
  [ -d "${dir}" ] || continue
  base="$(basename "${dir}")"
  [ "${base}" = "${newest}" ] && continue
  stamp="${base%%-*}"
  case "${stamp}" in
    [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;;
    *) continue ;;
  esac
  if [ "${stamp}" \< "${cutoff}" ]; then
    rm -rf "${dir}"
  fi
done
echo "Kept snapshots from the last ${RETENTION_DAYS} days under ${BACKUP_ROOT} (newest kept)"

if [ "${ENCRYPTED}" = "true" ]; then
  BYTES="$(stat -c%s "${DEST}/ubyhost-backup.tar.age" 2>/dev/null || echo 0)"
else
  BYTES="$(stat -c%s "${DEST}/ubyhost.db" 2>/dev/null || echo 0)"
fi
printf '{"at": "%s", "encrypted": %s, "bytes": %s, "retention_days": %s}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${ENCRYPTED}" "${BYTES}" "${RETENTION_DAYS}" \
  > "${BACKUP_ROOT}/.last_success.json"
chmod 600 "${BACKUP_ROOT}/.last_success.json"
