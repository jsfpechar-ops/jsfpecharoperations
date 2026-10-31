#!/usr/bin/env bash
# Select the PostgreSQL Compose overlay only when the explicit PG URI is set.
configure_postgres_compose() {
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    return 0
  fi
  if [ -n "${UBYHOST_DB:-}" ]; then
    echo "UBYHOST_DB must be unset when UBYHOST_DATABASE_URL is set." >&2
    return 1
  fi
  case "${UBYHOST_LITESTREAM_ENABLED:-0}" in
    0|false|no|FALSE|NO|"") ;;
    *) echo "Disable SQLite Litestream before selecting PostgreSQL." >&2; return 1 ;;
  esac
  COMPOSE_FILE="docker-compose.yml:docker-compose.postgres.yml"
  export COMPOSE_FILE UBYHOST_LITESTREAM_ENABLED=0
  local configured=() filtered=() profile
  IFS=, read -r -a configured <<<"${COMPOSE_PROFILES:-}"
  for profile in "${configured[@]}"; do
    [ -n "${profile}" ] || continue
    [ "${profile}" = "litestream" ] && continue
    filtered+=("${profile}")
  done
  COMPOSE_PROFILES="$(IFS=,; printf '%s' "${filtered[*]}")"
  export COMPOSE_PROFILES
}
