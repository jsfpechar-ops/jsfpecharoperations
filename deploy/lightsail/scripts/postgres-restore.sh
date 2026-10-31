#!/usr/bin/env bash
# Restore the latest encrypted S3 chain into a newly-created isolated volume.
# Existing volumes are never cleared, replaced, or deleted by this script.
set -euo pipefail
umask 077

usage() {
  echo "Usage: $0 ubyhost-pg-restore-YYYYMMDDTHHMMSSZ[-label] [--target='YYYY-MM-DD HH:MM:SS+00']" >&2
  exit 2
}

volume_name="${1:-}"
[ -n "${volume_name}" ] || usage
shift
if ! [[ "${volume_name}" =~ ^ubyhost-pg-restore-[0-9]{8}T[0-9]{6}Z(-[a-z0-9][a-z0-9-]{0,20})?$ ]]; then
  echo "Restore volume name must be a fresh ubyhost-pg-restore timestamp name." >&2
  exit 2
fi
if [ "${volume_name}" = "ubyhost-postgres-data" ]; then
  echo "Refusing production PostgreSQL volume as a restore target." >&2
  exit 2
fi

target_args=()
if [ "$#" -gt 0 ]; then
  if [ "$#" -ne 1 ] || [[ "$1" != --target=* ]]; then
    usage
  fi
  target_value="${1#--target=}"
  if ! [[ "${target_value}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]][0-9]{2}:[0-9]{2}:[0-9]{2}\+00$ ]]; then
    echo "Target time must be UTC in YYYY-MM-DD HH:MM:SS+00 format." >&2
    exit 2
  fi
  target_args=(--type=time "--target=${target_value}")
fi

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend
pg_compose config --quiet

if docker volume inspect "${volume_name}" >/dev/null 2>&1; then
  echo "Refusing existing restore volume ${volume_name}; it may contain a prior recovery." >&2
  exit 1
fi
if [ -n "$(docker ps -aq --filter "volume=${volume_name}")" ]; then
  echo "Refusing restore volume already mounted by a container." >&2
  exit 1
fi

docker volume create \
  --label ubyhost.role=postgres-restore \
  --label "ubyhost.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "${volume_name}" >/dev/null

if ! docker run --rm --volume "${volume_name}:/restore" \
  --entrypoint sh ubyhost-postgres:18.6-pgbackrest-2.60.0 \
  -ec 'test -d /restore && test -z "$(ls -A /restore)"'; then
  echo "New restore volume was not empty; preserving it and refusing restore." >&2
  exit 1
fi

COMPOSE_PROFILES="postgres-restore" \
UBYHOST_PG_RESTORE_VOLUME="${volume_name}" \
  pg_compose run --rm --no-deps postgres-restore \
    --stanza=ubyhost --pg1-path=/restore/18/docker "${target_args[@]}" restore

# Prove the restored cluster is readable by the pinned binaries before anyone
# starts it: PG_VERSION and pg_controldata must both be present and parseable.
docker run --rm --volume "${volume_name}:/restore" \
  --entrypoint sh ubyhost-postgres:18.6-pgbackrest-2.60.0 \
  -ec 'test -f /restore/18/docker/PG_VERSION && pg_controldata /restore/18/docker >/dev/null'

printf 'Restore files created in isolated volume %s and verified (PG_VERSION + pg_controldata). It was not started as a writer.\n' "${volume_name}"
printf '%s\n' "Keep this volume until the owner records reconciliation and recovery disposition."
