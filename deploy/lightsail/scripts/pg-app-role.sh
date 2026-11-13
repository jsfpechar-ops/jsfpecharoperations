#!/usr/bin/env bash
# 1206 (K-S11): create the restricted app role and give it the app objects.
#   ./scripts/pg-app-role.sh apply   run pg-app-role.sql as the bootstrap superuser
#   ./scripts/pg-app-role.sh check   read-only: role attributes and objects not owned by the app role
# Run from deploy/lightsail on the server. Idempotent; re-run after a restore or a
# cutover (objects created by the superuser). It never drops anything.
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  apply)
    docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 < scripts/pg-app-role.sql
    ;;
  check)
    docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 -c \
      "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin FROM pg_roles WHERE rolname IN ('ubyhost','ubyhost_app') ORDER BY 1" -c \
      "SELECT count(*) AS objects_not_owned_by_app FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f') AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = 'ubyhost_app')"
    ;;
  *)
    echo "usage: $0 apply|check" >&2
    exit 2
    ;;
esac
