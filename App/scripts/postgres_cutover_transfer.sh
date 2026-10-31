#!/usr/bin/env bash
# One-shot, quiesced SQLite snapshot, encrypted artifact, and 0455 transfer.
# Plaintext is confined to tmpfs and removed on every exit path.
set -euo pipefail
umask 077

mode="transfer"
if [ "${1:-}" = "--verify-only" ]; then
  mode="verify-only"
  shift
fi
stamp="${1:-}"
if ! [[ "${stamp}" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
  echo "Usage: postgres_cutover_transfer.sh [--verify-only] YYYYMMDDTHHMMSSZ" >&2
  exit 2
fi
if [ -z "${UBYHOST_BACKUP_AGE_RECIPIENT:-}" ]; then
  echo "UBYHOST_BACKUP_AGE_RECIPIENT is required; refusing plaintext snapshot." >&2
  exit 1
fi
if [ -z "${UBYHOST_PG_DATABASE:-}" ]; then
  echo "UBYHOST_PG_DATABASE is required for the explicit transfer guard." >&2
  exit 1
fi

snapshot="/dev/shm/ubyhost-pg-cutover-${stamp}.sqlite"
backup_dir="/data/backups/postgres-cutover"
artifact="${backup_dir}/ubyhost-sqlite-cutover-${stamp}.sqlite.age"
report="${backup_dir}/transfer-${stamp}.json"
verify_report="/dev/shm/ubyhost-pg-transfer-verify-${stamp}.json"
cleanup() {
  rm -f "${snapshot}"
}
trap cleanup EXIT

mkdir -p "${backup_dir}"
chmod 700 "${backup_dir}"
if [ "${mode}" = "transfer" ]; then
  if [ -e "${artifact}" ] || [ -L "${artifact}" ] || [ -e "${report}" ] || [ -L "${report}" ]; then
    echo "Cutover artifact/report already exists for ${stamp}; refusing overwrite." >&2
    exit 1
  fi
else
  if [ ! -s "${artifact}" ] || [ -L "${artifact}" ] || [ -e "${verify_report}" ] || [ -L "${verify_report}" ]; then
    echo "Recovery verification requires the original encrypted artifact and a fresh report path." >&2
    exit 1
  fi
fi
source_size="$(stat -c '%s' /data/ubyhost.db 2>/dev/null || stat -f '%z' /data/ubyhost.db)"
free_bytes="$(df -Pk /dev/shm | awk 'NR==2 {print $4 * 1024}')"
needed_bytes="$((source_size + 67108864))"
if [ "${free_bytes}" -lt "${needed_bytes}" ]; then
  echo "Tmpfs capacity is below SQLite source size plus 64 MiB safety margin; refusing snapshot." >&2
  exit 1
fi
python /app/scripts/create_postgres_cutover_snapshot.py \
  --source /data/ubyhost.db --destination "${snapshot}"
if [ "${mode}" = "transfer" ]; then
  age -r "${UBYHOST_BACKUP_AGE_RECIPIENT}" \
    -o "${artifact}.partial" "${snapshot}"
  if [ ! -s "${artifact}.partial" ]; then
    echo "Encrypted SQLite recovery artifact is empty." >&2
    exit 1
  fi
  mv "${artifact}.partial" "${artifact}"
  python /app/scripts/sqlite_to_postgres.py \
    --source "${snapshot}" --report "${report}" \
    --expect-database "${UBYHOST_PG_DATABASE}"
  printf '{"artifact":"%s","report":"%s","result":"transferred"}\n' \
    "$(basename "${artifact}")" "$(basename "${report}")"
else
  python /app/scripts/sqlite_to_postgres.py \
    --source "${snapshot}" --report "${verify_report}" \
    --expect-database "${UBYHOST_PG_DATABASE}" --verify-only
  rm -f "${verify_report}"
  printf '{"artifact":"%s","result":"reconciliation_verified"}\n' \
    "$(basename "${artifact}")"
fi
