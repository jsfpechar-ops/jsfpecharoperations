#!/usr/bin/env bash
# Weekly: snapshot DB on the server, copy the newest encrypted archive to
# Google Drive (rclone), and prune Drive copies older than the retention window.
#
# G-D2 keeps Drive alongside S3. Google processor terms (a DPA) exist only for
# Workspace/Cloud accounts; a consumer account has none. Confirm the account
# type before relying on this path (see FOLLOWUPS.md).
#
# One-time setup: install rclone, run `rclone config` → Google Drive → name it "gdrive".
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
source "$(dirname "$0")/lib-docker.sh"

REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_DIR="${RCLONE_BACKUP_FOLDER:-UbyHost-backups}"
RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"
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

# Refuse to upload anything but an encrypted archive. A plaintext snapshot here
# means OPS-1 is not configured; uploading it would recreate the exposure.
if ! docker compose exec -T ubyhost sh -c "ls -1 /data/backups/${LATEST}/*.age >/dev/null 2>&1"; then
  echo "Newest snapshot ${LATEST} has no .age archive — refusing to upload plaintext." >&2
  exit 1
fi

rm -rf "${TMP}"
mkdir -p "${TMP}"
docker cp "${CONTAINER}:/data/backups/${LATEST}" "${TMP}/${LATEST}"

rclone copy "${TMP}/${LATEST}" "${REMOTE}:${DRIVE_DIR}/${LATEST}" \
  --include "*.age" --stats-one-line
rm -rf "${TMP}"

# Bound Drive retention to the same window as the local snapshots.
if ! rclone delete --min-age "${RETENTION_DAYS}d" "${REMOTE}:${DRIVE_DIR}" --stats-one-line; then
  echo "ERROR: pruning old Drive backups failed; the ${RETENTION_DAYS}-day retention is not being kept." >&2
  exit 1
fi
rclone rmdirs --leave-root "${REMOTE}:${DRIVE_DIR}" || true

echo "Uploaded to ${REMOTE}:${DRIVE_DIR}/${LATEST}"
