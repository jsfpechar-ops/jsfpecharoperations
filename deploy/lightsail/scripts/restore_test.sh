#!/usr/bin/env bash
# Restore drill for the Litestream replica (WP05). Run once after the first
# deploy with Litestream and then once per quarter.
#
# It restores the newest replica from S3 into a temporary file inside a
# throwaway litestream container, runs PRAGMA integrity_check on it, prints the
# row counts of the main tables next to the live database's counts and deletes
# the temporary file. Nothing is written to the data volume or to the host, and
# only counts are printed, never row contents.
#
# Usage (from deploy/lightsail):
#   ./scripts/restore_test.sh
#   RESTORE_TEST_SETTLE_SECONDS=30 ./scripts/restore_test.sh
#
# Exit code: 0 when the restore is intact and every count matches, 1 otherwise.
#
# A count "matches" when the restored value lies between the live counts read
# just before and just after the restore. The app keeps writing during the
# drill, and the replica trails the live file by up to one sync-interval
# (10 s), so the script waits RESTORE_TEST_SETTLE_SECONDS (default 15) after the
# first live reading before it restores.
#
# RESTORE_TEST_LOCAL=1 runs the same steps with the litestream and sqlite3
# binaries on PATH instead of through docker compose (used to test the script
# against a local S3 emulator). It then needs LITESTREAM_CONFIG and the
# variables litestream.yml expands.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

TABLES="user_account legal_entity apartment reservation guest submission"
SETTLE="${RESTORE_TEST_SETTLE_SECONDS:-15}"
case "${SETTLE}" in
  ''|*[!0-9]*) echo "RESTORE_TEST_SETTLE_SECONDS must be a whole number of seconds." >&2; exit 1 ;;
esac

# The drill itself, as a POSIX sh script fed on stdin, so that it runs
# unchanged inside the litestream image (Debian, has sh and sqlite3).
drill() {
  cat <<'DRILL'
set -eu
tables="$1"
settle="$2"
db="${LITESTREAM_DB_PATH:?LITESTREAM_DB_PATH is not set}"
cfg="${LITESTREAM_CONFIG:-/etc/litestream.yml}"

if [ ! -f "${db}" ]; then
  echo "No live database at ${db}." >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT INT TERM
restored="${work}/restore-test.db"

count() {
  sqlite3 -readonly "$1" "SELECT COUNT(*) FROM $2;"
}

for t in ${tables}; do
  echo "${t} $(count "${db}" "${t}")"
done > "${work}/before"

echo "==> Waiting ${settle}s so the replica catches up with the live database"
sleep "${settle}"

echo "==> Restoring the newest replica into a temporary file"
started="$(date +%s)"
litestream restore -config "${cfg}" -o "${restored}" "${db}"
echo "Restore took $(( $(date +%s) - started ))s"

integrity="$(sqlite3 -readonly "${restored}" 'PRAGMA integrity_check;')"
echo "integrity_check: ${integrity}"

for t in ${tables}; do
  echo "${t} $(count "${db}" "${t}")"
done > "${work}/after"

status=0
[ "${integrity}" = "ok" ] || status=1

printf '%-16s %10s %10s %10s  %s\n' table live_before restored live_after result
paste -d ' ' "${work}/before" "${work}/after" > "${work}/counts"
while read -r t b _t a; do
  r="$(count "${restored}" "${t}" 2>/dev/null || echo missing)"
  lo="${b}"; hi="${a}"
  if [ "${a}" -lt "${b}" ]; then lo="${a}"; hi="${b}"; fi
  if [ "${r}" != "missing" ] && [ "${r}" -ge "${lo}" ] && [ "${r}" -le "${hi}" ]; then
    result=ok
  else
    result=MISMATCH
    status=1
  fi
  printf '%-16s %10s %10s %10s  %s\n' "${t}" "${b}" "${r}" "${a}" "${result}"
done < "${work}/counts"

rm -f "${restored}" "${restored}-wal" "${restored}-shm"
if [ "${status}" -eq 0 ]; then
  echo "Restore drill passed. The temporary copy was deleted."
else
  echo "Restore drill FAILED. The temporary copy was deleted." >&2
fi
exit "${status}"
DRILL
}

if [ "${RESTORE_TEST_LOCAL:-0}" = "1" ]; then
  drill | sh -s -- "${TABLES}" "${SETTLE}"
  exit $?
fi

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx litestream; then
  echo "WARNING: the litestream service is not running; the replica may be stale." >&2
fi

# A one-off container of the litestream service: same image, user, volume,
# config and S3 credentials, removed when the drill ends (--rm). The temporary
# restore lives in that container's /tmp only.
drill | docker compose run --rm --no-deps -T --entrypoint sh litestream \
  -s -- "${TABLES}" "${SETTLE}"
