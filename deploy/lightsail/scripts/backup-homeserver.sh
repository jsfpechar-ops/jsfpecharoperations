#!/usr/bin/env bash
# Weekly off-site copy of the newest encrypted snapshot to the homeserver vault
# (restic over SFTP). Encrypted archives only, like backup-s3.sh: a plaintext
# snapshot means OPS-1 is not configured and is refused.
#
# One-time setup: deploy/homeserver/setup-vault.sh on the homeserver, then
# ./scripts/homeserver-vault-init.sh here. Full steps:
# deploy/lightsail/README.md, "Weekly backup to the homeserver".
#
# Env: UBYHOST_HS_REPO (required, e.g. sftp:homeserver-vault:/restic),
#      UBYHOST_HS_PASSWORD_FILE (default ~/.ubyhost-hs-restic-password),
#      UBYHOST_HS_KEEP_WEEKLY (default 8).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# shellcheck source=lib-docker.sh
source "$(dirname "$0")/lib-docker.sh"

REPO="${UBYHOST_HS_REPO:?set UBYHOST_HS_REPO, e.g. sftp:homeserver-vault:/restic}"
PASSWORD_FILE="${UBYHOST_HS_PASSWORD_FILE:-$HOME/.ubyhost-hs-restic-password}"
KEEP_WEEKLY="${UBYHOST_HS_KEEP_WEEKLY:-8}"
CONTAINER="$(ubyhost_container_ref "${ROOT}")" || exit 1
TMP="/tmp/ubyhost-hs-upload"

if ! command -v restic >/dev/null 2>&1; then
  echo "Install restic first: sudo apt-get install -y restic" >&2
  exit 1
fi
if [ ! -f "${PASSWORD_FILE}" ]; then
  echo "Missing restic password file ${PASSWORD_FILE} - run ./scripts/homeserver-vault-init.sh first." >&2
  exit 1
fi

export RESTIC_REPOSITORY="${REPO}"
export RESTIC_PASSWORD_FILE="${PASSWORD_FILE}"

# Fresh snapshot first, exactly like the S3 copy: a failed backup also stops
# the upload.
./scripts/backup.sh

LATEST="$(docker compose exec -T ubyhost sh -c 'ls -1 /data/backups 2>/dev/null | sort -r | head -1')"
if [ -z "${LATEST}" ]; then
  echo "No backup folder in container /data/backups" >&2
  exit 1
fi

# Refuse to upload anything but an encrypted archive.
if ! docker compose exec -T ubyhost sh -c "ls -1 /data/backups/${LATEST}/*.age >/dev/null 2>&1"; then
  echo "Newest snapshot ${LATEST} has no .age archive - refusing to upload plaintext." >&2
  exit 1
fi

rm -rf "${TMP}"
mkdir -p "${TMP}"
docker cp "${CONTAINER}:/data/backups/${LATEST}" "${TMP}/${LATEST}"

restic backup "${TMP}/${LATEST}" --tag "snapshot:${LATEST}"
restic forget --keep-weekly "${KEEP_WEEKLY}" --prune
restic snapshots

rm -rf "${TMP}"
echo "Homeserver copy done: ${REPO} (snapshot ${LATEST}, keep-weekly ${KEEP_WEEKLY})"
