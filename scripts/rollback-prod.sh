#!/usr/bin/env bash
# Manual production rollback helper (dry-run by default).
#
# Usage (from the repo root on the server):
#   ./scripts/rollback-prod.sh              # print the steps, change nothing
#   ROLLBACK_CONFIRM=yes ./scripts/rollback-prod.sh
#
# Drops migration 00024's guide_import.codes_left_out when present, restores
# :previous images and .deployed-sha compose, reloads Caddy, checks /healthz.
# Does not undo goose migrations beyond that column (same as deploy.sh rollback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIGHTSAIL="${ROOT}/deploy/lightsail"
cd "${LIGHTSAIL}"

if [ ! -f .env ]; then
  echo "Missing .env in ${LIGHTSAIL}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

DRY=1
if [ "${ROLLBACK_CONFIRM:-}" = "yes" ]; then
  DRY=0
fi

PREV_SHA="$(cat .deployed-sha 2>/dev/null || true)"
echo "Rollback target commit: ${PREV_SHA:-unknown (.deployed-sha missing)}"
echo "Mode: $([ "${DRY}" = "1" ] && echo dry-run || echo execute)"

# shellcheck source=rollback-schema-prep.sh
# shellcheck disable=SC1091
source ./scripts/rollback-schema-prep.sh
ROLLBACK_SCHEMA_DRY_RUN="${DRY}" rollback_drop_guide_import_00024 || {
  echo "Schema prep failed." >&2
  exit 1
}

if [ "${DRY}" = "1" ]; then
  echo "Would: git checkout \${PREV_SHA} -- docker-compose.yml caddy/Caddyfile.*"
  echo "Would: tag ubyhost:previous and ubyhost-go:previous to :local and slot tags"
  echo "Would: docker compose up -d --no-build (go rollback slots, remove orphans)"
  echo "Would: caddy reload and curl public /healthz"
  echo "Re-run with ROLLBACK_CONFIRM=yes to execute."
  exit 0
fi

# shellcheck source=go-slot.sh
# shellcheck disable=SC1091
source ./scripts/go-slot.sh

if [ -n "${PREV_SHA}" ]; then
  git -C "${ROOT}" checkout "${PREV_SHA}" -- deploy/lightsail/docker-compose.yml \
    deploy/lightsail/caddy/Caddyfile.acme deploy/lightsail/caddy/Caddyfile.cloudflare || true
fi
if [ -f caddy/Caddyfile.previous ]; then
  cp caddy/Caddyfile.previous caddy/Caddyfile.active
fi
docker image inspect ubyhost:previous >/dev/null 2>&1 && docker tag ubyhost:previous ubyhost:local || true
docker image inspect ubyhost-go:previous >/dev/null 2>&1 && docker tag ubyhost-go:previous ubyhost-go:local || true
go_rollback_slots || true
if docker compose --profile go config --services 2>/dev/null | grep -x ubyhost-go >/dev/null; then
  # shellcheck disable=SC2046
  docker compose up -d --no-build --remove-orphans $(go_non_slot_services)
else
  docker compose up -d --no-build --remove-orphans
fi
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

for _ in $(seq 1 12); do
  if curl -fsS --max-time 10 -o /dev/null "${UBYHOST_PUBLIC_BASE_URL%/}/healthz"; then
    echo "Manual rollback complete; public /healthz answers."
    exit 0
  fi
  sleep 5
done

echo "Public /healthz did not answer after rollback." >&2
exit 1