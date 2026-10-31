#!/usr/bin/env bash
# Create/refresh the proposed least-privilege PostgreSQL roles (brief 0456).
#
# This is an OWNER-DECISION proposal: it never changes UBYHOST_DATABASE_URL.
# Passwords come from 0600 files and are passed to psql as environment variables
# (docker compose exec -e passthrough), never on a command line and never echoed.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
# Overlay + secret files only: role creation does not need the age recipient.
require_restore_backend

APP_PASSWORD_FILE="${UBYHOST_PG_APP_PASSWORD_FILE:-}"
MIGRATION_PASSWORD_FILE="${UBYHOST_PG_MIGRATION_PASSWORD_FILE:-}"
BACKUP_PASSWORD_FILE="${UBYHOST_PG_BACKUP_PASSWORD_FILE:-}"

require_password_file() {
  local path="$1" label="$2"
  if [ -z "${path}" ]; then
    echo "${label} is required (a 0600 file containing only the password)." >&2
    exit 1
  fi
  case "${path}" in
    /*) ;;
    *) echo "${label} must be an absolute path." >&2; exit 1 ;;
  esac
  if [ -L "${path}" ] || [ ! -f "${path}" ] || [ ! -s "${path}" ]; then
    echo "${label} is missing, empty or a symlink: ${path}" >&2
    exit 1
  fi
}

require_password_file "${APP_PASSWORD_FILE}" "UBYHOST_PG_APP_PASSWORD_FILE"
require_password_file "${MIGRATION_PASSWORD_FILE}" "UBYHOST_PG_MIGRATION_PASSWORD_FILE"

if ! pg_compose exec -T postgres pg_isready \
  -U "${UBYHOST_PG_SUPERUSER}" -d "${UBYHOST_PG_DATABASE}" >/dev/null; then
  echo "PostgreSQL is not healthy; no role was changed." >&2
  exit 1
fi

# Exported for `docker compose exec -e VAR` passthrough. The names, not the
# values, are what appear in the compose argv.
UBYHOST_ROLE_APP_PASSWORD="$(cat "${APP_PASSWORD_FILE}")"
UBYHOST_ROLE_MIGRATION_PASSWORD="$(cat "${MIGRATION_PASSWORD_FILE}")"
export UBYHOST_ROLE_APP_PASSWORD UBYHOST_ROLE_MIGRATION_PASSWORD

skip_backup=1
if [ -n "${BACKUP_PASSWORD_FILE}" ]; then
  require_password_file "${BACKUP_PASSWORD_FILE}" "UBYHOST_PG_BACKUP_PASSWORD_FILE"
  UBYHOST_ROLE_BACKUP_PASSWORD="$(cat "${BACKUP_PASSWORD_FILE}")"
  export UBYHOST_ROLE_BACKUP_PASSWORD
  skip_backup=0
fi
export UBYHOST_ROLE_SKIP_BACKUP="${skip_backup}"

exec_args=(
  -e UBYHOST_ROLE_APP_PASSWORD
  -e UBYHOST_ROLE_MIGRATION_PASSWORD
  -e UBYHOST_ROLE_SKIP_BACKUP
)
if [ "${skip_backup}" = 0 ]; then
  exec_args+=(-e UBYHOST_ROLE_BACKUP_PASSWORD)
fi

pg_compose exec -T "${exec_args[@]}" postgres \
  psql -X -q -v ON_ERROR_STOP=1 \
    -U "${UBYHOST_PG_SUPERUSER}" -d "${UBYHOST_PG_DATABASE}" \
  <"${PG_OPS_ROOT}/postgres/roles.sql"

# Verify the app role really is least-privilege: login works, DDL is refused.
if ! pg_compose exec -T postgres psql -X -qAt \
  -U ubyhost_app -d "${UBYHOST_PG_DATABASE}" -c "SELECT current_user" \
  | grep -qx "ubyhost_app"; then
  echo "ubyhost_app cannot log in after the role bootstrap." >&2
  exit 1
fi
if pg_compose exec -T postgres psql -X -q \
  -U ubyhost_app -d "${UBYHOST_PG_DATABASE}" \
  -c "CREATE TABLE ubyhost_app_must_not_create (x integer)" >/dev/null 2>&1; then
  echo "ubyhost_app unexpectedly has DDL rights; refusing to report success." >&2
  exit 1
fi
if ! pg_compose exec -T postgres psql -X -qAt \
  -U ubyhost_migrate -d "${UBYHOST_PG_DATABASE}" -c "SELECT current_user" \
  | grep -qx "ubyhost_migrate"; then
  echo "ubyhost_migrate cannot log in after the role bootstrap." >&2
  exit 1
fi

printf '%s\n' "Role proposal applied: ubyhost_app (login + DML, DDL refused) and ubyhost_migrate (login + DDL)."
printf '%s\n' "UBYHOST_DATABASE_URL was NOT changed; read the owner runbook section 9 before switching the app DSN."
