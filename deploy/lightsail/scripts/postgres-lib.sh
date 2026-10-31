#!/usr/bin/env bash
# Shared PostgreSQL overlay operations. Never print expanded Compose config.
set -euo pipefail

PG_OPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PG_OPS_ROOT}"

pg_compose() {
  local configured_profiles="${COMPOSE_PROFILES:-}"
  local active_profiles=()
  local profile
  IFS=, read -r -a configured <<<"${configured_profiles}"
  for profile in "${configured[@]}"; do
    [ -n "${profile}" ] || continue
    [ "${profile}" = "litestream" ] && continue
    active_profiles+=("${profile}")
  done
  local profile_value
  profile_value="$(IFS=,; printf '%s' "${active_profiles[*]}")"
  COMPOSE_PROFILES="${profile_value}" \
    UBYHOST_LITESTREAM_ENABLED=0 \
    docker compose --env-file .env \
      -f docker-compose.yml -f docker-compose.postgres.yml "$@"
}

load_private_env() {
  if [ ! -f .env ]; then
    echo "Missing .env in ${PG_OPS_ROOT}" >&2
    return 1
  fi
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
}

# The backend choice itself: explicit PostgreSQL URI and no contradictory SQLite
# or Litestream configuration. Every PostgreSQL command needs this.
require_postgres_identity() {
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "UBYHOST_DATABASE_URL is required for PostgreSQL operations." >&2
    return 1
  fi
  case "${UBYHOST_DATABASE_URL}" in
    postgresql://*|postgres://*) ;;
    *) echo "UBYHOST_DATABASE_URL must use a PostgreSQL URI." >&2; return 1 ;;
  esac
  if [ -n "${UBYHOST_DB:-}" ]; then
    echo "UBYHOST_DB must be unset while PostgreSQL is selected." >&2
    return 1
  fi
  case "${UBYHOST_LITESTREAM_ENABLED:-0}" in
    0|false|no|FALSE|NO|"") ;;
    *) echo "UBYHOST_LITESTREAM_ENABLED must disable SQLite Litestream for PostgreSQL." >&2; return 1 ;;
  esac
}

# Everything the Compose overlay interpolates plus the secret files it mounts.
# Needed by backup, cutover and restore alike.
require_postgres_repo_env() {
  : "${UBYHOST_PG_DATABASE:?set UBYHOST_PG_DATABASE}"
  : "${UBYHOST_PG_SUPERUSER:?set UBYHOST_PG_SUPERUSER}"
  : "${UBYHOST_PG_SUPERUSER_PASSWORD_FILE:?set UBYHOST_PG_SUPERUSER_PASSWORD_FILE}"
  : "${UBYHOST_PG_BACKREST_BUCKET:?set UBYHOST_PG_BACKREST_BUCKET}"
  : "${UBYHOST_PG_BACKREST_ENDPOINT:?set UBYHOST_PG_BACKREST_ENDPOINT}"
  : "${UBYHOST_PG_BACKREST_REGION:?set UBYHOST_PG_BACKREST_REGION}"
  : "${UBYHOST_PG_BACKREST_S3_KEY_FILE:?set UBYHOST_PG_BACKREST_S3_KEY_FILE}"
  : "${UBYHOST_PG_BACKREST_S3_SECRET_FILE:?set UBYHOST_PG_BACKREST_S3_SECRET_FILE}"
  : "${UBYHOST_PG_BACKREST_CIPHER_PASS_FILE:?set UBYHOST_PG_BACKREST_CIPHER_PASS_FILE}"
  for path in \
    "${UBYHOST_PG_SUPERUSER_PASSWORD_FILE}" \
    "${UBYHOST_PG_BACKREST_S3_KEY_FILE}" \
    "${UBYHOST_PG_BACKREST_S3_SECRET_FILE}" \
    "${UBYHOST_PG_BACKREST_CIPHER_PASS_FILE}"; do
    if [ ! -s "${path}" ]; then
      echo "Required PostgreSQL secret file is missing or empty: ${path}" >&2
      return 1
    fi
  done
}

# The age recipient is only needed where new encrypted artifacts are produced:
# SQLite cutover snapshot and the app-key bundle. Restore deliberately does not
# call this, so a disaster restore still runs if the recipient was rotated away.
require_backup_age_recipient() {
  if [ -z "${UBYHOST_BACKUP_AGE_RECIPIENT:-}" ]; then
    echo "UBYHOST_BACKUP_AGE_RECIPIENT is required for the separate age-encrypted app-key archive." >&2
    return 1
  fi
}

# Forward operations (cutover, backup, key backup): full contract.
require_postgres_backend() {
  require_postgres_identity || return 1
  require_postgres_repo_env || return 1
  require_backup_age_recipient || return 1
}

# Restore/rehearsal: everything the overlay needs, no forward-only age recipient.
require_restore_backend() {
  require_postgres_identity || return 1
  require_postgres_repo_env || return 1
}

