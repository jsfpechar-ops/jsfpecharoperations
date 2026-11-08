#!/bin/sh
# 1022: ship finished WAL files from the spool to S3 with wal-g, oldest first.
# The postgres container (no network) copies each finished file into the spool
# (archive_command); this container has the network. A spool file is deleted
# only after `wal-g wal-push` exited 0 (upload confirmed). A failure keeps it and
# retries; 1023's walg-check.sh alerts when a file stays too long.
set -u
SPOOL="${WALG_SPOOL:-/walspool}"
INTERVAL="${WALG_SHIP_INTERVAL:-15}"

ship_once() {
  if [ -z "${WALG_S3_PREFIX:-}" ]; then
    echo "walg-ship: WALG_S3_PREFIX is not set (is .env.walg missing?); shipping nothing" >&2
    return 1
  fi
  # Only finished WAL names (segments, timeline history, backup labels): skips
  # *.tmp copies in progress and anything else that may appear in the spool.
  for f in $(ls -1 "$SPOOL" 2>/dev/null \
      | grep -E '^[0-9A-F]{24}$|^[0-9A-F]{24}\.[0-9A-F]{8}\.backup$|^[0-9A-F]{8}\.history$' \
      | LC_ALL=C sort); do
    [ -f "$SPOOL/$f" ] || continue
    if wal-g wal-push "$SPOOL/$f"; then
      rm -f "$SPOOL/$f"
    else
      echo "walg-ship: wal-push failed for $f, will retry" >&2
      return 1
    fi
  done
  return 0
}

if [ "${WALG_SHIP_ONCE:-0}" = 1 ]; then
  ship_once
  exit $?
fi
while true; do
  ship_once || true
  sleep "$INTERVAL"
done
