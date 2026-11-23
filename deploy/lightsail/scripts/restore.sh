#!/usr/bin/env bash
# Restore ubyhost.db (and secret_key if present) from a snapshot on the volume.
#
# Usage (from deploy/lightsail):
#   ./scripts/restore.sh                  # interactive: latest /data/backups stamp
#   ./scripts/restore.sh 20260915T030000Z
#   RESTORE_CONFIRM=yes ./scripts/restore.sh 20260915T030000Z
#   AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/restore.sh 20260915T030000Z
#
# Encrypted snapshots (OPS-1) are a single `ubyhost-backup.tar.age`; they need
# the age private identity on the host, never on the volume. Legacy plaintext
# snapshots (a bare `ubyhost.db`) still restore unchanged.
#
# On PostgreSQL deployments use pg-restore.sh instead of this script.
# Always stop the app first so SQLite is not written during the copy.
# Container files are owned by uid 10001 (see Dockerfile).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib-docker.sh"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

if grep -Eq '^UBYHOST_DATABASE_URL=' .env 2>/dev/null; then
  echo "This server runs on PostgreSQL. Use ./scripts/pg-restore.sh with AGE_IDENTITY_FILE instead." >&2
  exit 2
fi

STAMP="${1:-}"
CONFIRM="${RESTORE_CONFIRM:-}"
IDENTITY="${AGE_IDENTITY_FILE:-}"

list_stamps() {
  ubyhost_app_run_sh 'ls -1 /data/backups 2>/dev/null | sort -r' || true
}

if [ -z "${STAMP}" ]; then
  echo "Available stamps on volume (newest first):"
  list_stamps
  echo ""
  read -r -p "Stamp to restore (or empty to abort): " STAMP
fi

if [ -z "${STAMP}" ]; then
  echo "No stamp given — abort." >&2
  exit 1
fi

if ! printf '%s' "${STAMP}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$'; then
  echo "Stamp '${STAMP}' is not a backup name like 20260915T030000Z." >&2
  exit 1
fi

# What is in this stamp? Encrypted (age), legacy plaintext, or nothing.
LAYOUT="$(ubyhost_app_run_sh "
  if [ -f /data/backups/${STAMP}/ubyhost-backup.tar.age ]; then echo encrypted;
  elif [ -f /data/backups/${STAMP}/ubyhost.db ]; then echo plaintext;
  else echo missing; fi
" 2>/dev/null | tr -d '\r')"

if [ "${LAYOUT}" = "missing" ]; then
  echo "No snapshot ${STAMP} on the volume (or it holds neither .age nor .db)." >&2
  list_stamps >&2
  exit 1
fi

if [ "${LAYOUT}" = "encrypted" ] && [ -z "${IDENTITY}" ]; then
  echo "Snapshot ${STAMP} is encrypted." >&2
  echo "Set AGE_IDENTITY_FILE=/path/on/host/to/age-identity (never inside the volume)." >&2
  exit 1
fi
if [ "${LAYOUT}" = "encrypted" ] && [ ! -f "${IDENTITY}" ]; then
  echo "AGE_IDENTITY_FILE=${IDENTITY} does not exist on the host." >&2
  exit 1
fi

if [ "${CONFIRM}" != "yes" ]; then
  echo "This replaces /data/ubyhost.db from backups/${STAMP} (${LAYOUT})."
  echo "Host login cookies stay valid only if secret_key is restored too."
  read -r -p "Type yes to continue: " CONFIRM
fi
if [ "${CONFIRM}" != "yes" ]; then
  echo "Aborted." >&2
  exit 1
fi

CONTAINER="$(ubyhost_container_ref "${ROOT}" 2>/dev/null || true)"
if [ -z "${CONTAINER}" ]; then
  CONTAINER="$(docker compose ps -aq ubyhost 2>/dev/null | head -1 || true)"
  CONTAINER="${CONTAINER:-$(docker compose --profile go ps -aq ubyhost-go 2>/dev/null | head -1 || true)}"
fi
if [ -z "${CONTAINER}" ]; then
  echo "Could not find an app container — run ./scripts/deploy.sh first." >&2
  exit 1
fi

RUN_SVC=ubyhost
RUN_ARGS=()
INSTALL_ARGS=(run --rm --user 0 --no-deps)
if compose_has_go_app && ! compose_has_python_app; then
  RUN_SVC=ubyhost-go
  RUN_ARGS=(--profile go)
  INSTALL_ARGS=(--profile go run --rm --user 0 --no-deps)
fi

echo "==> Stopping worker and app (Caddy stays up and will 502 until restart)"
# WP06: the scheduler worker writes to the database too.
docker compose stop worker 2>/dev/null || true
if [ "${RUN_SVC}" = ubyhost-go ]; then
  docker compose --profile go stop ubyhost-go ubyhost-go-b 2>/dev/null || true
else
  docker compose stop ubyhost 2>/dev/null || true
fi

if [ "${LAYOUT}" = "encrypted" ]; then
  TMP="$(mktemp -d)"
  chmod 700 "${TMP}"
  trap 'rm -rf "${TMP}"' EXIT

  echo "==> Pulling and decrypting ${STAMP} on the host"
  docker cp "${CONTAINER}:/data/backups/${STAMP}/ubyhost-backup.tar.age" \
    "${TMP}/ubyhost-backup.tar.age"
  age -d -i "${IDENTITY}" -o "${TMP}/ubyhost-backup.tar" "${TMP}/ubyhost-backup.tar.age"
  tar -C "${TMP}" -xf "${TMP}/ubyhost-backup.tar"
  rm -f "${TMP}/ubyhost-backup.tar" "${TMP}/ubyhost-backup.tar.age"

  echo "==> Installing the decrypted files into the volume"
  docker compose "${INSTALL_ARGS[@]}" -v "${TMP}:/restore:ro" \
    --entrypoint bash "${RUN_SVC}" -lc "
      set -euo pipefail
      if [ -f /data/ubyhost.db ]; then cp -a /data/ubyhost.db /data/ubyhost.db.before-restore-\$(date -u +%Y%m%dT%H%M%SZ); fi
      rm -f /data/ubyhost.db-wal /data/ubyhost.db-shm
      cp -a /restore/ubyhost.db /data/ubyhost.db
      if [ -f /restore/secret_key ]; then
        cp -a /restore/secret_key /data/secret_key
        chown 10001:10001 /data/secret_key
      fi
      chown 10001:10001 /data/ubyhost.db
      chmod 600 /data/ubyhost.db /data/secret_key 2>/dev/null || true
      test \"\$(sqlite3 /data/ubyhost.db 'PRAGMA integrity_check;')\" = \"ok\" || { echo \"Restored database failed integrity_check\" >&2; exit 1; }
      echo Restored from encrypted ${STAMP}
    "
else
  echo "==> Restoring ${STAMP} (legacy plaintext)"
  docker compose "${INSTALL_ARGS[@]}" --entrypoint bash "${RUN_SVC}" -lc "
    set -euo pipefail
    SRC=/data/backups/${STAMP}
    if [ ! -f \"\${SRC}/ubyhost.db\" ]; then
      echo \"Missing \${SRC}/ubyhost.db\" >&2
      ls -la /data/backups >&2 || true
      exit 1
    fi
    if [ -f /data/ubyhost.db ]; then cp -a /data/ubyhost.db /data/ubyhost.db.before-restore-\$(date -u +%Y%m%dT%H%M%SZ); fi
    rm -f /data/ubyhost.db-wal /data/ubyhost.db-shm
    cp -a \"\${SRC}/ubyhost.db\" /data/ubyhost.db
    if [ -f \"\${SRC}/secret_key\" ]; then
      cp -a \"\${SRC}/secret_key\" /data/secret_key
      chown 10001:10001 /data/secret_key
    fi
    chown 10001:10001 /data/ubyhost.db
    chmod 600 /data/ubyhost.db /data/secret_key 2>/dev/null || true
    test \"\$(sqlite3 /data/ubyhost.db 'PRAGMA integrity_check;')\" = \"ok\" || { echo \"Restored database failed integrity_check\" >&2; exit 1; }
    echo Restored from \${SRC}
  "
fi

echo "==> Starting app and worker"
if [ "${RUN_SVC}" = ubyhost-go ]; then
  docker compose --profile go up -d ubyhost-go
else
  docker compose up -d ubyhost worker
fi

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if ubyhost_app_healthz_ok; then
    echo "Restore complete. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "The app did not become healthy — run ./scripts/logs.sh" >&2
exit 1