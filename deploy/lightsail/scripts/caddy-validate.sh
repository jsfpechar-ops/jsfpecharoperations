#!/usr/bin/env bash
# 0710: validate caddy/Caddyfile.active with the caddy service from
# docker-compose.yml: the image digest, environment and mounts production runs.
# Usage (from deploy/lightsail): ./scripts/caddy-validate.sh
set -euo pipefail

cd "$(dirname "$0")/.."
docker compose run --rm --no-deps -T \
  caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
