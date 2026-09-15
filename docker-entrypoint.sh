#!/bin/sh
# Production entrypoint: refuse unsafe UbyPort/deployment combinations, then start.
set -e

if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -z "${UBYHOST_PUBLIC_BASE_URL:-}" ]; then
  echo "WARNING: UBYHOST_PUBLIC_BASE_URL is not set — guest permalinks may be wrong." >&2
fi

python -c "from app.env_guard import apply; apply()"

exec "$@"
