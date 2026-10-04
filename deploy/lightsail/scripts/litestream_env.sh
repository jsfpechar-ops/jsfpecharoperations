#!/usr/bin/env bash
# Resolve whether the Litestream compose profile should run. Sourced by
# preflight.sh and deploy.sh after .env is loaded.
# Sets: litestream_enabled (0 or 1), litestream_auto_disabled (0 or 1).

litestream_enabled=1
litestream_auto_disabled=0

case "${UBYHOST_LITESTREAM_ENABLED:-}" in
  0|false|no|FALSE|NO)
    litestream_enabled=0
    ;;
  1|true|yes|TRUE|YES)
    litestream_enabled=1
    ;;
  "")
    if [ -z "${LITESTREAM_S3_BUCKET:-}" ] \
      && [ -z "${LITESTREAM_ACCESS_KEY_ID:-}" ] \
      && [ -z "${LITESTREAM_SECRET_ACCESS_KEY:-}" ]; then
      litestream_enabled=0
      litestream_auto_disabled=1
    fi
    ;;
  *)
    echo "ERROR: UBYHOST_LITESTREAM_ENABLED must be 0 or 1 (got ${UBYHOST_LITESTREAM_ENABLED})" >&2
    exit 1
    ;;
esac
