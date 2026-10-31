#!/usr/bin/env bash
# Initialize the encrypted off-host pgBackRest stanza and create the first base.
set -euo pipefail
umask 077
# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend
pg_compose config --quiet

if ! pg_compose exec -T postgres pg_isready -U "${UBYHOST_PG_SUPERUSER}" -d "${UBYHOST_PG_DATABASE}" >/dev/null; then
  echo "PostgreSQL is not healthy; no backup stanza was changed." >&2
  exit 1
fi
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost stanza-create
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost --type=full backup
pg_compose exec -T postgres /usr/local/bin/pgbackrest-runner --stanza=ubyhost check
printf '%s\n' "Initial encrypted base backup and WAL archive check completed."
