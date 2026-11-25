#!/usr/bin/env bash
# Restore the PostgreSQL dump that backup.sh wrote into a snapshot folder (brief 0464).
#
# Usage (from deploy/lightsail):
#   AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh 20260915T030000Z
#   RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh <stamp>
#   AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh --file /path/to/ubyhost-pg.dump.age
#
# Give exactly one source: a <stamp> (dump read from the app volume) or --file
# (a local .age file on the host, e.g. downloaded from Google Drive; no volume, no AWS).
# Refuses while .env still points the app at SQLite. The dump is decrypted
# on the host and streamed straight into pg_restore: no plaintext file is written.
set -euo pipefail

START_DIR="$PWD"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib-docker.sh"

die() { echo "ERROR: $*" >&2; exit "${2:-1}"; }

[ -f .env ] || die "missing .env in ${ROOT}"
if grep -Eq '^UBYHOST_DB=' .env; then
  die "the app still runs on SQLite (UBYHOST_DB is set in .env); restore only after cutover" 2
fi
grep -Eq '^UBYHOST_DATABASE_URL=' .env || die "UBYHOST_DATABASE_URL is not set in .env; the app is not on PostgreSQL" 2

IDENTITY="${AGE_IDENTITY_FILE:-}"
USAGE="usage: $0 <stamp> | $0 --file /path/to/ubyhost-pg.dump.age"
MODE=""
STAMP=""
DUMP_FILE=""
if [ "$#" -eq 2 ] && [ "$1" = "--file" ]; then
  MODE="file"
  DUMP_FILE="$2"
elif [ "$#" -eq 1 ] && [ "$1" != "--file" ]; then
  MODE="stamp"
  STAMP="$1"
else
  die "${USAGE}"
fi

if [ "${MODE}" = "stamp" ]; then
  [ -n "${STAMP}" ] || die "${USAGE}"
  printf '%s' "${STAMP}" | grep -E '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$' >/dev/null || die "stamp '${STAMP}' is not a backup name like 20260915T030000Z"
  SOURCE="${STAMP}"
  WHAT="snapshot ${STAMP}"
else
  [ -n "${DUMP_FILE}" ] || die "${USAGE}"
  case "${DUMP_FILE}" in /*) ;; *) DUMP_FILE="${START_DIR}/${DUMP_FILE}" ;; esac
  case "${DUMP_FILE}" in *.age) ;; *) die "${DUMP_FILE} is not an .age file" ;; esac
  [ -f "${DUMP_FILE}" ] || die "${DUMP_FILE} does not exist on the host"
  [ -r "${DUMP_FILE}" ] || die "${DUMP_FILE} is not readable"
  [ -s "${DUMP_FILE}" ] || die "${DUMP_FILE} is empty"
  SOURCE="${DUMP_FILE}"
  WHAT="file ${DUMP_FILE}"
fi

[ -n "${IDENTITY}" ] || die "set AGE_IDENTITY_FILE to the age identity on the host (never inside the volume)"
[ -f "${IDENTITY}" ] || die "AGE_IDENTITY_FILE=${IDENTITY} does not exist on the host"
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"

if [ "${MODE}" = "file" ]; then
  # Brief 1169: a restore from a file means a rebuilt box, and the old server may
  # still be filing. Check as if restored; the marker is written only after the
  # confirm, just before any container stops (docs/DISASTER_RECOVERY.md,
  # "Two servers never file at once").
  bash "${ROOT}/scripts/filing-guard.sh" --assume-restored \
    || die "turn automatic filing off in .env first (UBYHOST_ENABLE_SCHEDULER=0, submit in neither job list), run ./scripts/deploy.sh, then run this again" 3
fi

if [ "${MODE}" = "stamp" ]; then
  ubyhost_app_run_sh "test -f /data/backups/${STAMP}/ubyhost-pg.dump.age" >/dev/null 2>&1 \
    || die "no ubyhost-pg.dump.age in snapshot ${STAMP}"
fi

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "This replaces every table in the ubyhost PostgreSQL database with ${WHAT}."
  read -r -p "Type yes to continue: " CONFIRM
  [ "${CONFIRM}" = "yes" ] || die "aborted"
fi

CONTAINER="$(ubyhost_container_ref "${ROOT}" || true)"
[ -n "${CONTAINER}" ] || die "could not find a running app container (ubyhost-go or ubyhost); start the stack first"

STACK_GO_ONLY=0
if compose_has_go_app && ! compose_has_python_app; then
  STACK_GO_ONLY=1
fi

STOP_SERVICES="$(ubyhost_restore_stop_services)"

if [ "${MODE}" = "file" ]; then
  printf 'restored %s from %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "${DUMP_FILE}")" > .restored-box
fi

restore_apps_up() {
  if [ "${MODE}" = "file" ] || [ "${STACK_GO_ONLY}" != "1" ]; then
    docker compose up -d >/dev/null 2>&1 || true
  else
    docker compose --profile go up -d >/dev/null 2>&1 || true
  fi
}

TMP="$(mktemp -d)"
chmod 700 "${TMP}"
# From here on, any failure brings the app back up, a partly failed stop included
# (brief 1169-cont-2; a no-op after the explicit start below).
trap 'rm -rf "${TMP}"; restore_apps_up' EXIT

echo "==> Stopping ${STOP_SERVICES}"
# shellcheck disable=SC2086
if [ -n "${STOP_SERVICES}" ]; then
  if [ "${STACK_GO_ONLY}" = "1" ]; then
    docker compose --profile go stop ${STOP_SERVICES}
  else
    docker compose stop ${STOP_SERVICES}
  fi
fi

if [ "${MODE}" = "stamp" ]; then
  echo "==> Pulling ${STAMP} and restoring it into PostgreSQL"
  docker cp "${CONTAINER}:/data/backups/${STAMP}/ubyhost-pg.dump.age" "${TMP}/ubyhost-pg.dump.age"
  age -d -i "${IDENTITY}" "${TMP}/ubyhost-pg.dump.age" \
    | docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction
  rm -f "${TMP}/ubyhost-pg.dump.age"
else
  echo "==> Restoring ${DUMP_FILE} into PostgreSQL"
  age -d -i "${IDENTITY}" "${DUMP_FILE}" \
    | docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction
fi

echo "==> Starting every service"
if [ "${MODE}" = "file" ] || [ "${STACK_GO_ONLY}" != "1" ]; then
  docker compose up -d
else
  docker compose --profile go up -d
fi

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if ubyhost_app_healthz_ok; then
    echo "PostgreSQL restore complete from ${SOURCE}. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "The app did not become healthy: run ./scripts/logs.sh" >&2
exit 1