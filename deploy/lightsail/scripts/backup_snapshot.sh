# shellcheck shell=bash
# Snapshot secrets (and SQLite when not on PostgreSQL) into /data/backups/<stamp>.
# Sourced from backup.sh after data_sh is defined. Replaces App/scripts/backup_data.sh
# on the Go-only stack (no Python container).
set -euo pipefail
umask 077

DATA_DIR="${UBYHOST_DATA_DIR:-/data}"
BACKUP_ROOT="${UBYHOST_BACKUP_DIR:-${DATA_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"
suffix=0
while data_sh "test -e '${DEST}'"; do
  suffix=$((suffix + 1))
  DEST="${BACKUP_ROOT}/${STAMP}-${suffix}"
done

DEPLOYMENT="${UBYHOST_DEPLOYMENT:-local}"
RECIPIENT="${UBYHOST_BACKUP_AGE_RECIPIENT:-}"
RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"
PG_MODE=0
if [ -n "${UBYHOST_DATABASE_URL:-}" ]; then
  PG_MODE=1
fi

if [ -z "${RECIPIENT}" ] && [ "${DEPLOYMENT}" = "production" ]; then
  echo "Refusing to write an unencrypted backup in production." >&2
  echo "Set UBYHOST_BACKUP_AGE_RECIPIENT to a public age1... recipient." >&2
  return 1 2>/dev/null || exit 1
fi

data_sh "mkdir -p '${DEST}' && chmod 700 '${BACKUP_ROOT}' '${DEST}' 2>/dev/null || true"

cleanup_on_error() {
  data_sh "rm -f '${DEST}/ubyhost.db' '${DEST}/secret_key' '${DEST}/initial_admin_credentials' \
    '${DEST}/ubyhost-backup.tar' '${DEST}/ubyhost-backup.tar.age'"
  data_sh "rmdir '${DEST}' 2>/dev/null || true"
}
if [ -n "${RECIPIENT}" ]; then
  trap cleanup_on_error ERR
fi

if [ "${PG_MODE}" != "1" ]; then
  if ! data_sh "test -f '${DATA_DIR}/ubyhost.db'"; then
    echo "No database at ${DATA_DIR}/ubyhost.db" >&2
    return 1 2>/dev/null || exit 1
  fi
  if data_sh "command -v sqlite3 >/dev/null 2>&1"; then
    data_sh "sqlite3 '${DATA_DIR}/ubyhost.db' \".backup '${DEST}/ubyhost.db'\""
  else
    data_sh "cp -a '${DATA_DIR}/ubyhost.db' '${DEST}/ubyhost.db'"
  fi
fi

for extra in secret_key initial_admin_credentials; do
  data_sh "test -f '${DATA_DIR}/${extra}' && cp -a '${DATA_DIR}/${extra}' '${DEST}/${extra}'" || true
done

if ! data_sh "test -s '${DEST}/secret_key'" && [ -n "${UBYHOST_SECRET_KEY:-}" ]; then
  printf '%s\n' "${UBYHOST_SECRET_KEY}" | ubyhost_app_exec \
    sh -c "cat > '${DEST}/secret_key' && chmod 600 '${DEST}/secret_key'" || true
fi

if ! data_sh "test -s '${DEST}/secret_key'"; then
  echo "WARNING: no secret key in ${DEST}. This backup cannot be decrypted" \
    "off-site. Set UBYHOST_SECRET_KEY for the backup, or copy data/secret_key" \
    "into ${DATA_DIR}." >&2
fi

ENCRYPTED="false"
if [ -n "${RECIPIENT}" ]; then
  command -v age >/dev/null 2>&1 || {
    echo "UBYHOST_BACKUP_AGE_RECIPIENT is set but the 'age' binary is missing." >&2
    data_sh "rm -rf '${DEST}'"
    return 1 2>/dev/null || exit 1
  }
  tar_cmd="cd '${DEST}' && set --; for n in ubyhost.db secret_key initial_admin_credentials; do
    [ -f \"\$n\" ] && set -- \"\$@\" \"\$n\"; done; [ \"\$#\" -gt 0 ] || exit 1; tar -cf - \"\$@\""
  if ! ubyhost_app_service >/dev/null; then
    echo "Refusing backup: no app container is running (ubyhost-go or ubyhost-go-b on the Go-only stack, ubyhost on the Python stack)." >&2
    return 1 2>/dev/null || exit 1
  fi
  if ! ubyhost_app_exec sh -c "${tar_cmd}" | age -r "${RECIPIENT}" | data_sh "cat > '${DEST}/ubyhost-backup.tar.age'"; then
    cleanup_on_error
    return 1 2>/dev/null || exit 1
  fi
  data_sh "rm -f '${DEST}/ubyhost-backup.tar' '${DEST}/ubyhost.db' \
    '${DEST}/secret_key' '${DEST}/initial_admin_credentials'"
  ENCRYPTED="true"
  trap - ERR
fi

echo "Backup written to ${DEST} (encrypted: ${ENCRYPTED})"

newest="$(data_sh "ls -1 '${BACKUP_ROOT}' 2>/dev/null | sort | tail -n 1" || true)"
cutoff="$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%dT%H%M%SZ 2>/dev/null || date -u -v-"${RETENTION_DAYS}"d +%Y%m%dT%H%M%SZ)"
for base in $(data_sh "ls -1 '${BACKUP_ROOT}' 2>/dev/null" || true); do
  [ -n "${base}" ] || continue
  [ "${base}" = "${newest}" ] && continue
  stamp="${base%%-*}"
  case "${stamp}" in
    [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) ;;
    *) continue ;;
  esac
  if [ "${stamp}" \< "${cutoff}" ]; then
    data_sh "rm -rf '${BACKUP_ROOT}/${base}'"
  fi
done
echo "Kept snapshots from the last ${RETENTION_DAYS} days under ${BACKUP_ROOT} (newest kept)"

if [ "${ENCRYPTED}" = "true" ]; then
  BYTES="$(data_sh "wc -c < '${DEST}/ubyhost-backup.tar.age'" | tr -d '[:space:]')"
else
  BYTES="$(data_sh "wc -c < '${DEST}/ubyhost.db' 2>/dev/null" | tr -d '[:space:]')" || BYTES=0
fi
marker="$(printf '{"at": "%s", "encrypted": %s, "bytes": %s, "retention_days": %s}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${ENCRYPTED}" "${BYTES}" "${RETENTION_DAYS}")"
printf '%s' "${marker}" | data_sh "cat > '${BACKUP_ROOT}/.last_success.json' && chmod 600 '${BACKUP_ROOT}/.last_success.json'"