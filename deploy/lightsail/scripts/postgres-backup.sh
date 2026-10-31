#!/usr/bin/env bash
# pgBackRest encrypts and archives WAL synchronously to the private S3 prefix.
# A daily full backup establishes/extends the 30-day time-based recovery chain.
set -euo pipefail
umask 077

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend
backup_type="${1:-full}"
case "${backup_type}" in
  full|diff) ;;
  *) echo "Usage: $0 [full|diff]" >&2; exit 2 ;;
esac
pg_compose config --quiet

if ! pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check >/dev/null; then
  echo "pgBackRest check failed; retaining the previous recovery chain." >&2
  exit 1
fi
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost "--type=${backup_type}" backup
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check >/dev/null
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner \
  --stanza=ubyhost info --output=json \
  | pg_compose run --rm --no-deps -T --entrypoint python ubyhost \
      scripts/pg_schema.py record-backup \
      --expect-database "${UBYHOST_PG_DATABASE}" --stanza ubyhost

# Never write connection strings or backup contents to a report.
printf '{"at":"%s","stanza":"ubyhost","result":"ok","retention_days":30}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ -n "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "${UBYHOST_BACKUP_PING_URL}" >/dev/null || \
    echo "WARNING: PostgreSQL backup succeeded but its dead-man switch failed." >&2
fi
