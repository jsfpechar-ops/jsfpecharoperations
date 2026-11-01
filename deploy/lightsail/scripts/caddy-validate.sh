#!/usr/bin/env bash
# 0710: validate a Caddyfile with the caddy service from docker-compose.yml:
# the image digest, environment and certificate mounts production runs.
# Usage (from deploy/lightsail): ./scripts/caddy-validate.sh caddy/Caddyfile.active
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
FILE="${1:?usage: caddy-validate.sh CADDYFILE}"
docker compose run --rm --no-deps -T \
  -v "${ROOT}/${FILE}:/etc/caddy/Caddyfile.check:ro" \
  caddy caddy validate --config /etc/caddy/Caddyfile.check --adapter caddyfile
