#!/usr/bin/env bash
# Restore the PostgreSQL dump that backup.sh wrote into a snapshot folder (brief 0464).
#
# Usage (from deploy/lightsail):
#   AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh 20260915T030000Z
#   RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh <stamp>
#
# Refuses while .env still points the app at SQLite. The dump is decrypted
# on the host and streamed straight into pg_restore: no plaintext file is written.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

die() { echo "ERROR: $*" >&2; exit "${2:-1}"; }

[ -f .env ] || die "missing .env in ${ROOT}"
if grep -Eq '^UBYHOST_DB=' .env; then
  die "the app still runs on SQLite (UBYHOST_DB is set in .env); restore only after cutover" 2
fi
grep -Eq '^UBYHOST_DATABASE_URL=' .env || die "UBYHOST_DATABASE_URL is not set in .env; the app is not on PostgreSQL" 2

STAMP="${1:-}"
IDENTITY="${AGE_IDENTITY_FILE:-}"
[ -n "${STAMP}" ] || die "usage: $0 <stamp>"
printf '%s' "${STAMP}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$' || die "stamp '${STAMP}' is not a backup name like 20260915T030000Z"
[ -n "${IDENTITY}" ] || die "set AGE_IDENTITY_FILE to the age identity on the host (never inside the volume)"
[ -f "${IDENTITY}" ] || die "AGE_IDENTITY_FILE=${IDENTITY} does not exist on the host"
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"

docker compose run --rm --no-deps -T --entrypoint sh ubyhost \
  -c "test -f /data/backups/${STAMP}/ubyhost-pg.dump.age" >/dev/null 2>&1 \
  || die "no ubyhost-pg.dump.age in snapshot ${STAMP}"

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "This replaces every table in the ubyhost PostgreSQL database with snapshot ${STAMP}."
  read -r -p "Type yes to continue: " CONFIRM
  [ "${CONFIRM}" = "yes" ] || die "aborted"
fi

CONTAINER="$(docker compose ps -aq ubyhost)"
[ -n "${CONTAINER}" ] || die "could not find the ubyhost container; run ./scripts/deploy.sh first"

TMP="$(mktemp -d)"
chmod 700 "${TMP}"
trap 'rm -rf "${TMP}"' EXIT

echo "==> Stopping worker and ubyhost"
docker compose stop worker ubyhost
# From here on, any failure brings the app back up (a no-op after the explicit start below).
trap 'rm -rf "${TMP}"; docker compose up -d ubyhost worker >/dev/null 2>&1 || true' EXIT

echo "==> Pulling ${STAMP} and restoring it into PostgreSQL"
docker cp "${CONTAINER}:/data/backups/${STAMP}/ubyhost-pg.dump.age" "${TMP}/ubyhost-pg.dump.age"
age -d -i "${IDENTITY}" "${TMP}/ubyhost-pg.dump.age" \
  | docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction
rm -f "${TMP}/ubyhost-pg.dump.age"

echo "==> Starting ubyhost and the worker"
docker compose up -d ubyhost worker

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    echo "PostgreSQL restore complete from ${STAMP}. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "ubyhost did not become healthy: run ./scripts/logs.sh ubyhost" >&2
exit 1
