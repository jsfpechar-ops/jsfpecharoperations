#!/usr/bin/env bash
# PostgreSQL cutover for the Lightsail stack (brief 0463; plan migration-plan-v4 step 8).
#
# Usage (from deploy/lightsail, on the server):
#   ./scripts/pg-cutover.sh rehearse   # copy production data into a throwaway database and verify it
#   ./scripts/pg-cutover.sh cutover    # stop the app, copy, verify, switch .env to PostgreSQL, start
#   ./scripts/pg-cutover.sh rollback   # switch .env back to SQLite (rows written to PostgreSQL stay there)
#
# The SQLite file is only read: a .backup copy is what gets transferred.
# A failure in cutover ends with the app up on SQLite and a non-zero exit.
# Needs UBYHOST_PG_PASSWORD in .env (preflight.sh checks it).
# Set PG_CUTOVER_LIB=1 to source the functions without running a command.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

PG_URL='postgresql://ubyhost@/ubyhost?host=/var/run/postgresql'
REHEARSAL_URL='postgresql://ubyhost@/ubyhost_rehearsal?host=/var/run/postgresql'
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PG_TOUCHED=0
ENV_SWITCHED=0
ENV_COPY=""

die() { echo "ERROR: $*" >&2; exit 1; }

# wait_until <tries> <command...>: retries every 2 s
wait_until() {
  local tries="$1"; shift
  for _ in $(seq 1 "${tries}"); do
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

healthz_ok() {
  docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
}

login_ok() {
  docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=3)"
}

# pg_sql <database> <sql>: one statement in the postgres container
pg_sql() {
  docker compose exec -T postgres psql -U ubyhost -d "$1" -v ON_ERROR_STOP=1 -Atc "$2"
}

count_tables() {  # <database>: public tables in it
  pg_sql "$1" "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
}

env-switch() {  # <env-file> <url>: drop the SQLite setting and point the app at PostgreSQL
  local file="$1" url="$2" tmp
  tmp="$(mktemp "${file}.XXXXXX")"
  grep -Ev '^(UBYHOST_DB|UBYHOST_DATABASE_URL)=' "${file}" > "${tmp}" || true
  printf 'UBYHOST_DATABASE_URL=%s\n' "${url}" >> "${tmp}"
  chmod --reference="${file}" "${tmp}"
  mv "${tmp}" "${file}"
}

env-restore() {  # <env-file> <copy>: put the saved .env back, byte for byte
  cp -p "$2" "$1"
}

preflight() {  # postgres is up and is version 16 or newer; host memory is printed for information
  docker compose up -d postgres >/dev/null
  wait_until 30 docker compose exec -T postgres pg_isready -U ubyhost -d ubyhost \
    || die "postgres container is not ready"
  local facts version max_conn shared
  facts="$(pg_sql postgres "SELECT current_setting('server_version_num') || ' ' || current_setting('max_connections') || ' ' || current_setting('shared_buffers')")"
  read -r version max_conn shared <<<"${facts}"
  echo "postgres: server_version_num=${version} max_connections=${max_conn} shared_buffers=${shared}"
  [ "${version}" -ge 160000 ] || die "PostgreSQL 16 or newer is required"
  free -m | head -2
}

copy_source() {  # hot SQLite copy into the data volume, checked with integrity_check
  docker compose run --rm --no-deps -T --entrypoint bash ubyhost -c '
    set -euo pipefail
    mkdir -p /data/pg-cutover
    rm -f /data/pg-cutover/source.db
    sqlite3 /data/ubyhost.db ".backup /data/pg-cutover/source.db"
    test "$(sqlite3 /data/pg-cutover/source.db "PRAGMA integrity_check;")" = ok
  ' >/dev/null
}

remove_source_copy() {
  docker compose run --rm --no-deps -T --entrypoint rm ubyhost -f /data/pg-cutover/source.db >/dev/null 2>&1 || true
}

# pg_transfer <url> <database> <report> [--verify-only]: sqlite_to_postgres.py in a one-off container
pg_transfer() {
  local url="$1" db="$2" report="$3"; shift 3
  docker compose run --rm --no-deps -T -e "UBYHOST_DATABASE_URL=${url}" --entrypoint sh ubyhost \
    -c 'unset UBYHOST_DB; exec python /app/scripts/sqlite_to_postgres.py "$@"' sh \
    --source /data/pg-cutover/source.db --report "${report}" --expect-database "${db}" "$@" 2>&1 | tail -30
}

fresh_rehearsal() {  # exit 0 when the newest rehearsal verify report is under 24 h old, verify-only, all tables match
  local py
  py="$(cat <<'PY'
import glob, json, os, sys, time
reports = sorted(glob.glob("/data/pg-cutover/rehearsal-*.verify.json"), key=os.path.getmtime)
if not reports:
    sys.exit(1)
newest = reports[-1]
r = json.load(open(newest))
fresh = time.time() - os.path.getmtime(newest) < 86400
tables = r.get("tables") or {}
ok = (fresh and r.get("mode") == "verify-only" and r.get("target_database") == "ubyhost_rehearsal"
      and bool(tables) and all(t.get("match") is True for t in tables.values()))
sys.exit(0 if ok else 1)
PY
)"
  docker compose run --rm --no-deps -T --entrypoint python ubyhost -c "${py}" >/dev/null 2>&1
}

print_report_tables() {  # <report>: per-table row counts and hashes as stored in the report
  local py
  py="$(cat <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
print(json.dumps(report.get("tables", report), indent=1, sort_keys=True))
PY
)"
  docker compose run --rm --no-deps -T --entrypoint python ubyhost -c "${py}" "$1" 2>&1 | tail -60
}

rehearsal_cleanup() {  # on exit: drop the rehearsal database and the SQLite copy
  pg_sql postgres "DROP DATABASE IF EXISTS ubyhost_rehearsal" >/dev/null 2>&1 || true
  remove_source_copy
}

fail_cutover() {  # <reason>: undo what was done, start the app on SQLite, exit 1
  trap - ERR
  echo "CUTOVER FAILED: $1. SQLite was not written; the app goes back to SQLite." >&2
  if [ "${PG_TOUCHED}" = 1 ]; then
    pg_sql ubyhost "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null \
      || echo "WARNING: could not clear the ubyhost schema" >&2
  fi
  remove_source_copy
  if [ "${ENV_SWITCHED}" = 1 ]; then env-restore .env "${ENV_COPY}"; fi
  docker compose up -d ubyhost worker
  wait_until 30 healthz_ok || echo "ubyhost is not healthy: run ./scripts/logs.sh ubyhost" >&2
  exit 1
}

rehearse() {
  preflight
  ./scripts/backup.sh
  local report="/data/pg-cutover/rehearsal-${STAMP}.json"
  trap rehearsal_cleanup EXIT
  copy_source
  pg_sql postgres "DROP DATABASE IF EXISTS ubyhost_rehearsal" >/dev/null
  pg_sql postgres "CREATE DATABASE ubyhost_rehearsal" >/dev/null
  pg_transfer "${REHEARSAL_URL}" ubyhost_rehearsal "${report}" || die "rehearsal transfer failed"
  pg_transfer "${REHEARSAL_URL}" ubyhost_rehearsal "${report%.json}.verify.json" --verify-only \
    || die "rehearsal verify failed"
  print_report_tables "${report}"
  echo "REHEARSAL OK"
}

cutover() {
  preflight
  [ "$(count_tables ubyhost)" = 0 ] || die "the ubyhost database already has tables; refusing to cut over"
  fresh_rehearsal || die "no ok rehearsal report younger than 24 h; run ./scripts/pg-cutover.sh rehearse first"
  ./scripts/backup.sh
  local report="/data/pg-cutover/cutover-${STAMP}.json" down_from
  ENV_COPY=".env.sqlite-${STAMP}"
  cp -p .env "${ENV_COPY}"
  down_from="${SECONDS}"
  docker compose stop worker ubyhost
  trap 'fail_cutover "unexpected error at line ${LINENO}"' ERR
  copy_source || fail_cutover "SQLite copy failed its integrity check"
  PG_TOUCHED=1
  pg_transfer "${PG_URL}" ubyhost "${report}" || fail_cutover "transfer into PostgreSQL failed"
  pg_transfer "${PG_URL}" ubyhost "${report%.json}.verify.json" --verify-only \
    || fail_cutover "verification in PostgreSQL failed"
  remove_source_copy
  env-switch .env "${PG_URL}"
  ENV_SWITCHED=1
  docker compose up -d ubyhost worker
  wait_until 30 healthz_ok || fail_cutover "ubyhost did not become healthy on PostgreSQL"
  wait_until 30 login_ok || fail_cutover "/login did not return 200 on PostgreSQL"
  trap - ERR
  echo "Downtime: $((SECONDS - down_from)) s"
  echo "SQLite file kept on the volume: /data/ubyhost.db; .env copy: ${ENV_COPY}"
  echo "CUTOVER OK"
}

rollback() {
  local copy answer
  copy="$(ls -1 .env.sqlite-* 2>/dev/null | sort | tail -1 || true)"
  [ -n "${copy}" ] || die "no .env.sqlite-<stamp> copy found; nothing to roll back to"
  echo "Restoring .env from ${copy}."
  echo "Rows written to PostgreSQL since the cutover are NOT carried back to SQLite."
  read -r -p "Type ROLLBACK to continue: " answer
  [ "${answer}" = "ROLLBACK" ] || die "not confirmed; nothing changed"
  env-restore .env "${copy}"
  docker compose up -d ubyhost worker
  wait_until 30 healthz_ok || die "ubyhost is not healthy: run ./scripts/logs.sh ubyhost"
  echo "ROLLBACK OK: the app runs on SQLite again"
}

main() {
  [ -f .env ] || die "missing .env in ${ROOT}"
  case "${1:-}" in
    rehearse) rehearse ;;
    cutover) cutover ;;
    rollback) rollback ;;
    *) die "usage: $0 rehearse|cutover|rollback" ;;
  esac
}

if [ -z "${PG_CUTOVER_LIB:-}" ]; then
  main "$@"
fi
