#!/usr/bin/env bash
# Weekly: snapshot DB on the server, copy newest folder to Google Drive (rclone).
# One-time setup: install rclone, run `rclone config` → Google Drive → name it "gdrive".
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
source "$(dirname "$0")/lib-docker.sh"

env_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' .env 2>/dev/null
}

REMOTE="${UBYHOST_GDRIVE_REMOTE:-${RCLONE_REMOTE:-$(env_value UBYHOST_GDRIVE_REMOTE)}}"
REMOTE="${REMOTE:-gdrive}"
DRIVE_DIR="${RCLONE_BACKUP_FOLDER:-$(env_value UBYHOST_GDRIVE_FOLDER)}"
DRIVE_DIR="${DRIVE_DIR:-UbyHost-backups}"
CONTAINER="$(ubyhost_container_ref "${ROOT}")" || exit 1
TMP="/tmp/ubyhost-gdrive-upload"

if ! command -v rclone >/dev/null 2>&1; then
  echo "Install rclone first: sudo apt-get install -y rclone" >&2
  exit 1
fi

if ! rclone listremotes | grep -q "^${REMOTE}:$"; then
  echo "No rclone remote '${REMOTE}:' — run: rclone config" >&2
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

rclone copy "${TMP}/${LATEST}" "${REMOTE}:${DRIVE_DIR}/${LATEST}" --stats-one-line
rm -rf "${TMP}"

echo "Uploaded to ${REMOTE}:${DRIVE_DIR}/${LATEST}"
