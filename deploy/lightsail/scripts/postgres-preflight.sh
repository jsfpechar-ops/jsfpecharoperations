#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=postgres-lib.sh
source "$(dirname "$0")/postgres-lib.sh"
load_private_env
require_postgres_backend

for tool in docker age rclone python3; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Required local operations tool is missing: ${tool}" >&2
    exit 1
  fi
done

if ! docker compose version --short >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 1
fi

# Compose validates the overlay without printing expanded environment values.
pg_compose config --quiet

printf '%s\n' "PostgreSQL operations preflight passed (no secret values displayed)."
