#!/usr/bin/env bash
# Owner-operated PostgreSQL state machine. A failure leaves maintenance on.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env

STATE_DIR="${UBYHOST_PG_CUTOVER_STATE_DIR:-${HOME}/.local/state/ubyhost/postgres-cutover}"
PHASE_FILE="${STATE_DIR}/phase"
LAST_STAMP_FILE="${STATE_DIR}/transfer-stamp"
WRITERS_MARKER="${STATE_DIR}/postgres-writers-enabled"

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

state() {
  if [ -f "${PHASE_FILE}" ]; then cat "${PHASE_FILE}"; else printf '%s\n' idle; fi
}

set_state() {
  local next="$1" temp="${PHASE_FILE}.tmp"
  printf '%s\n' "${next}" >"${temp}"
  chmod 600 "${temp}"
  mv "${temp}" "${PHASE_FILE}"
}

require_state() {
  local expected="$1" actual
  actual="$(state)"
  if [ "${actual}" != "${expected}" ]; then
    echo "Cutover phase is ${actual}; this command requires ${expected}." >&2
    return 1
  fi
}

set_env_value() {
  local key="$1" value="$2"
  python3 - "$PG_OPS_ROOT/.env" "${key}" "${value}" <<'PY'
from pathlib import Path
import os
import sys

path = Path(sys.argv[1])
key, value = sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
found = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
if len(found) > 1:
    raise SystemExit(f"{key} appears more than once in .env; refusing to edit")
if found:
    lines[found[0]] = f"{key}={value}"
else:
    lines.append(f"{key}={value}")
mode = path.stat().st_mode & 0o777
path.write_text("\n".join(lines) + "\n")
os.chmod(path, mode)
PY
  export "${key}=${value}"
}

remove_env_value() {
  local key="$1"
  python3 - "$PG_OPS_ROOT/.env" "${key}" <<'PY'
from pathlib import Path
import os
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
mode = path.stat().st_mode & 0o777
lines = path.read_text().splitlines()
kept = [line for line in lines if not line.startswith(key + "=")]
path.write_text("\n".join(kept) + "\n")
os.chmod(path, mode)
PY
  unset "${key}"
}

save_pre_cutover_settings() {
  local profiles="${COMPOSE_PROFILES:-}" litestream="${UBYHOST_LITESTREAM_ENABLED:-}"
  printf '%s' "${profiles}" >"${STATE_DIR}/previous-compose-profiles"
  printf '%s' "${litestream}" >"${STATE_DIR}/previous-litestream-enabled"
  chmod 600 "${STATE_DIR}/previous-compose-profiles" "${STATE_DIR}/previous-litestream-enabled"
}

maintenance_on() {
  set_env_value UBYHOST_MAINTENANCE 1
  pg_compose up -d --no-deps caddy
  pg_compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
  local response
  response="$(curl -kfsS -o /dev/null -w '%{http_code}' \
    --resolve "${UBYHOST_DOMAIN}:443:127.0.0.1" \
    "https://${UBYHOST_DOMAIN}/healthz" || true)"
  if [ "${response}" != "503" ]; then
    echo "Caddy did not return the expected maintenance 503 on loopback (got ${response:-no-response})." >&2
    return 1
  fi
}

ensure_app_stopped() {
  local running
  running="$(pg_compose ps --status running --services 2>/dev/null || true)"
  if printf '%s\n' "${running}" | grep -Eq '^(ubyhost|worker)$'; then
    echo "Web or worker is still running; PostgreSQL cutover remains in maintenance." >&2
    return 1
  fi
}

upload_cutover_snapshot() {
  local stamp="$1" remote prefix temp artifact
  remote="${RCLONE_REMOTE:-s3}"
  prefix="${UBYHOST_PG_CUTOVER_PREFIX:-UbyHost-postgres-cutover}"
  temp="$(mktemp "${TMPDIR:-/tmp}/ubyhost-pg-cutover.XXXXXX")"
  chmod 600 "${temp}"
  artifact="/data/backups/postgres-cutover/ubyhost-sqlite-cutover-${stamp}.sqlite.age"
  if ! pg_compose run --rm --no-deps -T --entrypoint sh ubyhost -c \
    "cat '${artifact}'" >"${temp}"; then
    rm -f "${temp}"
    echo "Could not read encrypted cutover artifact from the data volume." >&2
    return 1
  fi
  if [ ! -s "${temp}" ]; then
    rm -f "${temp}"
    echo "Encrypted cutover artifact is missing or empty." >&2
    return 1
  fi
  rclone copyto "${temp}" "${remote}:${UBYHOST_S3_BUCKET:?set UBYHOST_S3_BUCKET}/${prefix}/ubyhost-sqlite-cutover-${stamp}.sqlite.age"
  rclone check "${temp}" "${remote}:${UBYHOST_S3_BUCKET}/${prefix}/ubyhost-sqlite-cutover-${stamp}.sqlite.age" --download
  rm -f "${temp}"
}

case "${1:-}" in
  prepare)
    require_postgres_backend

    require_state idle
    if [ -e "${WRITERS_MARKER}" ] || pg_compose run --rm --no-deps -T --entrypoint sh ubyhost -c 'test -e /data/database-authority.json'; then
      echo "PostgreSQL authority marker exists; refusing a SQLite cutover workflow." >&2
      exit 1
    fi
    save_pre_cutover_settings
    maintenance_on
    set_state maintenance
    ;;
  stop-writers)
    require_postgres_backend
    require_state maintenance
    pg_compose stop worker ubyhost
    ensure_app_stopped
    set_state writers_stopped
    ;;
  start-postgres)
    require_postgres_backend
    require_state writers_stopped
    pg_compose up -d postgres
    healthy=0
    for _ in $(seq 1 60); do
      if pg_compose exec -T postgres pg_isready \
        -U "${UBYHOST_PG_SUPERUSER}" -d "${UBYHOST_PG_DATABASE}" >/dev/null 2>&1; then
        healthy=1
        break
      fi
      sleep 2
    done
    if [ "${healthy}" != 1 ]; then
      echo "PostgreSQL did not become healthy; writers remain stopped and maintenance stays on." >&2
      exit 1
    fi
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost stanza-create
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
    set_state postgres_ready
    ;;
  transfer)
    require_postgres_backend
    require_state postgres_ready
    ensure_app_stopped
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    printf '%s' "${stamp}" >"${LAST_STAMP_FILE}"
    chmod 600 "${LAST_STAMP_FILE}"
    # Set a durable ambiguity marker before any transfer write can begin.
    set_state transfer_in_progress
    if ! pg_compose run --rm --no-deps -T --entrypoint bash ubyhost \
      /app/scripts/postgres_cutover_transfer.sh "${stamp}"; then
      echo "Transfer failed or its outcome is ambiguous. Keep maintenance and do not restart SQLite." >&2
      exit 1
    fi
    set_state transfer_pending_offsite
    if ! upload_cutover_snapshot "${stamp}"; then
      echo "Transfer completed locally but off-host artifact verification failed; remain in maintenance." >&2
      exit 1
    fi
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost --type=full backup
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
    set_state transferred
    printf 'Transfer and encrypted off-host source snapshot verified: %s\n' "${stamp}"
    ;;
  upload-final-snapshot)
    require_postgres_backend
    require_state transfer_pending_offsite
    stamp="$(cat "${LAST_STAMP_FILE}")"
    upload_cutover_snapshot "${stamp}"
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost --type=full backup
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
    set_state transferred
    printf 'Encrypted off-host source snapshot verified: %s\n' "${stamp}"
    ;;
  transfer-recovery-verify)
    require_postgres_backend
    require_state transfer_in_progress
    ensure_app_stopped
    stamp="$(cat "${LAST_STAMP_FILE}")"
    artifact="/data/backups/postgres-cutover/ubyhost-sqlite-cutover-${stamp}.sqlite.age"
    if [ ! -s "${artifact}" ] || ! head -c 21 "${artifact}" | grep -q 'age-encryption.org/v1'; then
      echo "Encrypted source artifact is missing or invalid; preserve PostgreSQL and investigate." >&2
      exit 1
    fi
    pg_compose run --rm --no-deps -T --entrypoint bash ubyhost \
      /app/scripts/postgres_cutover_transfer.sh --verify-only "${stamp}"
    set_state transfer_pending_offsite
    ;;
  authorize-postgres-writers)
    require_postgres_backend
    require_state transferred
    if [ "${2:-}" != "--owner-ack=POSTGRES_IS_AUTHORITATIVE" ]; then
      echo "Required explicit flag: --owner-ack=POSTGRES_IS_AUTHORITATIVE" >&2
      exit 2
    fi
    pg_compose run --rm --no-deps -T --entrypoint python ubyhost \
      scripts/pg_schema.py seal-authority --expect-database "${UBYHOST_PG_DATABASE}"
    printf '{"at":"%s","state":"postgres-authoritative"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"${WRITERS_MARKER}"
    chmod 600 "${WRITERS_MARKER}"
    set_state postgres_authoritative
    ;;
  start-writers)
    require_postgres_backend
    require_state postgres_authoritative
    [ -s "${WRITERS_MARKER}" ] || { echo "Missing durable PostgreSQL writer marker." >&2; exit 1; }
    pg_compose run --rm --no-deps -T --entrypoint sh ubyhost -c 'test -s /data/database-authority.json'
    set_state writers_enabled
    pg_compose up -d --no-deps ubyhost worker
    ;;
  finish-live)
    require_postgres_backend
    require_state writers_enabled
    if [ "${2:-}" != "--owner-ack=POST_CUTOVER_CHECKS_PASSED" ]; then
      echo "Required explicit flag: --owner-ack=POST_CUTOVER_CHECKS_PASSED" >&2
      exit 2
    fi
    if ! pg_compose exec -T ubyhost python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"; then
      echo "Web health failed; retain maintenance and PostgreSQL authority." >&2
      exit 1
    fi
    if ! pg_compose exec -T worker python -c \
      "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/data/worker.alive') < 120 else 1)"; then
      echo "Worker is not healthy; retain maintenance and PostgreSQL authority." >&2
      exit 1
    fi
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
    ./scripts/postgres-status.sh
    ./scripts/postgres-schedule.sh postgres
    set_env_value UBYHOST_MAINTENANCE 0
    pg_compose up -d --no-deps caddy
    set_state live
    printf '%s\n' "PostgreSQL writers are active. SQLite rollback is permanently refused by this state machine."
    ;;
  abort-to-sqlite)
    require_postgres_backend
    phase="$(state)"
    case "${phase}" in
      maintenance|writers_stopped|postgres_ready) ;;
      *) echo "Refusing SQLite restart from phase ${phase}; transfer may have written PostgreSQL." >&2; exit 1 ;;
    esac
    if [ -e "${WRITERS_MARKER}" ] || pg_compose run --rm --no-deps -T --entrypoint sh ubyhost -c 'test -e /data/database-authority.json'; then
      echo "PostgreSQL authority marker exists; stale SQLite rollback is unsafe." >&2
      exit 1
    fi
    pg_compose stop worker ubyhost postgres || true
    ensure_app_stopped
    # An empty UBYHOST_DATABASE_URL= is contradictory config (0455 rejects
    # "set but empty"), so remove the line instead of blanking it.
    remove_env_value UBYHOST_DATABASE_URL
    set_env_value COMPOSE_PROFILES "$(cat "${STATE_DIR}/previous-compose-profiles")"
    set_env_value UBYHOST_LITESTREAM_ENABLED "$(cat "${STATE_DIR}/previous-litestream-enabled")"
    unset COMPOSE_FILE
    docker compose --env-file .env up -d ubyhost worker
    set_env_value UBYHOST_MAINTENANCE 0
    docker compose --env-file .env up -d --no-deps caddy
    set_state aborted_to_sqlite
    ;;
  status)
    printf 'phase=%s\n' "$(state)"
    [ ! -e "${WRITERS_MARKER}" ] || printf '%s\n' "postgres-writers-enabled=yes"
    ;;
  *)
    echo "Usage: $0 {prepare|stop-writers|start-postgres|transfer|transfer-recovery-verify|upload-final-snapshot|authorize-postgres-writers --owner-ack=POSTGRES_IS_AUTHORITATIVE|start-writers|finish-live --owner-ack=POST_CUTOVER_CHECKS_PASSED|abort-to-sqlite|status}" >&2
    exit 2
    ;;
esac
