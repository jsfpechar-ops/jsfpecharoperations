#!/bin/sh
# Production entrypoint: validate config, then start uvicorn.
set -e

if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -z "${UBYHOST_PUBLIC_BASE_URL:-}" ]; then
  echo "WARNING: UBYHOST_PUBLIC_BASE_URL is not set — guest permalinks may be wrong." >&2
fi

if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ "${UBYHOST_UBYPORT_ENV:-mock}" = "mock" ]; then
  echo "WARNING: production deployment with UBYHOST_UBYPORT_ENV=mock — nothing reaches the police." >&2
fi

exec "$@"
