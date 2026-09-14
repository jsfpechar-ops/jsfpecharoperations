#!/usr/bin/env bash
# Monthly: snapshot DB on the server, copy newest folder to S3 (rclone).
# One-time: rclone config → Amazon S3 → remote name "s3" (or set RCLONE_REMOTE).
# Env: UBYHOST_S3_BUCKET (required), UBYHOST_S3_PREFIX (default UbyHost-backups).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
source "$(dirname "$0")/lib-docker.sh"

env_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' .env 2>/dev/null
}

REMOTE="${UBYHOST_S3_REMOTE:-${RCLONE_REMOTE:-$(env_value UBYHOST_S3_REMOTE)}}"
REMOTE="${REMOTE:-s3}"
BUCKET="${UBYHOST_S3_BUCKET:-$(env_value UBYHOST_S3_BUCKET)}"
PREFIX="${UBYHOST_S3_PREFIX:-$(env_value UBYHOST_S3_PREFIX)}"
PREFIX="${PREFIX:-UbyHost-backups}"

if [ -z "${BUCKET}" ]; then
  echo "Set UBYHOST_S3_BUCKET in ${ROOT}/.env or the process environment" >&2
  exit 1
fi
CONTAINER="$(ubyhost_container_ref "${ROOT}")" || exit 1
TMP="/tmp/ubyhost-s3-upload"

if ! command -v rclone >/dev/null 2>&1; then
  echo "Install rclone first: sudo apt-get install -y rclone" >&2
  exit 1
fi

if ! rclone listremotes | grep -q "^${REMOTE}:$"; then
  echo "No rclone remote '${REMOTE}:' — run: rclone config (storage: Amazon S3)" >&2
  exit 1
fi

./scripts/backup.sh

LATEST="$(docker compose exec -T ubyhost sh -c 'ls -1 /data/backups 2>/dev/null | sort -r | head -1')"
if [ -z "${LATEST}" ]; then
  echo "No backup folder in container /data/backups" >&2
  exit 1
fi

rm -rf "${TMP}"
mkdir -p "${TMP}"
docker cp "${CONTAINER}:/data/backups/${LATEST}" "${TMP}/${LATEST}"

DEST="${REMOTE}:${BUCKET}/${PREFIX}/${LATEST}"
rclone copy "${TMP}/${LATEST}" "${DEST}" --stats-one-line
rm -rf "${TMP}"

echo "Uploaded to ${DEST}"
