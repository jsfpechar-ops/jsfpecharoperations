#!/usr/bin/env bash
# Usage (repo root):  source scripts/e2e/parity_env.sh
export PGBIN=/usr/lib/postgresql/16/bin
export PARITY_PG_DIR=/var/tmp/parity-pg
export UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433
export UBYHOST_E2E_PSQL=$PGBIN/psql
export PARITY_OUT=${PARITY_OUT:-/var/tmp/parity-visual}
export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
export PATH=/usr/local/go/bin:$PATH
mkdir -p /var/tmp/parity_data "$PARITY_OUT"
if ! $PGBIN/pg_isready -q -h 127.0.0.1 -p 5433; then
  if [ ! -d "$PARITY_PG_DIR/data" ]; then
    mkdir -p "$PARITY_PG_DIR" && chown postgres "$PARITY_PG_DIR"
    runuser -u postgres -- $PGBIN/initdb -D "$PARITY_PG_DIR/data" -A trust -U postgres >/dev/null
  fi
  runuser -u postgres -- $PGBIN/pg_ctl -D "$PARITY_PG_DIR/data" -w -l "$PARITY_PG_DIR/pg.log" \
    -o "-p 5433 -c listen_addresses=127.0.0.1 -c fsync=off -c unix_socket_directories=$PARITY_PG_DIR" start >/dev/null
fi
[ -x App/.venv/bin/python ] || python3 -m venv App/.venv
if ! App/.venv/bin/python -c "import playwright, uvicorn, psycopg, httpx" 2>/dev/null; then
  App/.venv/bin/pip install -q -r App/requirements.lock -r App/requirements-dev.txt
  App/.venv/bin/pip install -q playwright==1.63.0
fi
