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
  printf '%s' "${STAMP}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$' || die "stamp '${STAMP}' is not a backup name like 20260915T030000Z"
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
  docker compose run --rm --no-deps -T --entrypoint sh ubyhost \
    -c "test -f /data/backups/${STAMP}/ubyhost-pg.dump.age" >/dev/null 2>&1 \
    || die "no ubyhost-pg.dump.age in snapshot ${STAMP}"
fi

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "This replaces every table in the ubyhost PostgreSQL database with ${WHAT}."
  read -r -p "Type yes to continue: " CONFIRM
  [ "${CONFIRM}" = "yes" ] || die "aborted"
fi

CONTAINER="$(docker compose ps -aq ubyhost)"
[ -n "${CONTAINER}" ] || die "could not find the ubyhost container; run ./scripts/deploy.sh first"

STOP_SERVICES="worker ubyhost"
UP_SERVICES="ubyhost worker"
if [ "${MODE}" = "file" ]; then
  printf 'restored %s from %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "${DUMP_FILE}")" > .restored-box
  # Brief 1169-cont-1: the Go service could claim a submit job from the restored
  # database with its old env. Stop it too (only when the go profile defines or
  # runs it), and start every service again so each one reads the current .env.
  KNOWN_SERVICES="$( { docker compose config --services; docker compose ps --services; } 2>/dev/null || true)"
  if printf '%s\n' "${KNOWN_SERVICES}" | grep -qx 'ubyhost-go'; then
    STOP_SERVICES="worker ubyhost-go ubyhost"
  fi
  UP_SERVICES=""
fi

TMP="$(mktemp -d)"
chmod 700 "${TMP}"
# From here on, any failure brings the app back up, a partly failed stop included
# (brief 1169-cont-2; a no-op after the explicit start below).
# shellcheck disable=SC2086
trap 'rm -rf "${TMP}"; docker compose up -d ${UP_SERVICES} >/dev/null 2>&1 || true' EXIT

echo "==> Stopping ${STOP_SERVICES}"
# shellcheck disable=SC2086
docker compose stop ${STOP_SERVICES}

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

echo "==> Starting ${UP_SERVICES:-every service}"
# shellcheck disable=SC2086
docker compose up -d ${UP_SERVICES}

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    echo "PostgreSQL restore complete from ${SOURCE}. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "ubyhost did not become healthy: run ./scripts/logs.sh ubyhost" >&2
exit 1
