#!/usr/bin/env bash
# Follow application and proxy logs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

SERVICE="${1:-}"
if [ -n "${SERVICE}" ]; then
  docker compose logs -f --tail=100 "${SERVICE}"
else
  docker compose logs -f --tail=100
fi
