#!/usr/bin/env bash
# Report the server-observed durable archive lag; do not claim an RPO from
# archive_timeout alone. Synchronous archive-push is acknowledged only after
# pgBackRest has accepted the segment into its encrypted S3 repository.
set -euo pipefail
# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend

pg_compose exec -T postgres psql -X -qAt -U "${UBYHOST_PG_SUPERUSER}" \
  -d "${UBYHOST_PG_DATABASE}" -c \
  "SELECT json_build_object('last_archived_time', last_archived_time, 'last_archived_wal', last_archived_wal, 'failed_count', failed_count, 'lag_seconds', CASE WHEN last_archived_time IS NULL THEN NULL ELSE GREATEST(0, EXTRACT(EPOCH FROM (clock_timestamp() - last_archived_time))::integer) END)::text FROM pg_stat_archiver;"
