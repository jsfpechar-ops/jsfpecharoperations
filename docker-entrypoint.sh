#!/bin/sh
# Production entrypoint: refuse unsafe UbyPort/deployment combinations, then start.
set -e

if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && [ -z "${UBYHOST_PUBLIC_BASE_URL:-}" ]; then
  echo "WARNING: UBYHOST_PUBLIC_BASE_URL is not set — guest permalinks may be wrong." >&2
fi

# WP32: the web container's uvicorn worker count (Dockerfile CMD).
case "${UBYHOST_WEB_WORKERS:-2}" in
  ''|*[!0-9]*|0|0*)
    echo "ERROR: UBYHOST_WEB_WORKERS must be a whole number from 1 to 16." >&2
    exit 1 ;;
esac
if [ "${UBYHOST_WEB_WORKERS:-2}" -gt 16 ]; then
  echo "ERROR: UBYHOST_WEB_WORKERS must be a whole number from 1 to 16." >&2
  exit 1
fi

python -c "from app.env_guard import apply; apply()"

exec "$@"
