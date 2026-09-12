#!/usr/bin/env bash
# Snapshot SQLite + secrets inside the running container (keeps last 10 backups).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env in ${ROOT}" >&2
  exit 1
fi

docker compose exec -T ubyhost bash /app/scripts/backup_data.sh
echo "Copy backups off-server periodically (S3, Google Drive, etc.)."
