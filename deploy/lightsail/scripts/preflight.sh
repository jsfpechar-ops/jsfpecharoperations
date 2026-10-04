#!/usr/bin/env bash
# Validate Lightsail .env before building the stack.
# Usage (from deploy/lightsail): ./scripts/preflight.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example and set domain, email, and passwords." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

fail=0
warn() { echo "WARNING: $*" >&2; }
die() { echo "ERROR: $*" >&2; fail=1; }

for var in UBYHOST_DOMAIN ACME_EMAIL UBYHOST_PUBLIC_BASE_URL UBYHOST_ADMIN_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    die "required variable ${var} is empty in .env"
  fi
done

DEPLOYMENT="${UBYHOST_DEPLOYMENT:-local}"
UBYPORT="${UBYHOST_UBYPORT_ENV:-mock}"

if [ "${DEPLOYMENT}" = "staging" ]; then
  # Step 0: the staging Lightsail server. Either the mock UbyPort, served by
  # the mock-ubyport compose service (profile "staging"), or the real UbyPort
  # test environment. Never prod (refused below as well).
  case "${UBYPORT}" in
    mock)
      case ",${COMPOSE_PROFILES:-}," in
        *,staging,*) ;;
        *) die "staging on mock needs COMPOSE_PROFILES=staging in .env (starts the mock-ubyport service)" ;;
      esac
      case "${UBYHOST_MOCK_URL:-}" in
        http://mock-ubyport:8081/*) ;;
        *) die "staging on mock needs UBYHOST_MOCK_URL=http://mock-ubyport:8081/ws_uby/ws_uby.svc" ;;
      esac
      ;;
    test)
      warn "staging talks to the real UbyPort test environment: test data and test credentials only"
      ;;
    *) die "UBYHOST_DEPLOYMENT=staging requires UBYHOST_UBYPORT_ENV=mock or test" ;;
  esac
  case "${UBYHOST_WEB_WORKERS:-2}" in
  ''|*[!0-9]*|0|0*) die "UBYHOST_WEB_WORKERS must be a whole number from 1 to 16" ;;
esac
if [ "${UBYHOST_WEB_WORKERS:-2}" -gt 16 ]; then
  die "UBYHOST_WEB_WORKERS must be a whole number from 1 to 16"
fi

case "${LITESTREAM_S3_PATH:-ubyhost/production}" in
    *production*) die "staging must replicate to its own LITESTREAM_S3_PATH, not ${LITESTREAM_S3_PATH:-ubyhost/production}" ;;
  esac
elif [ "${DEPLOYMENT}" != "production" ]; then
  warn "UBYHOST_DEPLOYMENT=${DEPLOYMENT} — this Lightsail stack is meant to be production or staging"
fi

case ",${COMPOSE_PROFILES:-}," in
  *,staging,*)
    if [ "${DEPLOYMENT}" = "production" ]; then
      die "COMPOSE_PROFILES=staging on production would start the mock UbyPort"
    fi
    ;;
esac

if [ "${UBYPORT}" = "prod" ] && [ "${DEPLOYMENT}" != "production" ]; then
  die "UBYHOST_UBYPORT_ENV=prod requires UBYHOST_DEPLOYMENT=production"
fi

haystack="${RENDER_EXTERNAL_URL:-} ${UBYHOST_PUBLIC_BASE_URL:-} ${UBYHOST_DOMAIN:-}"
if [ "${RENDER:-}" = "true" ] || [ "${RENDER:-}" = "1" ] || [ -n "${RENDER_SERVICE_ID:-}" ]; then
  if [ "${UBYPORT}" = "prod" ]; then
    die "UBYHOST_UBYPORT_ENV=prod is not allowed on Render-like configuration"
  fi
  warn "Render environment variables are set — this Lightsail .env looks copied from Render"
fi
case "${haystack}" in
  *onrender.com*)
    if [ "${UBYPORT}" = "prod" ]; then
      die "UBYHOST_UBYPORT_ENV=prod is not allowed when the public URL is onrender.com"
    fi
    warn "Public URL/domain contains onrender.com — Lightsail should use ubyhost.com"
    ;;
esac

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYPORT}" = "mock" ]; then
  warn "production + mock — nothing is reported to the police"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_GUEST_PIN:-1}" = "0" ]; then
  die "UBYHOST_GUEST_PIN=0 on production — guest permalinks would be unprotected and the app refuses to start"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_ENABLE_SCHEDULER:-1}" = "0" ]; then
  warn "UBYHOST_ENABLE_SCHEDULER=0 — iCal sync, auto-submit, and photo sweep will not run"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_ICAL_ALLOW_PRIVATE:-0}" = "1" ]; then
  die "UBYHOST_ICAL_ALLOW_PRIVATE must not be enabled on production"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_AGE_RECIPIENT:-}" ]; then
  die "UBYHOST_BACKUP_AGE_RECIPIENT is empty — the nightly backup refuses to run on production without it"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ -z "${UBYHOST_BACKUP_PING_URL:-}" ]; then
  die "UBYHOST_BACKUP_PING_URL is empty — a failing nightly backup would go unnoticed"
fi

# WP06: web + scheduler worker + litestream + Caddy need at least the 2 GB
# bundle. WP32: the compose defaults (web 2g, worker 1g, litestream 256m,
# caddy 256m) are sized for the 8 GB production server; a smaller server sets
# lower UBYHOST_*_MEM values in .env (see docs/LIGHTSAIL.md, Sizing).
mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
if [ "${mem_kb:-0}" -gt 0 ] && [ "${mem_kb}" -lt 1700000 ]; then
  if [ "${UBYHOST_ALLOW_SMALL_HOST:-0}" = "1" ]; then
    warn "only $((mem_kb / 1024)) MB RAM — the stack is sized for the 2 GB bundle"
  else
    die "only $((mem_kb / 1024)) MB RAM — move to the 2 GB Lightsail bundle first (or set UBYHOST_ALLOW_SMALL_HOST=1)"
  fi
fi

# WP05: the litestream service replicates the database to S3 continuously.
# Without these it crash-loops and the only off-site copy is a day old.
if [ "${DEPLOYMENT}" = "production" ]; then
  for var in LITESTREAM_S3_BUCKET LITESTREAM_ACCESS_KEY_ID LITESTREAM_SECRET_ACCESS_KEY; do
    if [ -z "${!var:-}" ]; then
      die "${var} is empty — Litestream cannot replicate the database to S3 (see README.md, Litestream)"
    fi
  done
  if [ -z "${LITESTREAM_HEARTBEAT_URL:-}" ]; then
    warn "LITESTREAM_HEARTBEAT_URL is empty — stalled replication would go unnoticed"
  fi
fi
case "${LITESTREAM_S3_PATH:-ubyhost/production}" in
  /*|*/) die "LITESTREAM_S3_PATH must not start or end with a slash" ;;
esac

if [ -n "${UBYHOST_SECRET_KEY:-}" ] && [ "${#UBYHOST_SECRET_KEY}" -lt 32 ]; then
  die "UBYHOST_SECRET_KEY must be at least 32 characters (or leave empty for auto-generate)"
fi

base="${UBYHOST_PUBLIC_BASE_URL:-}"
if [ "${base#https://}" = "${base}" ]; then
  warn "UBYHOST_PUBLIC_BASE_URL should use https:// in production"
fi
host="${base#https://}"
host="${host#http://}"
host="${host%%/*}"
host="${host%%:*}"
if [ -n "${UBYHOST_DOMAIN:-}" ] && [ -n "${host}" ] && [ "${host}" != "${UBYHOST_DOMAIN}" ]; then
  warn "UBYHOST_PUBLIC_BASE_URL host (${host}) does not match UBYHOST_DOMAIN (${UBYHOST_DOMAIN})"
fi

if [ "${CLOUDFLARE_PROXY:-0}" = "1" ]; then
  for cert in caddy/certs/origin.pem caddy/certs/origin-key.pem; do
    if [ ! -f "${cert}" ]; then
      die "missing ${cert} — see docs/CLOUDFLARE.md"
    fi
  done
fi

if [ "${fail}" -ne 0 ]; then
  echo "Preflight failed. Fix .env (and origin certs) before deploy." >&2
  exit 1
fi

echo "Preflight OK (deployment=${DEPLOYMENT} ubyport=${UBYPORT} domain=${UBYHOST_DOMAIN})"
