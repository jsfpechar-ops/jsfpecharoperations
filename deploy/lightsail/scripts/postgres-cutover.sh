#!/usr/bin/env bash
# Owner-operated PostgreSQL state machine. A failure leaves maintenance on.
#
# Every mutating verb takes an exclusive flock, so two operators (or a cron)
# cannot interleave phases. `status` reads without the lock.
#
# State lives in a stable, user-independent directory by default. It used to be
# under $HOME, which silently pointed at a different state when the cutover ran
# as one user but deploy.sh/root looked at another.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env

STATE_DIR="${UBYHOST_PG_CUTOVER_STATE_DIR:-${PG_OPS_ROOT}/.postgres-cutover-state}"
PHASE_FILE="${STATE_DIR}/phase"
LAST_STAMP_FILE="${STATE_DIR}/transfer-stamp"
WRITERS_MARKER="${STATE_DIR}/postgres-writers-enabled"
LITESTREAM_MARKER="${STATE_DIR}/previous-litestream-running"
LOCK_FILE="${STATE_DIR}/lock"

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

verb="${1:-}"
if [ "${verb}" != "status" ]; then
  if ! command -v flock >/dev/null 2>&1; then
    echo "flock (util-linux) is required so two cutover commands cannot interleave." >&2
    exit 1
  fi
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "Another PostgreSQL cutover command holds ${LOCK_FILE}; wait for it to finish." >&2
    exit 1
  fi
fi

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

# Print present|absent for a path inside the ubyhost image, and fail (non-zero)
# when the container could not be inspected. Callers must treat that failure as
# "unknown" instead of "absent": every check below fails closed.
container_path_state() {
  local path="$1" out
  out="$(pg_compose run --rm --no-deps -T --entrypoint sh ubyhost -c \
    "if [ -e '${path}' ]; then printf present; else printf absent; fi" 2>/dev/null)" || return 2
  case "${out}" in
    present|absent) printf '%s' "${out}" ;;
    *) return 2 ;;
  esac
}

# 0 = durable PostgreSQL authority marker present, 1 = absent, 2 = unknown.
postgres_authority_present() {
  local marker_state
  marker_state="$(container_path_state /data/database-authority.json)" || return 2
  [ "${marker_state}" = "present" ]
}

# 0 = target schema empty, 1 = target has objects, 2 = could not inspect.
postgres_target_empty() {
  local relation
  if ! relation="$(pg_compose exec -T postgres psql -X -qAt -v ON_ERROR_STOP=1 \
    -U "${UBYHOST_PG_SUPERUSER}" -d "${UBYHOST_PG_DATABASE}" -c \
    "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = current_schema() LIMIT 1")"; then
    echo "Could not inspect the PostgreSQL target schema; refusing to guess." >&2
    return 2
  fi
  [ -z "${relation}" ]
}

maintenance_on() {
  set_env_value UBYHOST_MAINTENANCE 1
  # --force-recreate is deliberate: Compose only recreates on a detected config
  # change, and a stale container would keep serving production while the phase
  # file already says maintenance.
  pg_compose up -d --no-deps --force-recreate caddy
  if ! pg_compose exec -T caddy caddy validate \
    --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null; then
    echo "Caddy rejected the mounted Caddyfile with UBYHOST_MAINTENANCE=1; maintenance is not proven." >&2
    return 1
  fi
  # Deterministic proof that the running container carries the flag. A loopback
  # curl cannot observe the 503: 127.0.0.1 is not in Cloudflare's ranges, so the
  # 0421 abort guard closes the connection before the maintenance handler runs.
  # Confirming the visible page through Cloudflare is an explicit owner step in
  # docs/plans/postgresql/owner-cutover-runbook.md.
  local flag_value
  if ! flag_value="$(pg_compose exec -T caddy printenv UBYHOST_MAINTENANCE 2>/dev/null | tr -d '\r\n')"; then
    echo "Could not read UBYHOST_MAINTENANCE from the running caddy container." >&2
    return 1
  fi
  if [ "${flag_value}" != "1" ]; then
    echo "Caddy container does not carry UBYHOST_MAINTENANCE=1 (got '${flag_value:-empty}'); maintenance is not proven." >&2
    return 1
  fi
}

ensure_app_stopped() {
  local running
  if ! running="$(pg_compose ps --status running --services 2>/dev/null)"; then
    echo "Could not query Compose service state; refusing to treat writers as stopped." >&2
    return 1
  fi
  if printf '%s\n' "${running}" | grep -Eq '^(ubyhost|worker)$'; then
    echo "Web or worker is still running; PostgreSQL cutover remains in maintenance." >&2
    return 1
  fi
}

# Running Litestream containers, addressed by Compose labels because the replica
# is not part of the PostgreSQL Compose profile.
litestream_container_ids() {
  docker ps -q \
    --filter "label=com.docker.compose.project=ubyhost" \
    --filter "label=com.docker.compose.service=litestream"
}

# Stop the SQLite replica before the final snapshot. SIGTERM lets Litestream
# flush; the previous running/stopped state is recorded so abort-to-sqlite can
# put it back.
stop_litestream() {
  local ids id
  if ! ids="$(litestream_container_ids)"; then
    echo "Could not query Litestream containers; refusing to continue while a replica may run." >&2
    return 1
  fi
  if [ -z "${ids}" ]; then
    printf '0' >"${LITESTREAM_MARKER}"
    chmod 600 "${LITESTREAM_MARKER}"
    return 0
  fi
  printf '1' >"${LITESTREAM_MARKER}"
  chmod 600 "${LITESTREAM_MARKER}"
  while IFS= read -r id; do
    [ -n "${id}" ] || continue
    docker stop "${id}" >/dev/null
  done <<< "${ids}"
  if [ -n "$(litestream_container_ids)" ]; then
    echo "Litestream is still running; refusing to declare writers quiesced." >&2
    return 1
  fi
}

# Only restart Litestream on abort when this cutover actually stopped it.
maybe_restore_litestream() {
  [ -f "${LITESTREAM_MARKER}" ] || return 0
  [ "$(cat "${LITESTREAM_MARKER}")" = "1" ] || return 0
  docker compose --env-file .env --profile litestream up -d --no-deps litestream
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
  rclone check "${temp}" "${remote}:${UBYHOST_S3_BUCKET:?set UBYHOST_S3_BUCKET}/${prefix}/ubyhost-sqlite-cutover-${stamp}.sqlite.age" --download
  rm -f "${temp}"
}

# One transfer attempt, from the quiesced /data/ubyhost.db snapshot through the
# encrypted off-host artifact to the first pgBackRest base backup.
run_transfer_attempt() {
  local stamp="$1"
  printf '%s' "${stamp}" >"${LAST_STAMP_FILE}"
  chmod 600 "${LAST_STAMP_FILE}"
  # Set a durable ambiguity marker before any transfer write can begin.
  set_state transfer_in_progress
  if ! pg_compose run --rm --no-deps -T --entrypoint bash ubyhost \
    /app/scripts/postgres_cutover_transfer.sh "${stamp}"; then
    echo "Transfer failed or its outcome is ambiguous. Keep maintenance and do not restart SQLite." >&2
    return 1
  fi
  set_state transfer_pending_offsite
  if ! upload_cutover_snapshot "${stamp}"; then
    echo "Transfer completed locally but off-host artifact verification failed; remain in maintenance." >&2
    return 1
  fi
  pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost --type=full backup
  pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
  set_state transferred
  printf 'Transfer and encrypted off-host source snapshot verified: %s\n' "${stamp}"
}

case "${verb}" in
  prepare)
    require_postgres_backend

    require_state idle
    if [ -e "${WRITERS_MARKER}" ]; then
      echo "PostgreSQL authority marker exists; refusing a SQLite cutover workflow." >&2
      exit 1
    fi
    authority_status=0
    postgres_authority_present || authority_status=$?
    case "${authority_status}" in
      0) echo "PostgreSQL authority marker exists in /data; refusing a SQLite cutover workflow." >&2; exit 1 ;;
      1) ;;
      *) echo "Could not verify the PostgreSQL authority marker; refusing to guess." >&2; exit 1 ;;
    esac
    ./scripts/postgres-preflight.sh
    save_pre_cutover_settings
    maintenance_on
    set_state maintenance
    ;;
  stop-writers)
    require_postgres_backend
    require_state maintenance
    pg_compose stop worker ubyhost
    ensure_app_stopped
    stop_litestream
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
    # stanza-create is idempotent-safe here: skip it when the stanza already
    # exists so a rerun after a failed check can make progress.
    if pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner \
      --stanza=ubyhost info >/dev/null 2>&1; then
      echo "pgBackRest stanza already exists; not recreating it."
    else
      pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost stanza-create
    fi
    pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
    set_state postgres_ready
    ;;
  transfer)
    require_postgres_backend
    require_state postgres_ready
    ensure_app_stopped
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    run_transfer_attempt "${stamp}"
    ;;
  transfer-retry)
    require_postgres_backend
    require_state transfer_in_progress
    ensure_app_stopped
    previous_stamp="$(cat "${LAST_STAMP_FILE}" 2>/dev/null || true)"
    if [ -z "${previous_stamp}" ]; then
      echo "No recorded transfer stamp; this is not a retryable pre-commit failure." >&2
      exit 1
    fi
    empty_status=0
    postgres_target_empty || empty_status=$?
    case "${empty_status}" in
      0) ;;
      1) echo "PostgreSQL target is not empty: the earlier attempt may have committed. Run transfer-recovery-verify; never reset the target." >&2; exit 1 ;;
      *) exit 1 ;;
    esac
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    while [ "${stamp}" = "${previous_stamp}" ]; do
      sleep 1
      stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    done
    printf 'Pre-commit retry confirmed the target is still empty; new stamp %s.\n' "${stamp}"
    run_transfer_attempt "${stamp}"
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
    marker_state="$(container_path_state /data/database-authority.json)" || {
      echo "Could not verify the container-side PostgreSQL authority marker; refusing to start writers." >&2
      exit 1
    }
    if [ "${marker_state}" != "present" ]; then
      echo "Container-side PostgreSQL authority marker is absent; refusing to start writers." >&2
      exit 1
    fi
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
    pg_compose up -d --no-deps --force-recreate caddy
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
    if [ -e "${WRITERS_MARKER}" ]; then
      echo "PostgreSQL authority marker exists; stale SQLite rollback is unsafe." >&2
      exit 1
    fi
    authority_status=0
    postgres_authority_present || authority_status=$?
    case "${authority_status}" in
      0) echo "PostgreSQL authority marker exists in /data; stale SQLite rollback is unsafe." >&2; exit 1 ;;
      1) ;;
      *) echo "Could not verify the PostgreSQL authority marker; refusing to guess." >&2; exit 1 ;;
    esac
    pg_compose stop worker ubyhost postgres
    ensure_app_stopped
    # An empty UBYHOST_DATABASE_URL= is contradictory config (0455 rejects
    # "set but empty"), so remove the line instead of blanking it.
    remove_env_value UBYHOST_DATABASE_URL
    set_env_value COMPOSE_PROFILES "$(cat "${STATE_DIR}/previous-compose-profiles")"
    set_env_value UBYHOST_LITESTREAM_ENABLED "$(cat "${STATE_DIR}/previous-litestream-enabled")"
    unset COMPOSE_FILE
    docker compose --env-file .env up -d ubyhost worker
    ./scripts/postgres-schedule.sh sqlite
    maybe_restore_litestream
    set_env_value UBYHOST_MAINTENANCE 0
    docker compose --env-file .env up -d --no-deps --force-recreate caddy
    set_state aborted_to_sqlite
    ;;
  status)
    printf 'state_dir=%s\n' "${STATE_DIR}"
    printf 'phase=%s\n' "$(state)"
    [ ! -s "${LAST_STAMP_FILE}" ] || printf 'transfer_stamp=%s\n' "$(cat "${LAST_STAMP_FILE}")"
    [ ! -e "${WRITERS_MARKER}" ] || printf '%s\n' "postgres-writers-enabled=yes"
    [ ! -e "${LITESTREAM_MARKER}" ] || printf 'previous_litestream_running=%s\n' "$(cat "${LITESTREAM_MARKER}")"
    case "$(state)" in
      transfer_in_progress)
        printf '%s\n' "next: transfer-retry (target must still be empty) or transfer-recovery-verify (target populated)"
        ;;
    esac
    ;;
  *)
    echo "Usage: $0 {prepare|stop-writers|start-postgres|transfer|transfer-retry|transfer-recovery-verify|upload-final-snapshot|authorize-postgres-writers --owner-ack=POSTGRES_IS_AUTHORITATIVE|start-writers|finish-live --owner-ack=POST_CUTOVER_CHECKS_PASSED|abort-to-sqlite|status}" >&2
    exit 2
    ;;
esac
