#!/usr/bin/env bash
# Build and start (or update) the UbyHost Lightsail stack.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example and set your domain, email, and passwords." >&2
  exit 1
fi

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
echo "Run ./scripts/logs.sh to tail logs."
