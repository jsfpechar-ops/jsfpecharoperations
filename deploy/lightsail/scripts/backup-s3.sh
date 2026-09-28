#!/usr/bin/env bash
# Copy the newest encrypted snapshot to S3 (rclone). Encrypted archives only.
#
# One-time setup (AWS) is documented in deploy/lightsail/README.md: a bucket in
# eu-central-1 with Block Public Access on, SSE-S3 default encryption, a
# lifecycle rule expiring objects after UBYHOST_BACKUP_RETENTION_DAYS, and an
# IAM user limited to this bucket.
#
# One-time: rclone config → Amazon S3 → remote name "s3" (or set RCLONE_REMOTE).
# Env: UBYHOST_S3_BUCKET (required), UBYHOST_S3_PREFIX (default UbyHost-backups).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
source "$(dirname "$0")/lib-docker.sh"

REMOTE="${RCLONE_REMOTE:-s3}"
BUCKET="${UBYHOST_S3_BUCKET:?set UBYHOST_S3_BUCKET to your bucket name}"
PREFIX="${UBYHOST_S3_PREFIX:-UbyHost-backups}"
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

# Refuse to upload anything but an encrypted archive. A plaintext snapshot here
# means OPS-1 is not configured; uploading it would recreate the exposure.
if ! docker compose exec -T ubyhost sh -c "ls -1 /data/backups/${LATEST}/*.age >/dev/null 2>&1"; then
  echo "Newest snapshot ${LATEST} has no .age archive — refusing to upload plaintext." >&2
  exit 1
fi

rm -rf "${TMP}"
mkdir -p "${TMP}"
docker cp "${CONTAINER}:/data/backups/${LATEST}" "${TMP}/${LATEST}"

DEST="${REMOTE}:${BUCKET}/${PREFIX}/${LATEST}"
rclone copy "${TMP}/${LATEST}" "${DEST}" --include "*.age" --stats-one-line
rm -rf "${TMP}"

echo "Uploaded to ${DEST}"
