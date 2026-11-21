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

# 1999: lib-docker.sh tells these scripts whether the checkout still has the
# Python app (before 1782) or only the Go service. Sourced when present; without
# it (a trimmed fixture tree) the old Python layout is assumed, exactly as
# before, so nothing here is a new hard dependency.
if [ -f ./scripts/lib-docker.sh ]; then
  # shellcheck disable=SC1091
  source ./scripts/lib-docker.sh
else
  app_is_python() { return 0; }
  app_service() { printf 'ubyhost\n'; }
  app_running_service() { printf 'ubyhost\n'; }
  app_run() { docker compose run --rm --no-deps -T ubyhost "$@"; }
fi

# 1999: 1782 deleted the Python services (`ubyhost`, `worker`) from this compose
# file, so a Go-only stack has neither. Every Python-only step below (the SQL
# checks, the worker wait, the two backfills, the one-off `run ubyhost`) is
# gated on the compose file actually defining them, and the Go service takes
# over the steps that only needed a container with /data.
APP_PYTHON=0
WORKER_PYTHON=0
if app_is_python; then APP_PYTHON=1; fi
if docker compose config --services 2>/dev/null | grep -qx 'worker'; then WORKER_PYTHON=1; fi
GO_ENABLED=0
if docker compose --profile go config --services 2>/dev/null | grep -qx 'ubyhost-go'; then
  GO_ENABLED=1
fi
if [ "${APP_PYTHON}" = "1" ]; then
  APP_PORT=8080
else
  APP_PORT=8081
fi
app_running() { [ -n "$(app_running_service)" ]; }

# PostgreSQL mode: the same test scripts/backup.sh uses.
PG_MODE=0
if [ -n "${UBYHOST_DATABASE_URL:-}" ]; then
  PG_MODE=1
fi

# 1261: which code applies the PostgreSQL goose files. python (the default,
# also when unset or empty) runs App/scripts/pg_schema.py in the new ubyhost
# image; go runs `ubyhost-web migrate apply` in the new ubyhost-go image. Both
# write the same goose_db_version rows. Go applies goose files only: when the
# functions or triggers Python re-creates on every apply differ from the app's,
# Go fails closed and the deploy stops; deploy once with python, then go again.
# Checked here, before anything touches the stack.
# 1999: the default follows the checkout. A Go-only stack has no Python image,
# so `python` is no longer a possible default there; a checkout that still has
# the Python service keeps the old default.
if [ "${APP_PYTHON}" = "1" ]; then
  DEFAULT_SCHEMA_APPLY=python
else
  DEFAULT_SCHEMA_APPLY=go
fi
SCHEMA_APPLY="${UBYHOST_SCHEMA_APPLY:-${DEFAULT_SCHEMA_APPLY}}"
case "${SCHEMA_APPLY}" in
  python)
    if [ "${APP_PYTHON}" != "1" ]; then
      echo "UBYHOST_SCHEMA_APPLY=python, but this compose file has no ubyhost (Python) service." >&2
      echo "Set UBYHOST_SCHEMA_APPLY=go (the Go binary runs the same goose files)." >&2
      exit 1
    fi
    ;;
  go)
    if [ "${PG_MODE}" != "1" ]; then
      echo "UBYHOST_SCHEMA_APPLY=go needs PostgreSQL (UBYHOST_DATABASE_URL); refusing deployment." >&2
      exit 1
    fi
    ;;
  *)
    echo "UBYHOST_SCHEMA_APPLY must be python or go (got '${SCHEMA_APPLY}'); refusing deployment." >&2
    exit 1
    ;;
esac

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
  if docker image inspect ubyhost-go:previous >/dev/null 2>&1; then
    docker tag ubyhost-go:previous ubyhost-go:local
  fi
  # Slot tags, not :local, are what the Go services run. Restoring only :local
  # would leave a failed two-copy on the new image (and Caddy preferring A).
  if [ -f ./scripts/go-slot.sh ]; then
    # shellcheck disable=SC1091
    source ./scripts/go-slot.sh
    go_rollback_slots || true
  fi
  if docker compose --profile go config --services 2>/dev/null | grep -qx 'ubyhost-go'; then
    # shellcheck disable=SC2046
    docker compose up -d --no-build --remove-orphans $(go_non_slot_services) || true
  else
    docker compose up -d --no-build --remove-orphans || true
  fi
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true
  if public_ok; then
    echo "Rollback done: the public site answers again. The new release is NOT live." >&2
  else
    echo "ROLLBACK DID NOT BRING THE SITE BACK. Run: docker compose ps; docker compose logs --tail=50 caddy" >&2
  fi
}

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

# 1999: `app_run` targets the Python service, or the Go one in a Go-only stack.
# In a Go-only stack nothing may mint a key: /data/secret_key is the only copy,
# and a second key there would make every encrypted column unreadable. So an
# unprobeable volume fails closed instead of generating one.
SECRET_KEY_PROBED=0
if [ -z "${UBYHOST_SECRET_KEY:-}" ]; then
  if app_run --entrypoint sh -c 'test -s /data/secret_key' >/dev/null 2>&1; then
    SECRET_KEY_PROBED=1
  fi
fi
if [ -z "${UBYHOST_SECRET_KEY:-}" ] && [ "${SECRET_KEY_PROBED}" = "1" ]; then
  # The volume already holds the key the data was encrypted with, and the app
  # reads it when the variable is empty. Minting a new one here would make
  # every encrypted field (TOTP, UbyPort passwords, document numbers) unreadable.
  echo "==> Using the existing /data/secret_key (UBYHOST_SECRET_KEY is empty in .env)."
elif [ -z "${UBYHOST_SECRET_KEY:-}" ] && [ "${APP_PYTHON}" != "1" ]; then
  echo "UBYHOST_SECRET_KEY is empty in .env and /data/secret_key could not be confirmed" >&2
  echo "(the Go-only stack has no Python image to probe it with)." >&2
  echo "Set UBYHOST_SECRET_KEY in .env to the value stored in /data/secret_key (it is" >&2
  echo "the only copy that decrypts the data), then run this deploy again." >&2
  exit 1
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
# 1999: the query runs through the Python app, so it is skipped in a Go-only
# stack (no Python image to import app.db from).
if [ "${APP_PYTHON}" = "1" ] && docker compose ps --status running --services 2>/dev/null | grep -qx ubyhost; then
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
if app_running; then
  # 1999: whichever app service runs (Python or Go) owns /data, so the checks
  # below ask for the running one instead of naming `ubyhost`.
  APP_EXEC="$(app_running_service)"
  echo "==> Mandatory pre-deploy backup"
  ./scripts/backup.sh
  BACKUP_STAMP="$(docker compose exec -T "${APP_EXEC}" sh -c \
    'ls -1 /data/backups 2>/dev/null | sort -r | sed -n "1p"' | tr -d '\r')"
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
    if ! docker compose exec -T "${APP_EXEC}" sh -c \
      "[ -s '${PG_DUMP}' ] && head -c 21 '${PG_DUMP}' | grep -q 'age-encryption.org/v1'"; then
      echo "PostgreSQL backup ${BACKUP_STAMP} is missing, empty or not an age file - refusing deployment." >&2
      exit 1
    fi
    echo "PostgreSQL backup ${BACKUP_STAMP} is valid."
  elif [ "${APP_PYTHON}" != "1" ]; then
    # 1999: a Go-only stack is PostgreSQL-only, so the SQLite checks below have
    # nothing to look at. UBYHOST_DATABASE_URL is what selects them.
    echo "Backup ${BACKUP_STAMP} is valid (PostgreSQL-only stack)."
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
  # 1999: the row counts compare before/after with the Python app's db helper.
  # A Go-only stack has no Python image, so the comparison is skipped there
  # instead of failing a deploy after the site is already up.
  if [ "${APP_PYTHON}" = "1" ]; then
    for table in "${TABLES[@]}"; do
      BEFORE_COUNTS["${table}"]="$(docker compose exec -T ubyhost python -c \
        "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM ${table}')['n'])")"
    done
    echo "Backup ${BACKUP_STAMP} is valid; live row counts recorded."
  else
    echo "Backup ${BACKUP_STAMP} is valid (row counts are Python-only; skipped)."
  fi
fi

if docker image inspect ubyhost:local >/dev/null 2>&1; then
  docker tag ubyhost:local ubyhost:previous
  echo "Kept the running image as ubyhost:previous for rollback."
fi
if docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  docker tag ubyhost-go:local ubyhost-go:previous
  echo "Kept the running Go image as ubyhost-go:previous for rollback."
fi

# 0422: the GitHub deploy builds the image from the commit CI passed, pushes it
# to GHCR and passes it here as UBYHOST_IMAGE, so the server only pulls. A
# manual deploy without it, or a pull that fails, builds here as before.
# 1171: with UBYHOST_IMAGE set (the GitHub deploy) the server never builds: both
# images are pulled first, and a failed pull stops here, before anything is
# changed, so the old containers keep running. Without it (a manual deploy on
# the server) the images are built here as before.
GO_IMAGE_PULLED=0
if [ -n "${UBYHOST_IMAGE:-}" ]; then
  # Pull everything first. Nothing is tagged or removed until both pulls succeed.
  if ! docker pull "${UBYHOST_IMAGE}"; then
    echo "ERROR: could not pull ${UBYHOST_IMAGE}. Nothing was changed; the old containers keep running. Check that the GHCR package is public (docs/LIGHTSAIL.md, Deploy from GitHub Actions)." >&2
    exit 1
  fi
  if [ -n "${UBYHOST_GO_IMAGE:-}" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
    if ! docker pull "${UBYHOST_GO_IMAGE}"; then
      echo "ERROR: could not pull ${UBYHOST_GO_IMAGE}. Nothing was changed; the old containers keep running. Check that the GHCR package is public (docs/LIGHTSAIL.md, Deploy from GitHub Actions)." >&2
      exit 1
    fi
    GO_IMAGE_PULLED=1
  fi
  echo "==> Using CI-built image ${UBYHOST_IMAGE}"
  docker tag "${UBYHOST_IMAGE}" ubyhost:local
  # Drop the extra tag so old commit images do not pile up on the disk.
  docker image rm "${UBYHOST_IMAGE}" >/dev/null
  if [ "${GO_IMAGE_PULLED}" = "1" ]; then
    echo "==> Using CI-built Go image ${UBYHOST_GO_IMAGE}"
    docker tag "${UBYHOST_GO_IMAGE}" ubyhost-go:local
    docker image rm "${UBYHOST_GO_IMAGE}" >/dev/null
  fi
else
  echo "==> Building image"
  docker compose build --pull
fi

if docker compose --profile go config --services | grep -qx 'ubyhost-go'; then
  # shellcheck disable=SC1091
  source ./scripts/go-slot.sh
  # A compose build tags slot-a, not :local. A CI pull already put the new
  # image on :local; copying an old slot-a over it would roll the deploy back.
  if [ "${GO_IMAGE_PULLED}" != "1" ]; then
    go_alias_built_to_local
  fi
  go_ensure_slot_images
fi

if [ "${PG_MODE}" = "1" ]; then
  # PostgreSQL: apply pending goose files with the new image, before the stack
  # starts. A failure exits here, before `up` touches the running stack.
  if [ "${SCHEMA_APPLY}" = "go" ]; then
    # 1261: build the new Go image first, so the apply runs the merged code.
    # --profile go: the service is profile-gated and may not be enabled.
    # 1263: a Go image pulled above is that code already; never rebuild it.
    if [ "${GO_IMAGE_PULLED}" = "1" ]; then
      echo "==> Using the pulled Go image for the schema apply"
    else
      echo "==> Building the Go image for the schema apply"
      if ! docker compose --profile go build ubyhost-go; then
        echo "Go image build failed." >&2
        exit 1
      fi
      go_alias_built_to_local
      go_ensure_slot_images
    fi
    echo "==> Applying PostgreSQL goose migrations (new Go image)"
    if ! docker compose --profile go run --rm --no-deps -T ubyhost-go \
      migrate apply --expect-database ubyhost; then
      echo "Goose apply failed." >&2
      exit 1
    fi
  else
    echo "==> Applying PostgreSQL goose migrations (new image)"
    if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
      scripts/pg_schema.py apply --expect-database ubyhost; then
      echo "Goose apply failed." >&2
      exit 1
    fi
  fi
  echo "Goose migrations applied."
elif [ -n "${BACKUP_STAMP}" ] && [ "${APP_PYTHON}" = "1" ]; then
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

if [ "${GO_IMAGE_PULLED}" != "1" ] && [ "${SCHEMA_APPLY}" != "go" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
  # 1171: build on the server only when no Go image was pulled above (manual
  # deploy, or an old workflow run without UBYHOST_GO_IMAGE). A pulled Go image is never rebuilt.
  # Rebuild the local Go image so a merged change reaches production.
  # Runs before "up", so a failed build leaves the running stack untouched.
  # With UBYHOST_SCHEMA_APPLY=go it was built (or pulled) before the schema apply.
  if ! docker compose build ubyhost-go; then
    echo "Go image build failed." >&2
    exit 1
  fi
  go_alias_built_to_local
  go_ensure_slot_images
fi

echo "==> Starting stack"
docker compose pull caddy
if docker compose --profile go config --services | grep -qx 'ubyhost-go'; then
  # shellcheck disable=SC1091
  source ./scripts/go-slot.sh
  go_ensure_slot_images
  # goose apply retagged slot-a to :local. Put the live tag back on the
  # running image, then `up` every service except the Go slots so the live
  # copy is not recreated and a stopped idle A cannot take Caddy traffic.
  go_pin_live_slot_image
  # shellcheck disable=SC2046
  docker compose up -d --remove-orphans $(go_non_slot_services)
else
  docker compose up -d --remove-orphans
fi

# 1830: two-copy deploy of ubyhost-go. The idle slot gets the new image and
# must be healthy before the old slot stops. Migrations are add-only, so the
# old copy keeps working on the new schema (docs/context/rules.md).
if docker compose --profile go config --services | grep -qx 'ubyhost-go' \
  && docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source ./scripts/go-slot.sh
  LIVE_SLOT="$(go_live_slot)"
  NEW_SLOT="$(go_idle_slot)"
  # compose up starts every go-profile service, including a stopped idle slot.
  # Caddy lb_policy first prefers ubyhost-go (slot A), so a restarted A would
  # take production traffic while B is live. Put the idle slot down first.
  docker compose --profile go stop "$(go_svc "${NEW_SLOT}")" || true
  echo "==> Starting ubyhost-go slot ${NEW_SLOT} beside slot ${LIVE_SLOT}"
  docker tag ubyhost-go:local "ubyhost-go:slot-${NEW_SLOT}"
  docker compose --profile go up -d --no-build --no-deps --force-recreate "$(go_svc "${NEW_SLOT}")"
  if ! go_wait_healthy "${NEW_SLOT}" 60; then
    echo "New ubyhost-go copy (slot ${NEW_SLOT}) never became healthy; the old copy keeps serving." >&2
    docker compose --profile go stop "$(go_svc "${NEW_SLOT}")" || true
    rollback
    exit 1
  fi
  echo "${NEW_SLOT}" > .go-slot
  sleep 3 # one Caddy health interval, so Caddy sees the new copy before the old one stops
  docker compose --profile go stop "$(go_svc "${LIVE_SLOT}")" || true
  echo "ubyhost-go now runs on slot ${NEW_SLOT}."
fi

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
# 1999: the Python app answers on 8080 and is probed with python3 (its image
# has no wget); the Go image is alpine with wget and answers on 8081.
HEALTH_SVC="$(app_running_service)"
if [ -z "${HEALTH_SVC}" ]; then
  # Nothing of the old stack is up yet on a first Go deploy: probe the service
  # name the compose file defines.
  HEALTH_SVC="$(app_service)"
fi
for _ in $(seq 1 30); do
  if [ "${APP_PYTHON}" = "1" ]; then
    docker compose exec -T "${HEALTH_SVC}" python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${APP_PORT}/healthz', timeout=3)" \
      >/dev/null 2>&1 && HEALTHY=1 && break
  else
    docker compose exec -T "${HEALTH_SVC}" wget -qO- "http://127.0.0.1:${APP_PORT}/healthz" \
      >/dev/null 2>&1 && HEALTHY=1 && break
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
# 1999: a Go-only stack has no `worker`; the Go service runs the scheduler in
# process (UBYHOST_ENABLE_SCHEDULER), so this wait is Python-only.
if [ "${WORKER_PYTHON}" = "1" ]; then
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
else
  echo "==> No Python worker in this stack; the Go service runs the scheduler"
fi

echo ""
docker compose ps
echo ""
echo "Health (internal):"
if [ "${APP_PYTHON}" = "1" ]; then
  docker compose exec -T "$(app_running_service)" python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:${APP_PORT}/healthz').read().decode())"
else
  docker compose exec -T "${HEALTH_SVC}" wget -qO- "http://127.0.0.1:${APP_PORT}/healthz" || \
    echo "not healthy (check docker compose logs --tail=50 ${HEALTH_SVC})"
fi

# Go port (G1b): report only. This block never exits non-zero.
# 1999: in a Go-only stack the Go service above already IS the app.
if [ "${APP_PYTHON}" = "1" ] && docker compose ps --status running --services | grep -qx ubyhost-go; then
  echo "Go service (internal, no traffic yet):"
  docker compose exec -T ubyhost-go wget -qO- http://127.0.0.1:8081/healthz || echo "not healthy (does not affect the app)"
elif [ "${APP_PYTHON}" = "1" ]; then
  echo "Go service: not enabled (COMPOSE_PROFILES has no go)"
fi

# 1999: both backfills below are Python scripts (App/scripts) that only exist in
# a checkout which still has the `ubyhost` service. They are skipped in a
# Go-only stack; the Go app reads the same rows and does not need them.
if [ "${APP_PYTHON}" != "1" ]; then
  echo "==> Skipping the Python backfills (legal acceptance, document numbers):"
  echo "    this stack has no ubyhost service. Run them once from a checkout that has it."
fi

# BE-1: turn legacy login acceptance lines into legal_acceptance rows. The
# script is idempotent and prints a count only. A failure aborts the deploy
# loudly rather than leaving acceptance evidence half-migrated.
if [ "${APP_PYTHON}" = "1" ]; then
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
fi
if [ -n "${BACKUP_STAMP}" ]; then
  echo ""
  echo "Post-deploy database integrity and row-count checks:"
  # 1999: Python-only (sqlite integrity_check and the db helper). The Go stack
  # is PostgreSQL-only and its health is asserted above.
  if [ "${PG_MODE}" != "1" ]; then
    LIVE_OK="$(docker compose exec -T ubyhost sqlite3 /data/ubyhost.db "PRAGMA integrity_check;")"
    if [ "${LIVE_OK}" != "ok" ]; then
      echo "Live database integrity check failed: ${LIVE_OK}" >&2
      exit 1
    fi
  fi
  for table in "${TABLES[@]}"; do
    [ "${APP_PYTHON}" = "1" ] || break
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

# 0962: success is final. Drop dangling images (the old ubyhost:local of each
# deploy) and all build cache of this deploy. Never -a: it would delete
# ubyhost:previous and digest-pinned service images. A failed prune is ignored.
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f >/dev/null 2>&1 || true
echo "Pruned dangling Docker images and all build cache."
