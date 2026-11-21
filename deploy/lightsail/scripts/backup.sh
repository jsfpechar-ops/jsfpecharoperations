#!/usr/bin/env bash
# Snapshot SQLite + secrets inside the running container (age-encrypted, time-based retention; see App/scripts/backup_data.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

# 1999: lib-docker.sh tells these scripts whether the checkout still has the
# Python app (before 1782) or only the Go service. Sourced when present; without
# it (a trimmed fixture tree) the old Python layout is assumed, exactly as
# before, so nothing here is a new hard dependency.
if [ -f ./scripts/lib-docker.sh ]; then
  # shellcheck disable=SC1091
  source ./scripts/lib-docker.sh
else
  app_is_python() { return 0; }
  app_service() { printf 'ubyhost\n'; }
  app_running_service() { printf 'ubyhost\n'; }
  app_run() { docker compose run --rm --no-deps -T ubyhost "$@"; }
fi

# 1999: a Go-only stack (1782 removed the Python services) has no Python image,
# so App/scripts/backup_data.sh is not available. There the snapshot is a
# directory this script creates itself, holding the age-encrypted PostgreSQL
# dump and the age-encrypted secret key; the SQLite copy does not exist because
# the Go stack is PostgreSQL-only. A checkout that still has `ubyhost` keeps the
# old path unchanged.
GO_ONLY=0
if ! app_is_python; then GO_ONLY=1; fi

# Brief 1020: in production on PostgreSQL, never take or prune a snapshot while postgres is down.
# A run without the dump would age out the last good dumps. Exits before backup_data.sh and before the ping.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -n "${UBYHOST_DATABASE_URL:-}" ] \
  && [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
  echo "Refusing to finish: the postgres container is not running in production, so no PostgreSQL dump can be taken." >&2
  exit 1
fi

SNAPSHOT_STAMP=""
if [ "${GO_ONLY}" = "1" ]; then
  APP_SVC="$(app_running_service)"
  if [ -z "${APP_SVC}" ]; then
    echo "No running app container (ubyhost-go). Start it with ./scripts/deploy.sh" >&2
    exit 1
  fi
  SNAPSHOT_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  suffix=0
  while [ -n "$(docker compose exec -T "${APP_SVC}" sh -c "[ -e /data/backups/${SNAPSHOT_STAMP} ] && echo x" 2>/dev/null)" ]; do
    suffix=$((suffix + 1))
    SNAPSHOT_STAMP="$(date -u +%Y%m%dT%H%M%SZ)-${suffix}"
  done
  if ! docker compose exec -T "${APP_SVC}" sh -c \
    "mkdir -p /data/backups/${SNAPSHOT_STAMP} && chmod 700 /data/backups /data/backups/${SNAPSHOT_STAMP}"; then
    echo "Could not create /data/backups/${SNAPSHOT_STAMP}." >&2
    exit 1
  fi
else
  docker compose exec -T ubyhost bash /app/scripts/backup_data.sh
fi

# Whichever container owns /data gets every read below (Python app, or the live
# Go slot). Empty only if the stack is down, which the checks above rejected.
APP_SVC="${APP_SVC:-$(app_running_service)}"

# PostgreSQL dump (brief 0464): into the newest snapshot folder, age-encrypted, never plaintext.
# Runs only once the app runs on PostgreSQL (UBYHOST_DATABASE_URL set), not before the cutover.
# Brief 1020: production must never finish without a PostgreSQL dump. The snapshot above is kept; no ping is sent.
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "Refusing to finish: UBYHOST_DATABASE_URL is unset in production, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
  if [ -z "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
    echo "Refusing to finish: the postgres container stopped during the backup, so no PostgreSQL dump was taken." >&2
    exit 1
  fi
fi

if [ -n "${UBYHOST_DATABASE_URL:-}" ] && [ -n "$(docker compose ps -q --status running postgres 2>/dev/null)" ]; then
  RECIPIENT="${UBYHOST_BACKUP_AGE_RECIPIENT:-}"
  if [ -z "${RECIPIENT}" ]; then
    if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
      echo "Refusing to write an unencrypted PostgreSQL dump in production." >&2
      echo "Set UBYHOST_BACKUP_AGE_RECIPIENT to a public age1... recipient." >&2
      exit 1
    fi
    echo "WARNING: no UBYHOST_BACKUP_AGE_RECIPIENT, PostgreSQL dump skipped" >&2
  else
    command -v age >/dev/null 2>&1 || { echo "The 'age' binary is missing on the host." >&2; exit 1; }
    NEWEST="$(docker compose exec -T "${APP_SVC}" sh -c 'ls -1 /data/backups | sort | tail -1' | tr -d '\r')"
    [ -n "${NEWEST}" ] || { echo "No snapshot folder to hold the PostgreSQL dump." >&2; exit 1; }
    docker compose exec -T "${APP_SVC}" sh -c "rm -f /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp"
    # Written as .tmp and renamed only after the whole pipeline succeeded (pipefail), so no truncated .age is left.
    docker compose exec -T postgres pg_dump -U ubyhost -Fc ubyhost --exclude-table-data=ruian_address \
      | age -r "${RECIPIENT}" \
      | docker compose exec -T "${APP_SVC}" sh -c "cat > /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp && mv /data/backups/${NEWEST}/ubyhost-pg.dump.age.tmp /data/backups/${NEWEST}/ubyhost-pg.dump.age"
    echo "PostgreSQL dump bytes: $(docker compose exec -T "${APP_SVC}" sh -c "wc -c < /data/backups/${NEWEST}/ubyhost-pg.dump.age" | tr -d '\r')"
  fi
fi

if [ "${GO_ONLY}" = "1" ] && [ -n "${NEWEST:-}" ]; then
  # The Python script tarred the key material and encrypted it. Do the same
  # here: stream each file through age on the host so no plaintext ever lands
  # outside the volume, then delete it from the snapshot.
  RECIPIENT="${UBYHOST_BACKUP_AGE_RECIPIENT:-}"
  if [ -z "${RECIPIENT}" ]; then
    if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ]; then
      echo "Refusing to leave the secret key unencrypted in production." >&2
      exit 1
    fi
    echo "WARNING: no UBYHOST_BACKUP_AGE_RECIPIENT, secret key not copied into the snapshot" >&2
  else
    command -v age >/dev/null 2>&1 || { echo "The 'age' binary is missing on the host." >&2; exit 1; }
    for name in secret_key initial_admin_credentials; do
      if docker compose exec -T "${APP_SVC}" sh -c "test -f /data/${name}" >/dev/null 2>&1; then
        docker compose exec -T "${APP_SVC}" sh -c "cat /data/${name}" \
          | age -r "${RECIPIENT}" \
          | docker compose exec -T "${APP_SVC}" sh -c "cat > /data/backups/${NEWEST}/${name}.age.tmp && mv /data/backups/${NEWEST}/${name}.age.tmp /data/backups/${NEWEST}/${name}.age"
        echo "Encrypted ${name} into the snapshot."
      fi
    done
  fi
  # Time-based retention, as App/scripts/backup_data.sh does: drop snapshots
  # older than the window but always keep the newest one.
  RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"
  CUTOFF="$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%dT%H%M%SZ 2>/dev/null \
    || date -u -v-"${RETENTION_DAYS}"d +%Y%m%dT%H%M%SZ)"
  docker compose exec -T "${APP_SVC}" sh -c \
    "newest=\$(ls -1 /data/backups | sort | tail -1); for d in /data/backups/*/; do b=\$(basename \"\$d\"); [ \"\$b\" = \"\$newest\" ] && continue; s=\${b%%-*}; case \"\$s\" in *T*Z) ;; *) continue ;; esac; if [ \"\$s\" \\< \"${CUTOFF}\" ]; then rm -rf \"\$d\"; fi; done" \
    || echo "WARNING: retention sweep failed" >&2
  echo "Kept snapshots from the last ${RETENTION_DAYS} days (newest kept)."
fi

# Optional dead-man switch (e.g. healthchecks.io). Only reached on success,
# because set -e stops the script on any failure above.
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: backup succeeded but the ping to UBYHOST_BACKUP_PING_URL failed" >&2
fi
echo "Copy backups off-server periodically (S3, Google Drive, etc.)."
