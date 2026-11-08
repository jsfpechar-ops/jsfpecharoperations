#!/usr/bin/env bash
# 1010: monitor for WAL-G archiving. Exits 1 (and does NOT ping the dead-man URL)
# when the walg container is down, archiving is late or failing, a file is stuck
# in the spool, or pg_wal or the spool is large (the disk would fill up).
# Cron every 10 minutes: docs/LIGHTSAIL.md. Runbook: docs/OPERATIONS.md.
# Reads only pg_stat_archiver, file ages and directory sizes. It never calls S3.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

MAX_AGE_S="${WALG_MAX_ARCHIVE_AGE_S:-1800}"      # 30 minutes
MAX_SPOOL_AGE_S="${WALG_MAX_SPOOL_AGE_S:-1800}"  # 30 minutes
PGWAL_MAX_MB="${WALG_PGWAL_MAX_MB:-5120}"        # 5 GB
SPOOL_MAX_MB="${WALG_SPOOL_MAX_MB:-2048}"        # 2 GB
STATE="${WALG_CHECK_STATE:-/var/tmp/ubyhost-walg-check.state}"

problems=()

if [ -z "$(docker compose ps -q --status running walg 2>/dev/null)" ]; then
  problems+=("the walg container is not running (COMPOSE_PROFILES must contain walg): nothing is shipped to S3")
fi

row="$(docker compose exec -T postgres psql -U ubyhost -d ubyhost -Atc \
  "SELECT COALESCE(EXTRACT(EPOCH FROM now() - last_archived_time)::bigint, -1), failed_count FROM pg_stat_archiver" 2>/dev/null | tr -d '\r')"
if [ -z "${row}" ]; then
  problems+=("cannot read pg_stat_archiver (is the postgres container running?)")
else
  age="${row%%|*}"
  failed="${row##*|}"
  if [ "${age}" -lt 0 ] 2>/dev/null; then
    problems+=("pg_stat_archiver has never archived a WAL file (is UBYHOST_PG_ARCHIVE=on in .env?)")
  elif [ "${age}" -gt "${MAX_AGE_S}" ] 2>/dev/null; then
    problems+=("last WAL archived ${age}s ago (limit ${MAX_AGE_S}s)")
  fi
  prev=0
  [ -f "${STATE}" ] && prev="$(cat "${STATE}" 2>/dev/null || echo 0)"
  if [ "${failed}" -gt "${prev}" ] 2>/dev/null; then
    problems+=("failed_count rose from ${prev} to ${failed}: archive_command fails (docker compose logs --tail 50 postgres)")
  fi
  printf '%s' "${failed}" > "${STATE}" 2>/dev/null || true
fi

oldest="$(docker compose exec -T postgres sh -c \
  'find /walspool -maxdepth 1 -type f ! -name "*.tmp" -exec stat -c %Y {} \; | sort -n | head -1' 2>/dev/null | tr -d '\r')"
if [ -n "${oldest}" ]; then
  spool_age=$(( $(date +%s) - oldest ))
  if [ "${spool_age}" -gt "${MAX_SPOOL_AGE_S}" ]; then
    problems+=("oldest WAL file in the spool is ${spool_age}s old: the upload to S3 is stuck (docker compose logs --tail 50 walg)")
  fi
fi

spool_mb="$(docker compose exec -T postgres sh -c 'du -sm /walspool | cut -f1' 2>/dev/null | tr -d '\r')"
if [ -n "${spool_mb}" ] && [ "${spool_mb}" -gt "${SPOOL_MAX_MB}" ] 2>/dev/null; then
  problems+=("the spool holds ${spool_mb} MB (limit ${SPOOL_MAX_MB} MB): uploads are failing and the disk is filling")
fi

pgwal_mb="$(docker compose exec -T postgres sh -c 'du -sm /var/lib/postgresql/data/pg_wal | cut -f1' 2>/dev/null | tr -d '\r')"
if [ -n "${pgwal_mb}" ] && [ "${pgwal_mb}" -gt "${PGWAL_MAX_MB}" ] 2>/dev/null; then
  problems+=("pg_wal is ${pgwal_mb} MB (limit ${PGWAL_MAX_MB} MB): archiving is failing and WAL is piling up on disk")
fi

if [ "${#problems[@]}" -gt 0 ]; then
  for p in "${problems[@]}"; do echo "WALG-CHECK FAIL: ${p}" >&2; done
  exit 1
fi

echo "walg-check ok"
if [ -n "${UBYHOST_WALG_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_WALG_PING_URL}" >/dev/null || \
    echo "WARNING: walg-check ok but the ping to UBYHOST_WALG_PING_URL failed" >&2
fi
