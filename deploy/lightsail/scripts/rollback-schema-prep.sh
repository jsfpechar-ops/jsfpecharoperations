#!/usr/bin/env bash
# Drop schema from a forward-only migration when rolling back app images.
# Sourced by deploy.sh rollback() and rollback-prod.sh (not run directly).
#
# Migration 00024 adds guide_import.codes_left_out. Older Python and Go images
# refuse to start when column counts drift (postgres_schema_status / migrate check).

rollback_drop_guide_import_00024() {
  local dry="${ROLLBACK_SCHEMA_DRY_RUN:-0}"
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    return 0
  fi
  if ! docker compose ps -q --status running postgres 2>/dev/null | grep -q .; then
    echo "WARNING: postgres is not running; cannot drop guide_import.codes_left_out for rollback." >&2
    return 1
  fi
  local present
  present="$(docker compose exec -T postgres psql -U ubyhost -d ubyhost -Atc \
    "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'guide_import' AND column_name = 'codes_left_out' LIMIT 1" \
    2>/dev/null | tr -d '[:space:]')"
  if [ "${present}" != "1" ]; then
    return 0
  fi
  if [ "${dry}" = "1" ]; then
    echo "Would run: ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;"
    return 0
  fi
  echo "==> Dropping guide_import.codes_left_out (migration 00024) so the previous release can start"
  docker compose exec -T postgres psql -U ubyhost -d ubyhost -v ON_ERROR_STOP=1 \
    -c "ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;"
}