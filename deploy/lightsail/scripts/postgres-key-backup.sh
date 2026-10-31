#!/usr/bin/env bash
# Age-encrypted off-host copy of .env, TLS keys, DB service secrets and the
# app-side secret_key/bootstrap files. PostgreSQL data/WAL is handled by
# pgBackRest; passport uploads remain deliberately outside this contract.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend

REMOTE="${RCLONE_REMOTE:-s3}"
BUCKET="${UBYHOST_S3_BUCKET:?set UBYHOST_S3_BUCKET for the existing rclone S3 remote}"
PREFIX="${UBYHOST_PG_KEY_BACKUP_PREFIX:-UbyHost-postgres-keys}"
RETENTION_DAYS="${UBYHOST_BACKUP_RETENTION_DAYS:-30}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/ubyhost-pg-keys.XXXXXX")"
trap 'rm -rf "${TMP}"' EXIT
chmod 700 "${TMP}"
DEST="${REMOTE}:${BUCKET}/${PREFIX}"

if ! command -v rclone >/dev/null 2>&1 || ! rclone listremotes | grep -Fqx "${REMOTE}:"; then
  echo "Configured rclone remote is unavailable: ${REMOTE}:" >&2
  exit 1
fi
if ! [[ "${RETENTION_DAYS}" =~ ^[1-9][0-9]{0,3}$ ]]; then
  echo "UBYHOST_BACKUP_RETENTION_DAYS must be a positive day count." >&2
  exit 1
fi

# H1: retention may only prune old bundles when this run is proven to carry app
# key material. Remote age archives cannot be inspected here (the identity is
# offline by design), so the invariant is enforced at the source: either the
# /data key files exist (the helper refuses symlinks and reports names only) or
# .env defines the key. Without either, the last key-bearing bundle could age
# out, so fail closed before anything is uploaded and before pruning.
key_check="$(pg_compose run --rm --no-deps -T --entrypoint python ubyhost \
  /app/scripts/postgres_key_bundle.py --check-only)" || {
  echo "Could not inspect the app-side key files; refusing the key backup." >&2
  exit 1
}
case "${key_check}" in
  keys_found=*) key_files_found="${key_check#keys_found=}" ;;
  *) echo "Unexpected app-key check output; refusing the key backup." >&2; exit 1 ;;
esac
if ! [[ "${key_files_found}" =~ ^[0-9]+$ ]]; then
  echo "Unexpected app-key count '${key_files_found}'; refusing the key backup." >&2
  exit 1
fi
env_carries_key=0
if grep -qE '^(UBYHOST_SECRET_KEY|UBYHOST_DATA_KEYS)=.+' .env; then
  env_carries_key=1
fi
if [ "${key_files_found}" -eq 0 ] && [ "${env_carries_key}" != 1 ]; then
  echo "No app key material found: no /data key files and no UBYHOST_SECRET_KEY/UBYHOST_DATA_KEYS in .env." >&2
  echo "Refusing to upload a keyless bundle and age out the last key-bearing one." >&2
  exit 1
fi

# Build a relative path list without following symlinks or exposing contents.
secret_paths=(
  "${UBYHOST_PG_SUPERUSER_PASSWORD_FILE}"
  "${UBYHOST_PG_BACKREST_S3_KEY_FILE}"
  "${UBYHOST_PG_BACKREST_S3_SECRET_FILE}"
  "${UBYHOST_PG_BACKREST_CIPHER_PASS_FILE}"
)
paths=("${PG_OPS_ROOT#/}/.env" "${PG_OPS_ROOT#/}/caddy/certs")
for path in "${secret_paths[@]}"; do
  case "${path}" in
    /*) ;;
    *) echo "Secret file path must be absolute." >&2; exit 1 ;;
  esac
  if [[ "${path}" == *"/../"* || "${path}" == */.. ]]; then
    echo "Secret file path contains a parent traversal." >&2
    exit 1
  fi
  if [ ! -f "${path}" ] || [ -L "${path}" ]; then
    echo "Required secret file is missing or is a symlink: ${path}" >&2
    exit 1
  fi
  paths+=("${path#/}")
done

# Host files and container key files are separately streamed through age; no
# plaintext tarball is written to disk or sent to rclone.
tar -C / -cf - "${paths[@]}" \
  | pg_compose run --rm --no-deps -T --entrypoint age ubyhost \
      -r "${UBYHOST_BACKUP_AGE_RECIPIENT}" \
  >"${TMP}/${STAMP}-host.tar.age"
pg_compose run --rm --no-deps -T --entrypoint python ubyhost \
  /app/scripts/postgres_key_bundle.py \
  | pg_compose run --rm --no-deps -T --entrypoint age ubyhost \
      -r "${UBYHOST_BACKUP_AGE_RECIPIENT}" \
  >"${TMP}/${STAMP}-data.tar.age"

for kind in host data; do
  file="${TMP}/${STAMP}-${kind}.tar.age"
  if [ ! -s "${file}" ]; then
    echo "Encrypted ${kind} key bundle is missing or empty." >&2
    exit 1
  fi
  remote_file="${DEST}/ubyhost-postgres-keys_${STAMP}_${kind}.tar.age"
  if rclone lsf --files-only "${DEST}" | grep -Fqx "$(basename "${remote_file}")"; then
    echo "Refusing to overwrite existing age key archive for ${STAMP}/${kind}." >&2
    exit 1
  fi
  rclone copyto "${file}" "${remote_file}"
  rclone check "${file}" "${DEST}/ubyhost-postgres-keys_${STAMP}_${kind}.tar.age" --download
done

# Keep complete timestamp pairs from the time window and always keep the newest
# verified pair. Unknown names stop pruning instead of risking the last chain.
# Pruning is also gated by the key-material proof above: this run's newest pair
# carries keys (files or .env), so removing older pairs cannot delete the last
# key-bearing bundle. The host bundle always contains .env; the data bundle
# contains whichever key files the helper found.
remote_files=()
pair_seen=()
while IFS= read -r file; do
  [ -n "${file}" ] && remote_files+=("${file}")
done < <(rclone lsf --files-only "${DEST}")
newest=""
for file in "${remote_files[@]}"; do
  if [[ "${file}" =~ ^ubyhost-postgres-keys_([0-9]{8}T[0-9]{6}Z)_(host|data)\.tar\.age$ ]]; then
    stamp="${BASH_REMATCH[1]}"
    kind="${BASH_REMATCH[2]}"
    pair_seen+=("${stamp},${kind}")
    if [[ -z "${newest}" || "${stamp}" > "${newest}" ]]; then
      newest="${stamp}"
    fi
  else
    echo "Unrecognized object in PostgreSQL key-backup prefix; refusing retention pruning." >&2
    exit 1
  fi
done

pair_stamps=()
for key in "${pair_seen[@]}"; do
  pair_stamp="${key%%,*}"
  found=0
  for existing in "${pair_stamps[@]}"; do
    [ "${existing}" = "${pair_stamp}" ] && found=1
  done
  [ "${found}" = 1 ] || pair_stamps+=("${pair_stamp}")
done
for pair_stamp in "${pair_stamps[@]}"; do
  host_found=0 data_found=0
  for key in "${pair_seen[@]}"; do
    [ "${key}" = "${pair_stamp},host" ] && host_found=1
    [ "${key}" = "${pair_stamp},data" ] && data_found=1
  done
  if [ "${host_found}" != 1 ] || [ "${data_found}" != 1 ]; then
    echo "Incomplete remote key-bundle timestamp ${pair_stamp}; refusing retention pruning." >&2
    exit 1
  fi
done
if [ "${newest}" != "${STAMP}" ]; then
  echo "Newest remote key bundle did not match this verified run; refusing pruning." >&2
  exit 1
fi
printf 'App key backup verified: %s key file(s) in the data bundle, .env key present=%s; retention window %s days.\n' \
  "${key_files_found}" "${env_carries_key}" "${RETENTION_DAYS}"
cutoff_epoch="$(( $(date -u +%s) - RETENTION_DAYS * 86400 ))"
for pair_stamp in "${pair_stamps[@]}"; do
  pair_epoch="$(date -u -j -f '%Y%m%dT%H%M%SZ' "${pair_stamp}" +%s 2>/dev/null || date -u -d "${pair_stamp:0:8} ${pair_stamp:9:2}:${pair_stamp:11:2}:${pair_stamp:13:2} UTC" +%s)"
  if [ "${pair_stamp}" != "${newest}" ] && [ "${pair_epoch}" -lt "${cutoff_epoch}" ]; then
    # Delete both verified members of the old pair; never leave a surviving half.
    rclone deletefile "${DEST}/ubyhost-postgres-keys_${pair_stamp}_host.tar.age"
    rclone deletefile "${DEST}/ubyhost-postgres-keys_${pair_stamp}_data.tar.age"
  fi
done
printf '{"at":"%s","encrypted":true,"retention_days":%s,"result":"ok"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${RETENTION_DAYS}"
