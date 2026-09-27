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
# Always stop the app first so SQLite is not written during the copy.
# Container files are owned by uid 10001 (see Dockerfile).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

STAMP="${1:-}"
CONFIRM="${RESTORE_CONFIRM:-}"
IDENTITY="${AGE_IDENTITY_FILE:-}"

list_stamps() {
  docker compose exec -T ubyhost sh -c 'ls -1 /data/backups 2>/dev/null | sort -r' || true
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

# What is in this stamp? Encrypted (age), legacy plaintext, or nothing.
LAYOUT="$(docker compose exec -T ubyhost sh -c "
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

CONTAINER="$(docker compose ps -aq ubyhost)"
if [ -z "${CONTAINER}" ]; then
  echo "Could not find the ubyhost container — run ./scripts/deploy.sh first." >&2
  exit 1
fi

echo "==> Stopping ubyhost (Caddy stays up and will 502 until restart)"
docker compose stop ubyhost

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
  # The mount is read-only; the plaintext never lands on the volume except as
  # the database/secret the app needs. The host copy is removed by the trap.
  docker compose run --rm --user 0 --no-deps -v "${TMP}:/restore:ro" \
    --entrypoint bash ubyhost -lc "
      set -euo pipefail
      cp -a /restore/ubyhost.db /data/ubyhost.db
      if [ -f /restore/secret_key ]; then
        cp -a /restore/secret_key /data/secret_key
        chown 10001:10001 /data/secret_key
      fi
      chown 10001:10001 /data/ubyhost.db
      chmod 600 /data/ubyhost.db /data/secret_key 2>/dev/null || true
      echo Restored from encrypted ${STAMP}
    "
else
  echo "==> Restoring ${STAMP} (legacy plaintext)"
  docker compose run --rm --user 0 --no-deps --entrypoint bash ubyhost -lc "
    set -euo pipefail
    SRC=/data/backups/${STAMP}
    if [ ! -f \"\${SRC}/ubyhost.db\" ]; then
      echo \"Missing \${SRC}/ubyhost.db\" >&2
      ls -la /data/backups >&2 || true
      exit 1
    fi
    cp -a \"\${SRC}/ubyhost.db\" /data/ubyhost.db
    if [ -f \"\${SRC}/secret_key\" ]; then
      cp -a \"\${SRC}/secret_key\" /data/secret_key
      chown 10001:10001 /data/secret_key
    fi
    chown 10001:10001 /data/ubyhost.db
    chmod 600 /data/ubyhost.db /data/secret_key 2>/dev/null || true
    echo Restored from \${SRC}
  "
fi

echo "==> Starting ubyhost"
docker compose up -d ubyhost

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    echo "Restore complete. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "ubyhost did not become healthy — run ./scripts/logs.sh ubyhost" >&2
exit 1
