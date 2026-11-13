#!/usr/bin/env bash
# 1473 (plan sqlite-retirement S4, S10): read-only looks at the production PostgreSQL.
#   ./scripts/pg-schema-dump.sh /home/ubuntu/ubyhost-schema.sql
#       Writes a schema-only dump (pg_dump --schema-only --no-owner --no-privileges)
#       to a NEW file: tables, columns, defaults, constraints, indexes, triggers and
#       functions. No rows, no sequence values, no owners, no grants. Refuses a path
#       that exists. The file is safe to hand over (docs/OPERATIONS.md, "Proofs").
#   ./scripts/pg-schema-dump.sh --counts [ubyhost|ubyhost_restoretest]
#       Prints "table rows" for every table (numbers only, never row content).
# Both modes are read-only: the session starts with default_transaction_read_only=on
# and runs pg_dump or one SELECT. Nothing is written to the database.
set -euo pipefail

START_DIR="$PWD"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
READ_ONLY="-c default_transaction_read_only=on"
USAGE="usage: $0 /path/to/new-file.sql | $0 --counts [ubyhost|ubyhost_restoretest]"

die() { echo "ERROR: $1" >&2; exit "${2:-1}"; }

COUNT_SQL="$(cat <<'SQL'
SELECT table_name || ' ' || (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name
SQL
)"

need_postgres() {
  cd "${ROOT}"
  if [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
    die "the postgres container is not running; nothing was read"
  fi
}

if [ "$#" -ge 1 ] && [ "$1" = "--counts" ]; then
  [ "$#" -le 2 ] || die "${USAGE}" 2
  DB="${2:-ubyhost}"
  case "${DB}" in
    ubyhost|ubyhost_restoretest) ;;
    *) die "database must be ubyhost or ubyhost_restoretest, not '${DB}'" 2 ;;
  esac
  need_postgres
  docker compose exec -T -e PGOPTIONS="${READ_ONLY}" postgres \
    psql -U ubyhost -d "${DB}" -X -v ON_ERROR_STOP=1 -At -c "${COUNT_SQL}"
  exit 0
fi

[ "$#" -eq 1 ] && [ -n "$1" ] && [ "${1#-}" = "$1" ] || die "${USAGE}" 2
OUT="$1"
case "${OUT}" in
  /*) ;;
  *) OUT="${START_DIR}/${OUT}" ;;
esac
TMP="${OUT}.partial"
if [ -e "${OUT}" ] || [ -L "${OUT}" ]; then
  die "${OUT} already exists; give a new file name (nothing was written)" 2
fi
if [ -e "${TMP}" ] || [ -L "${TMP}" ]; then
  die "${TMP} is left from an earlier run; delete it, then run again" 2
fi
[ -d "$(dirname "${OUT}")" ] || die "the folder $(dirname "${OUT}") does not exist" 2

need_postgres
umask 077
set -o noclobber
trap 'rm -f -- "${TMP}"' EXIT
docker compose exec -T -e PGOPTIONS="${READ_ONLY}" postgres \
  pg_dump -U ubyhost -d ubyhost --schema-only --no-owner --no-privileges --lock-wait-timeout=10s \
  > "${TMP}"

# A schema-only dump has no data: refuse to keep a file that has any.
if grep -Eq '^(COPY|INSERT INTO) |pg_catalog\.setval\(' "${TMP}"; then
  die "the dump contains data lines; it was deleted, do not hand anything over"
fi
grep -q '^CREATE TABLE public\.' "${TMP}" || die "the dump has no tables; it was deleted"

mv -n -- "${TMP}" "${OUT}"
[ ! -e "${TMP}" ] || die "${OUT} appeared while the dump ran; the dump was deleted" 2
trap - EXIT
echo "Wrote ${OUT}: $(grep -c '^CREATE TABLE ' "${OUT}") tables, $(wc -l < "${OUT}") lines"
echo "sha256 $(sha256sum "${OUT}" | cut -d' ' -f1)"
echo "COMMENT ON lines: $(grep -c '^COMMENT ON ' "${OUT}" || true) (0 expected)"
