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

echo "==> Building image"
docker compose build --pull

echo "==> Starting stack"
docker compose up -d --remove-orphans

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
