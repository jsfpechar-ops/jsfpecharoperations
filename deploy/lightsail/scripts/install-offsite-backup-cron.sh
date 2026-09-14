#!/usr/bin/env bash
# Keep Google Drive weekly and S3 monthly. Safe to run repeatedly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

crontab -l 2>/dev/null \
  | grep -v '/scripts/backup-gdrive.sh' \
  | grep -v '/scripts/backup-s3.sh' > "${TMP}" || true

cat >> "${TMP}" <<EOF
0 4 * * 0 cd ${ROOT} && ./scripts/backup-gdrive.sh >> /var/log/ubyhost-gdrive.log 2>&1
0 5 1 * * cd ${ROOT} && ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1
EOF

crontab "${TMP}"
echo "Installed weekly Google Drive backup (Sunday 04:00 UTC)."
echo "Installed monthly S3 backup (first day of month 05:00 UTC)."
