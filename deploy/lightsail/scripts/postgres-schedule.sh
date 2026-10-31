#!/usr/bin/env bash
# Switch only UbyHost's SQLite/PostgreSQL backup cron rows; preserve every other row.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env

STATE_DIR="${UBYHOST_PG_CUTOVER_STATE_DIR:-${HOME}/.local/state/ubyhost/postgres-cutover}"
SAVED_SQLITE="${STATE_DIR}/sqlite-backup-cron.txt"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"
current="$(crontab -l 2>/dev/null || true)"

case "${1:-}" in
  postgres)
    if [ ! -e "${SAVED_SQLITE}" ]; then
      printf '%s\n' "${current}" | while IFS= read -r line; do
        case "${line}" in
          *"${PG_OPS_ROOT}"*"./scripts/backup.sh "*|*"${PG_OPS_ROOT}"*"./scripts/backup-gdrive.sh "*|*"${PG_OPS_ROOT}"*"./scripts/backup-s3.sh "*)
            printf '%s\n' "${line}"
            ;;
        esac
      done >"${SAVED_SQLITE}"
      chmod 600 "${SAVED_SQLITE}"
    fi
    filtered="$(printf '%s\n' "${current}" | while IFS= read -r line; do
      case "${line}" in
        *"${PG_OPS_ROOT}"*"./scripts/backup.sh "*|*"${PG_OPS_ROOT}"*"./scripts/backup-gdrive.sh "*|*"${PG_OPS_ROOT}"*"./scripts/backup-s3.sh "*|*"./scripts/postgres-backup.sh "*|*"./scripts/postgres-key-backup.sh "*) ;;
        *) [ -n "${line}" ] && printf '%s\n' "${line}" ;;
      esac
    done)"
    filtered="${filtered}
0 3 * * * cd '${PG_OPS_ROOT}' && ./scripts/postgres-backup.sh full >> "${HOME}/ubyhost-postgres-backup.log" 2>&1
30 3 * * * cd '${PG_OPS_ROOT}' && ./scripts/postgres-key-backup.sh >> "${HOME}/ubyhost-postgres-key-backup.log" 2>&1"
    printf '%s\n' "${filtered}" | crontab -
    echo "Installed daily PostgreSQL full-backup and age key-bundle jobs; prior SQLite rows saved."
    ;;
  sqlite)
    filtered="$(printf '%s\n' "${current}" | while IFS= read -r line; do
      case "${line}" in
        *"./scripts/postgres-backup.sh "*|*"./scripts/postgres-key-backup.sh "*) ;;
        *) [ -n "${line}" ] && printf '%s\n' "${line}" ;;
      esac
    done)"
    if [ -f "${SAVED_SQLITE}" ]; then
      saved="$(cat "${SAVED_SQLITE}")"
      [ -z "${saved}" ] || filtered="${filtered}
${saved}"
    fi
    printf '%s\n' "${filtered}" | crontab -
    echo "Restored the captured SQLite backup jobs and removed PostgreSQL backup jobs."
    ;;
  status)
    crontab -l 2>/dev/null | grep -E 'scripts/(postgres-backup|postgres-key-backup|backup|backup-gdrive|backup-s3)\.sh' || true
    ;;
  *)
    echo "Usage: $0 {postgres|sqlite|status}" >&2
    exit 2
    ;;
esac
