#!/usr/bin/env bash
# Quick production health check.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

docker compose ps

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
  if [ -n "${UBYHOST_PUBLIC_BASE_URL:-}" ]; then
    echo ""
    echo "Public healthz:"
    curl -fsS "${UBYHOST_PUBLIC_BASE_URL%/}/healthz" || true
  fi
fi
