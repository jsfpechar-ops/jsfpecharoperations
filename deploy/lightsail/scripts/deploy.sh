#!/usr/bin/env bash
# Build and start (or update) the UbyHost Lightsail stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example and set your domain, email, and passwords." >&2
  exit 1
fi
chmod 600 .env

# shellcheck disable=SC1091
set -a
source .env
set +a

for var in UBYHOST_DOMAIN ACME_EMAIL UBYHOST_PUBLIC_BASE_URL UBYHOST_ADMIN_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    echo "Required variable ${var} is empty in .env" >&2
    exit 1
  fi
done

if [ "${UBYHOST_PUBLIC_BASE_URL#https://}" = "${UBYHOST_PUBLIC_BASE_URL}" ]; then
  echo "WARNING: UBYHOST_PUBLIC_BASE_URL should use https:// in production." >&2
fi

if [ "${CLOUDFLARE_PROXY:-0}" = "1" ]; then
  echo "==> Cloudflare proxy mode (origin certificate)"
  for cert in caddy/certs/origin.pem caddy/certs/origin-key.pem; do
    if [ ! -f "${cert}" ]; then
      echo "Missing ${cert} — see docs/CLOUDFLARE.md and caddy/certs/README.md" >&2
      exit 1
    fi
  done
  cp caddy/Caddyfile.cloudflare caddy/Caddyfile.active
else
  echo "==> Direct TLS mode (Let's Encrypt via Caddy)"
  cp caddy/Caddyfile.acme caddy/Caddyfile.active
fi

if [ -z "${UBYHOST_SECRET_KEY:-}" ]; then
  echo "Generating UBYHOST_SECRET_KEY in .env"
  KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
  if grep -q '^UBYHOST_SECRET_KEY=' .env; then
    sed -i "s|^UBYHOST_SECRET_KEY=.*|UBYHOST_SECRET_KEY=${KEY}|" .env
  else
    echo "UBYHOST_SECRET_KEY=${KEY}" >> .env
  fi
  set -a
  source .env
  set +a
fi

chmod +x scripts/*.sh
./scripts/preflight.sh

BACKUP_STAMP=""
TABLES=(user_account legal_entity apartment reservation guest submission)
declare -A BEFORE_COUNTS
if docker compose ps --status running --services 2>/dev/null | grep -qx ubyhost; then
  echo "==> Mandatory pre-deploy backup"
  ./scripts/backup.sh
  BACKUP_STAMP="$(docker compose exec -T ubyhost sh -c \
    'ls -1 /data/backups 2>/dev/null | sort -r | sed -n "1p"')"
  if [ -z "${BACKUP_STAMP}" ]; then
    echo "No backup stamp found after backup — refusing deployment." >&2
    exit 1
  fi
  # The production snapshot is age-encrypted and cannot be opened here (the
  # identity is kept off the server). Check that it exists and really is an
  # age file (or, outside production, a non-empty plaintext copy), then
  # integrity-check a fresh copy of the live database.
  if ! docker compose exec -T ubyhost sh -c \
    "f=/data/backups/${BACKUP_STAMP}/ubyhost-backup.tar.age; p=/data/backups/${BACKUP_STAMP}/ubyhost.db; if [ -s \"\$f\" ]; then head -c 21 \"\$f\" | grep -q 'age-encryption.org/v1'; else [ -s \"\$p\" ]; fi"; then
    echo "Backup ${BACKUP_STAMP} is missing, empty or not an age file - refusing deployment." >&2
    exit 1
  fi
  PREFLIGHT_DB="/data/.preflight-${BACKUP_STAMP}.db"
  docker compose exec -T ubyhost sqlite3 /data/ubyhost.db ".backup '${PREFLIGHT_DB}'"
  BACKUP_OK="$(docker compose exec -T ubyhost sh -c \
    "[ -s '${PREFLIGHT_DB}' ] && sqlite3 '${PREFLIGHT_DB}' 'PRAGMA integrity_check;'")" || BACKUP_OK="missing"
  if [ "${BACKUP_OK}" != "ok" ]; then
    echo "Live database copy failed its integrity check: ${BACKUP_OK}" >&2
    docker compose exec -T ubyhost rm -f "${PREFLIGHT_DB}"
    exit 1
  fi
  for table in "${TABLES[@]}"; do
    BEFORE_COUNTS["${table}"]="$(docker compose exec -T ubyhost sqlite3 \
      /data/ubyhost.db "SELECT COUNT(*) FROM ${table};")"
  done
  echo "Backup ${BACKUP_STAMP} is valid; live row counts recorded."
fi

echo "==> Building image"
docker compose build --pull

if [ -n "${BACKUP_STAMP}" ]; then
  echo "==> Dry-running database migration against a copy of the live database"
  if ! docker compose run --rm --no-deps \
    -e "UBYHOST_DB=${PREFLIGHT_DB}" \
    --entrypoint python ubyhost -c \
    "from app import db; db.init_db(); assert db.query_one('PRAGMA integrity_check')[0] == 'ok'; required={'guest_message','passport_photo_policy'}; apartment={r['name'] for r in db.query('PRAGMA table_info(apartment)')}; reservation={r['name'] for r in db.query('PRAGMA table_info(reservation)')}; claim={r['name'] for r in db.query('PRAGMA table_info(reservation_claim)')}; assert required <= apartment; assert 'registration_completed_at' in reservation; assert 'guest_access_reopened_at' in claim"; then
    docker compose exec -T ubyhost rm -f "${PREFLIGHT_DB}"
    echo "Migration dry-run failed." >&2
    exit 1
  fi
  docker compose exec -T ubyhost rm -f "${PREFLIGHT_DB}"
  echo "Migration dry-run passed."
fi

echo "==> Starting stack"
docker compose pull caddy
docker compose up -d --remove-orphans

# Reload Caddy unconditionally, every deploy.
#
# The Caddyfile is bind-mounted into the container, and the compose service
# sets no command: override, so Caddy runs the image default
# `caddy run --config /etc/caddy/Caddyfile` — which does NOT watch the file.
# Caddy documents --watch as development-only, so we must not rely on it.
# An unchanged service definition also means `up -d` never recreates the
# caddy container, so a config change alone would sit inert on disk forever.
# A change-detection check would be worse than useless here: the Caddyfile is
# copied into place above, before this point, so on exactly the deploy that
# needs a reload the file would already compare equal.
#
# `caddy reload` is a graceful, zero-downtime config swap over the admin API
# (localhost:2019 inside the container, enabled by default) — unlike
# `docker compose restart caddy`, it does not drop live connections. Caddy
# validates the new config before applying it and keeps the running config if
# validation fails, so aborting here on a bad config is safe.
echo "==> Reloading Caddy"
if ! docker compose exec -T caddy caddy reload \
  --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "Caddy reload failed — the deployed Caddyfile is NOT active." >&2
  exit 1
fi

echo "==> Waiting for health check"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo ""
docker compose ps
echo ""
echo "Health (internal):"
docker compose exec -T ubyhost python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz').read().decode())"

# BE-1: turn legacy login acceptance lines into legal_acceptance rows. The
# script is idempotent and prints a count only. A failure aborts the deploy
# loudly rather than leaving acceptance evidence half-migrated.
echo "==> Backfilling legal acceptance evidence"
if ! docker compose exec -T ubyhost python scripts/backfill_legal_acceptance.py; then
  echo "Legal acceptance backfill failed." >&2
  exit 1
fi

# BE-11: encrypt any travel-document numbers still sitting in the plaintext
# columns. Idempotent; logs a count only. The --check before it is
# informational, the one after it is the assertion the deploy must pass.
echo "==> Document-number backfill (counts only)"
docker compose exec -T ubyhost python scripts/migrate_encrypt_doc_fields.py --check || true
if ! docker compose exec -T ubyhost python scripts/migrate_encrypt_doc_fields.py; then
  echo "Document-number backfill failed." >&2
  exit 1
fi
if ! docker compose exec -T ubyhost python scripts/migrate_encrypt_doc_fields.py --check; then
  echo "Plaintext document numbers remain after the backfill." >&2
  exit 1
fi
if [ -n "${BACKUP_STAMP}" ]; then
  echo ""
  echo "Post-deploy database integrity and row-count checks:"
  LIVE_OK="$(docker compose exec -T ubyhost sqlite3 /data/ubyhost.db "PRAGMA integrity_check;")"
  if [ "${LIVE_OK}" != "ok" ]; then
    echo "Live database integrity check failed: ${LIVE_OK}" >&2
    exit 1
  fi
  for table in "${TABLES[@]}"; do
    after="$(docker compose exec -T ubyhost sqlite3 /data/ubyhost.db \
      "SELECT COUNT(*) FROM ${table};")"
    if [ "${after}" -lt "${BEFORE_COUNTS[${table}]}" ]; then
      echo "${table} row count fell from ${BEFORE_COUNTS[${table}]} to ${after}." >&2
      exit 1
    fi
    echo "  ${table}: ${BEFORE_COUNTS[${table}]} -> ${after}"
  done
fi
echo ""
echo "Public URL: ${UBYHOST_PUBLIC_BASE_URL}"
if [ "${CLOUDFLARE_PROXY:-0}" = "1" ]; then
  echo "Cloudflare: ensure DNS is proxied (orange cloud) and SSL/TLS is Full (strict)."
fi
echo "Run ./scripts/logs.sh to tail logs."
if [ "${SKIP_PUBLIC_SMOKE:-0}" != "1" ]; then
  echo ""
  echo "==> Public smoke (set SKIP_PUBLIC_SMOKE=1 to skip)"
  if ! ./scripts/smoke-remote.sh; then
    echo "WARNING: public smoke failed (DNS/TLS/Cloudflare?). Internal healthz is above." >&2
  fi
fi
