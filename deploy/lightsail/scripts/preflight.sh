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

if [ "${DEPLOYMENT}" != "production" ]; then
  warn "UBYHOST_DEPLOYMENT=${DEPLOYMENT} — this Lightsail stack is meant to be production"
fi

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
  warn "UBYHOST_GUEST_PIN=0 on production — guest permalinks are unprotected"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_ENABLE_SCHEDULER:-1}" = "0" ]; then
  warn "UBYHOST_ENABLE_SCHEDULER=0 — iCal sync, auto-submit, and photo sweep will not run"
fi

if [ "${DEPLOYMENT}" = "production" ] && [ "${UBYHOST_ICAL_ALLOW_PRIVATE:-0}" = "1" ]; then
  die "UBYHOST_ICAL_ALLOW_PRIVATE must not be enabled on production"
fi

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
