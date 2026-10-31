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

require_postgres_backend() {
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
  if [ -z "${UBYHOST_BACKUP_AGE_RECIPIENT:-}" ]; then
    echo "UBYHOST_BACKUP_AGE_RECIPIENT is required for the separate age-encrypted app-key archive." >&2
    return 1
  fi
}

