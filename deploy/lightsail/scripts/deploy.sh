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

case "${UBYHOST_SCHEDULER:-}" in
  go|Go|GO) ;;
  *)
    echo "ERROR: UBYHOST_SCHEDULER must be go before deploy (got '${UBYHOST_SCHEDULER:-unset}')." >&2
    echo "Set UBYHOST_SCHEDULER=go in deploy/lightsail/.env; the Python worker is gone after this release." >&2
    exit 1
    ;;
esac

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
SCHEMA_APPLY="${UBYHOST_SCHEMA_APPLY:-go}"
# go-only compose cannot apply schema with Python.
if [ "${SCHEMA_APPLY}" = "python" ] && ! docker compose config --services 2>/dev/null | grep -qx ubyhost; then
  echo "ERROR: UBYHOST_SCHEMA_APPLY=python with no ubyhost service in compose (Go-only stack)." >&2
  exit 1
fi

case "${SCHEMA_APPLY}" in
  python) ;;
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

# shellcheck source=lib-docker.sh
# shellcheck disable=SC1091
source ./scripts/lib-docker.sh

compose_has_go_service() {
  docker compose --profile go config --services 2>/dev/null | grep -qx ubyhost-go
}

# The two-copy deploy starts the *idle* slot and then stops the old one, so the
# running Go container is not always `ubyhost-go` (slot a): after a deploy it is
# `ubyhost-go-b`. Exec into whichever slot is actually up — otherwise every
# `go_exec` probe (the health wait, the scheduler check, the internal health
# print) talks to a stopped container and fails a deploy that is fine.
go_exec() {
  local svc=""
  if docker compose --profile go ps -q --status running ubyhost-go 2>/dev/null | grep -q .; then
    svc=ubyhost-go
  elif docker compose --profile go ps -q --status running ubyhost-go-b 2>/dev/null | grep -q .; then
    svc=ubyhost-go-b
  else
    echo "ERROR: ubyhost-go is not running (checked ubyhost-go and ubyhost-go-b)." >&2
    return 1
  fi
  docker compose --profile go exec -T "${svc}" "$@"
}

running_python_app() {
  docker compose config --services 2>/dev/null | grep -qx ubyhost     && docker compose ps -q --status running ubyhost 2>/dev/null | grep -q .
}

app_data_exec() {
  ubyhost_app_exec sh -c "$1"
}

pg_count() {
  docker compose exec -T postgres psql -U ubyhost -d ubyhost -tAc "SELECT COUNT(*) FROM $1" | tr -d '[:space:]'
}

# 0710: rollback target. .deployed-sha is written only when a deploy finished;
# before the first one, ORIG_HEAD is the commit the workflow reset away from.
PREV_SHA="$(cat .deployed-sha 2>/dev/null || git rev-parse -q --verify ORIG_HEAD 2>/dev/null || true)"

# 2044: after the Go slot switch the site runs the new release. No automatic
# rollback (owner decision); tell the operator exactly what to do.
fail_after_switch() {
  echo "$1" >&2
  echo "DEPLOY FAILED AFTER SWITCH: the site runs the new release. Do not re-run the workflow. To go back run: ROLLBACK_CONFIRM=yes ./scripts/rollback-prod.sh" >&2
  exit 1
}

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
  # shellcheck source=rollback-schema-prep.sh
  # shellcheck disable=SC1091
  source ./scripts/rollback-schema-prep.sh
  rollback_drop_guide_import_00024 || true
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

# 2044: .deploy-in-progress exists only while a deploy has not finished. If it is
# already there, the last run failed part-way: keep the rollback copies it made.
KEEP_ROLLBACK_COPIES=0
if [ -f .deploy-in-progress ]; then
  KEEP_ROLLBACK_COPIES=1
  echo "NOTE: previous deploy did not finish; keeping existing rollback copies" >&2
fi
git rev-parse HEAD > .deploy-in-progress

# 0710: keep the running Caddyfile for rollback.
if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && [ -f caddy/Caddyfile.active ]; then
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

if [ -z "${UBYHOST_SECRET_KEY:-}" ] && { \
    { compose_has_go_service \
        && docker compose --profile go run --rm --no-deps -T --entrypoint sh ubyhost-go \
          -c 'test -s /data/secret_key' >/dev/null 2>&1; } \
    || { docker compose config --services 2>/dev/null | grep -qx ubyhost \
        && docker compose run --rm --no-deps -T --entrypoint sh ubyhost \
          -c 'test -s /data/secret_key' >/dev/null 2>&1; }; \
  }; then
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
if compose_has_go_service && GO_APP_SVC="$(ubyhost_app_service)" && [ "${GO_APP_SVC}" != ubyhost ]; then
  MISSING_EMAIL="$(docker compose --profile go exec -T "${GO_APP_SVC}" ubyhost-web list-accounts-without-email 2>/dev/null \
    | awk -F': ' '/active accounts without a login e-mail:/{print $2; exit}' || true)"
  [ -n "${MISSING_EMAIL}" ] || MISSING_EMAIL="?"
elif running_python_app; then
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
if [ "${UBYHOST_DEPLOYMENT:-}" = "production" ] && compose_has_go_service; then
  if ! { ubyhost_app_service | grep -qx 'ubyhost-go\(-b\)\?'; }; then
    echo "Refusing deploy: ubyhost-go must be running for mandatory pre-deploy backup on the Go-only stack." >&2
    exit 1
  fi
fi
if ubyhost_app_service >/dev/null; then
  echo "==> Mandatory pre-deploy backup"
  ./scripts/backup.sh
  BACKUP_STAMP="$(app_data_exec 'ls -1 /data/backups 2>/dev/null | sort -r | sed -n "1p"')"
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
    if ! app_data_exec "[ -s '${PG_DUMP}' ] && head -c 21 '${PG_DUMP}' | grep -q 'age-encryption.org/v1'"; then
      echo "PostgreSQL backup ${BACKUP_STAMP} is missing, empty or not an age file - refusing deployment." >&2
      exit 1
    fi
    echo "PostgreSQL backup ${BACKUP_STAMP} is valid."
  else
    if ! app_data_exec "f=/data/backups/${BACKUP_STAMP}/ubyhost-backup.tar.age; p=/data/backups/${BACKUP_STAMP}/ubyhost.db; if [ -s \"\$f\" ]; then head -c 21 \"\$f\" | grep -q 'age-encryption.org/v1'; else [ -s \"\$p\" ]; fi"; then
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
    if [ "${PG_MODE}" = "1" ]; then
      BEFORE_COUNTS["${table}"]="$(pg_count "${table}")"
    else
      BEFORE_COUNTS["${table}"]="$(docker compose exec -T ubyhost python -c \
        "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM ${table}')['n'])")"
    fi
  done
  echo "Backup ${BACKUP_STAMP} is valid; live row counts recorded."
fi

if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && docker image inspect ubyhost:local >/dev/null 2>&1; then
  docker tag ubyhost:local ubyhost:previous
  echo "Kept the running image as ubyhost:previous for rollback."
fi
if [ "${KEEP_ROLLBACK_COPIES}" != "1" ] && docker image inspect ubyhost-go:local >/dev/null 2>&1; then
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
if [ -n "${UBYHOST_GO_IMAGE:-}" ]; then
  if ! docker pull "${UBYHOST_GO_IMAGE}"; then
    echo "ERROR: could not pull ${UBYHOST_GO_IMAGE}. Nothing was changed; the old containers keep running. Check that the GHCR package is public (docs/LIGHTSAIL.md, Deploy from GitHub Actions)." >&2
    exit 1
  fi
  GO_IMAGE_PULLED=1
  echo "==> Using CI-built Go image ${UBYHOST_GO_IMAGE}"
  docker tag "${UBYHOST_GO_IMAGE}" ubyhost-go:local
  docker image rm "${UBYHOST_GO_IMAGE}" >/dev/null
else
  echo "==> Building Go image"
  docker compose --profile go build --pull ubyhost-go
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
  elif docker compose config --services 2>/dev/null | grep -qx ubyhost; then
    echo "==> Applying PostgreSQL goose migrations (new image)"
    if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
      scripts/pg_schema.py apply --expect-database ubyhost; then
      echo "Goose apply failed." >&2
      exit 1
    fi
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
  docker compose up -d $(go_non_slot_services)
else
  docker compose up -d
fi

# 1830: two-copy deploy of ubyhost-go. The idle slot gets the new image and
# must be healthy before the old slot stops. Migrations are add-only, so the
# old copy keeps working on the new schema (docs/context/rules.md).
#
# UBYHOST_GO_SLOTS=1 runs a single Go copy instead: the live slot is recreated in
# place, so a deploy has a few seconds of downtime but never holds two copies in
# memory. That is the setting for a 1 GB staging box; production keeps the
# default 2 (no downtime at all).
if docker compose --profile go config --services | grep -qx 'ubyhost-go' \
  && docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source ./scripts/go-slot.sh
  LIVE_SLOT="$(go_live_slot)"
  NEW_SLOT="$(go_idle_slot)"

  if [ "${UBYHOST_GO_SLOTS:-2}" = "1" ]; then
    echo "==> Recreating ubyhost-go slot ${LIVE_SLOT} in place (UBYHOST_GO_SLOTS=1)"
    docker compose --profile go stop "$(go_svc "${NEW_SLOT}")" || true
    docker tag ubyhost-go:local "ubyhost-go:slot-${LIVE_SLOT}"
    docker compose --profile go up -d --no-build --no-deps --force-recreate \
      "$(go_svc "${LIVE_SLOT}")"
    if ! go_wait_healthy "${LIVE_SLOT}" 60; then
      echo "The recreated ubyhost-go copy never became healthy." >&2
      rollback
      exit 1
    fi
    echo "ubyhost-go runs on slot ${LIVE_SLOT} (single-slot mode: a deploy restarts it in place)."
  else
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
  echo "==> Removing retired compose services"
  # shellcheck disable=SC2046
  docker compose up -d --remove-orphans $(go_non_slot_services) || true
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
for _ in $(seq 1 30); do
  if compose_has_go_service && go_exec wget -qO- --timeout=3 http://127.0.0.1:8081/healthz >/dev/null 2>&1; then
    HEALTHY=1
    break
  elif running_python_app && docker compose exec -T ubyhost python -c \
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

echo "==> Scheduler and job queue (ubyhost-go; UBYHOST_SCHEDULER=go)"
if ! compose_has_go_service; then
  echo "ERROR: ubyhost-go is not in compose; this deploy expects the Go-only stack." >&2
  rollback
  exit 1
fi

echo ""
docker compose ps
echo ""
echo "Health (internal):"
if compose_has_go_service; then
  go_exec wget -qO- http://127.0.0.1:8081/healthz
elif running_python_app; then
  docker compose exec -T ubyhost python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/healthz').read().decode())"
else
  echo "ERROR: no running app container (expected ubyhost-go on the Go-only stack)." >&2
  exit 1
fi

echo "==> Backfilling legal acceptance evidence"
if ! go_exec ubyhost-web backfill-legal-acceptance; then
  fail_after_switch "Legal acceptance backfill failed."
fi

# BE-11: encrypt any travel-document numbers still sitting in the plaintext
# columns. Idempotent; logs a count only. The --check before it is
# informational, the one after it is the assertion the deploy must pass.
echo "==> Document-number backfill (counts only)"
go_exec ubyhost-web migrate-encrypt-doc-fields --check || true
if ! go_exec ubyhost-web migrate-encrypt-doc-fields; then
  fail_after_switch "Document-number backfill failed."
fi
if ! go_exec ubyhost-web migrate-encrypt-doc-fields --check; then
  fail_after_switch "Plaintext document numbers remain after the backfill."
fi
if [ -n "${BACKUP_STAMP}" ]; then
  echo ""
  echo "Post-deploy database integrity and row-count checks:"
  if [ "${PG_MODE}" != "1" ]; then
    LIVE_OK="$(docker compose exec -T ubyhost sqlite3 /data/ubyhost.db "PRAGMA integrity_check;")"
    if [ "${LIVE_OK}" != "ok" ]; then
      fail_after_switch "Live database integrity check failed: ${LIVE_OK}"
    fi
  fi
  for table in "${TABLES[@]}"; do
    if [ "${PG_MODE}" = "1" ]; then
      after="$(pg_count "${table}")"
    else
      after="$(docker compose exec -T ubyhost python -c \
        "from app import db; print(db.query_one('SELECT COUNT(*) AS n FROM ${table}')['n'])")"
    fi
    if [ "${after}" -lt "${BEFORE_COUNTS[${table}]}" ]; then
      fail_after_switch "${table} row count fell from ${BEFORE_COUNTS[${table}]} to ${after}."
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
    fail_after_switch "ERROR: public smoke failed (DNS/TLS/Cloudflare?). Internal healthz passed, the new version is running; check the public site now."
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
