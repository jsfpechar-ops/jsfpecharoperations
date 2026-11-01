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

# PostgreSQL mode: the same test scripts/backup.sh uses.
PG_MODE=0
if [ -n "${UBYHOST_DATABASE_URL:-}" ]; then
  PG_MODE=1
fi

# 0710: rollback target. .deployed-sha is written only when a deploy finished;
# before the first one, ORIG_HEAD is the commit the workflow reset away from.
PREV_SHA="$(cat .deployed-sha 2>/dev/null || git rev-parse -q --verify ORIG_HEAD 2>/dev/null || true)"

# 0710: the site as visitors reach it (Cloudflare, Caddy, app). About 60 s.
public_ok() {
  for _ in $(seq 1 12); do
    if curl -fsS --max-time 10 -o /dev/null "${UBYHOST_PUBLIC_BASE_URL%/}/healthz"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# 0710: put back the last good compose file, Caddyfile and app image. Database
# migrations are not undone (goose files are additive). The working tree stays
# modified until the next deploy's git reset.
rollback() {
  echo "==> Rolling back to ${PREV_SHA:-the previous image and Caddyfile}" >&2
  if [ -n "${PREV_SHA}" ]; then
    git checkout "${PREV_SHA}" -- docker-compose.yml caddy/Caddyfile.acme caddy/Caddyfile.cloudflare || true
  fi
  if [ -f caddy/Caddyfile.previous ]; then
    cp caddy/Caddyfile.previous caddy/Caddyfile.active
  fi
  if docker image inspect ubyhost:previous >/dev/null 2>&1; then
    docker tag ubyhost:previous ubyhost:local
  fi
  docker compose up -d --no-build --remove-orphans || true
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true
  if public_ok; then
    echo "Rollback done: the public site answers again. The new release is NOT live." >&2
  else
    echo "ROLLBACK DID NOT BRING THE SITE BACK. Run: docker compose ps; docker compose logs --tail=50 caddy" >&2
  fi
}

# shellcheck disable=SC1091
source "$(dirname "$0")/litestream_env.sh"
if [ "${litestream_enabled}" = "1" ]; then
  case ",${COMPOSE_PROFILES:-}," in
    *,litestream,*) ;;
    *)
      export COMPOSE_PROFILES="${COMPOSE_PROFILES:+$COMPOSE_PROFILES,}litestream"
      ;;
  esac
fi

for var in UBYHOST_DOMAIN ACME_EMAIL UBYHOST_PUBLIC_BASE_URL; do
  if [ -z "${!var:-}" ]; then
    echo "Required variable ${var} is empty in .env" >&2
    exit 1
  fi
done

if [ "${UBYHOST_PUBLIC_BASE_URL#https://}" = "${UBYHOST_PUBLIC_BASE_URL}" ]; then
  echo "WARNING: UBYHOST_PUBLIC_BASE_URL should use https:// in production." >&2
fi

# 0710: keep the running Caddyfile for rollback.
if [ -f caddy/Caddyfile.active ]; then
  cp caddy/Caddyfile.active caddy/Caddyfile.previous
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

# 0710: a recreated Caddy container does not keep its old config, so a broken
# file takes the site down. Test it with the production caddy service before
# anything restarts.
echo "==> Validating the Caddyfile"
if ! bash ./scripts/caddy-validate.sh; then
  if [ -f caddy/Caddyfile.previous ]; then
    cp caddy/Caddyfile.previous caddy/Caddyfile.active
  fi
  echo "The new Caddyfile is invalid; nothing was restarted." >&2
  exit 1
fi

if [ -z "${UBYHOST_SECRET_KEY:-}" ] && docker compose run --rm --no-deps -T --entrypoint sh ubyhost \
     -c 'test -s /data/secret_key' >/dev/null 2>&1; then
  # The volume already holds the key the data was encrypted with, and the app
  # reads it when the variable is empty. Minting a new one here would make
  # every encrypted field (TOTP, UbyPort passwords, document numbers) unreadable.
  echo "==> Using the existing /data/secret_key (UBYHOST_SECRET_KEY is empty in .env)."
elif [ -z "${UBYHOST_SECRET_KEY:-}" ]; then
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

# Task 0003: hosts log in with their login e-mail only. An active account
# without one would be locked out by this release, so refuse to deploy until
# every active account has one (admin > Users shows them).
# UBYHOST_ALLOW_MISSING_EMAIL=1 deploys anyway.
if docker compose ps --status running --services 2>/dev/null | grep -qx ubyhost; then
  MISSING_EMAIL="$(docker compose exec -T ubyhost python -c \
    "from app import db; print(db.query_one(\"SELECT COUNT(*) AS n FROM user_account WHERE active = 1 AND (email IS NULL OR email = '')\")['n'])" \
    2>/dev/null || echo "?")"
  if [ "${MISSING_EMAIL}" != "0" ] && [ "${UBYHOST_ALLOW_MISSING_EMAIL:-0}" != "1" ]; then
    echo "Active accounts without a login e-mail: ${MISSING_EMAIL}. Add one to each in admin > Users, then deploy again." >&2
    exit 1
  fi
fi

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
  if [ "${PG_MODE}" = "1" ]; then
    # PostgreSQL: backup.sh writes an age-encrypted pg_dump. The SQLite copy
    # and integrity check below do not apply to it.
    PG_DUMP="/data/backups/${BACKUP_STAMP}/ubyhost-pg.dump.age"
    if ! docker compose exec -T ubyhost sh -c \
      "[ -s '${PG_DUMP}' ] && head -c 21 '${PG_DUMP}' | grep -q 'age-encryption.org/v1'"; then
      echo "PostgreSQL backup ${BACKUP_STAMP} is missing, empty or not an age file - refusing deployment." >&2
      exit 1
    fi
    echo "PostgreSQL backup ${BACKUP_STAMP} is valid."
  else
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
  fi
  for table in "${TABLES[@]}"; do
    BEFORE_COUNTS["${table}"]="$(docker compose exec -T ubyhost python -c \
      "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM ${table}')['n'])")"
  done
  echo "Backup ${BACKUP_STAMP} is valid; live row counts recorded."
fi

if docker image inspect ubyhost:local >/dev/null 2>&1; then
  docker tag ubyhost:local ubyhost:previous
  echo "Kept the running image as ubyhost:previous for rollback."
fi

# 0422: the GitHub deploy builds the image from the commit CI passed, pushes it
# to GHCR and passes it here as UBYHOST_IMAGE, so the server only pulls. A
# manual deploy without it, or a pull that fails, builds here as before.
if [ -n "${UBYHOST_IMAGE:-}" ] && docker pull "${UBYHOST_IMAGE}"; then
  echo "==> Using CI-built image ${UBYHOST_IMAGE}"
  docker tag "${UBYHOST_IMAGE}" ubyhost:local
  # Drop the extra tag so old commit images do not pile up on the disk.
  docker image rm "${UBYHOST_IMAGE}" >/dev/null
else
  if [ -n "${UBYHOST_IMAGE:-}" ]; then
    echo "WARNING: could not pull ${UBYHOST_IMAGE}; building on the server instead." >&2
  fi
  echo "==> Building image"
  docker compose build --pull
fi

if [ "${PG_MODE}" = "1" ]; then
  # PostgreSQL: apply pending goose files with the new image, before the stack
  # starts. A failure exits here, before `up` touches the running stack.
  echo "==> Applying PostgreSQL goose migrations (new image)"
  if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
    scripts/pg_schema.py apply --expect-database ubyhost; then
    echo "Goose apply failed." >&2
    exit 1
  fi
  echo "Goose migrations applied."
elif [ -n "${BACKUP_STAMP}" ]; then
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
# validates the new config before applying it, but a container that `up -d`
# recreated has no running config to keep, so a failure here rolls back.
echo "==> Reloading Caddy"
if ! docker compose exec -T caddy caddy reload \
  --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "Caddy reload failed." >&2
  rollback
  exit 1
fi

echo "==> Waiting for health check"
HEALTHY=0
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 2
done
if [ "${HEALTHY}" != "1" ]; then
  echo "New release never became healthy." >&2
  rollback
  exit 1
fi

echo "==> Checking the public site (Cloudflare, Caddy, app)"
if ! public_ok; then
  echo "The public site does not answer after the restart." >&2
  rollback
  exit 1
fi

# WP06: the scheduler runs only in the worker container. Wait until it reports
# alive (it touches /data/worker.alive while its scheduler runs) and confirm
# the web container did not start one.
echo "==> Waiting for the background worker"
WORKER_ALIVE=0
for _ in $(seq 1 30); do
  if docker compose exec -T worker python -c \
    "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime('/data/worker.alive') < 120 else 1)" \
    >/dev/null 2>&1; then
    WORKER_ALIVE=1
    break
  fi
  sleep 2
done
if [ "${WORKER_ALIVE}" != "1" ]; then
  echo "The worker never started its scheduler. Logs:" >&2
  docker compose logs --tail=50 worker >&2 || true
  exit 1
fi
if docker compose logs ubyhost 2>/dev/null | grep -q "scheduler started"; then
  echo "The web container started a scheduler; it must run only in the worker (UBYHOST_ROLE)." >&2
  exit 1
fi
echo "Worker is running the scheduler (exactly one: the scheduler lock is held)."

echo ""
docker compose ps
echo ""
echo "Health (internal):"
docker compose exec -T ubyhost python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz').read().decode())"

# Go port (G1b): report only. This block never exits non-zero.
if docker compose ps --status running --services | grep -qx ubyhost-go; then
  echo "Go service (internal, no traffic yet):"
  docker compose exec -T ubyhost-go wget -qO- http://127.0.0.1:8081/healthz || echo "not healthy (does not affect the app)"
else
  echo "Go service: not enabled (COMPOSE_PROFILES has no go)"
fi

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
  if [ "${PG_MODE}" != "1" ]; then
    LIVE_OK="$(docker compose exec -T ubyhost sqlite3 /data/ubyhost.db "PRAGMA integrity_check;")"
    if [ "${LIVE_OK}" != "ok" ]; then
      echo "Live database integrity check failed: ${LIVE_OK}" >&2
      exit 1
    fi
  fi
  for table in "${TABLES[@]}"; do
    after="$(docker compose exec -T ubyhost python -c \
      "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM ${table}')['n'])")"
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
    echo "ERROR: public smoke failed (DNS/TLS/Cloudflare?). Internal healthz passed, the new version is running; check the public site now." >&2
    exit 1
  fi
fi

# 0710: this commit is now the rollback target.
git rev-parse HEAD > .deployed-sha
