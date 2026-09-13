#!/usr/bin/env bash
# One-shot Lightsail production bootstrap (run on the instance via SSH).
# Required env (do not commit secrets):
#   UBYHOST_DOMAIN   e.g. 3-70-222-66.sslip.io
#   UBYHOST_ADMIN_PASSWORD
# Optional: ACME_EMAIL, UBYHOST_OPERATOR_EMAIL (default admin@sslip.io)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${UBYHOST_INSTALL_DIR:-/opt/ubyhost}"
DOMAIN="${UBYHOST_DOMAIN:?set UBYHOST_DOMAIN}"
ADMIN_PW="${UBYHOST_ADMIN_PASSWORD:?set UBYHOST_ADMIN_PASSWORD}"
ACME_EMAIL="${ACME_EMAIL:-admin@sslip.io}"
OPERATOR_EMAIL="${UBYHOST_OPERATOR_EMAIL:-${ACME_EMAIL}}"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Running setup-server.sh"
  ${SUDO} bash "${INSTALL_DIR}/deploy/lightsail/scripts/setup-server.sh"
fi

if ! groups | grep -q docker; then
  echo "Note: re-login or run: sg docker -c '$0'" >&2
  if [ -n "${SUDO}" ]; then
    exec sg docker -c "bash $0"
  fi
fi

cd "${ROOT}"

if [ ! -f .env ]; then
  cp .env.example .env
fi

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

set_kv UBYHOST_DOMAIN "${DOMAIN}"
set_kv UBYHOST_PUBLIC_BASE_URL "https://${DOMAIN}"
set_kv CLOUDFLARE_PROXY "0"
set_kv UBYHOST_DEPLOYMENT "production"
set_kv UBYHOST_UBYPORT_ENV "test"
set_kv UBYHOST_ADMIN_USERNAME "admin"
set_kv UBYHOST_ADMIN_PASSWORD "${ADMIN_PW}"
set_kv ACME_EMAIL "${ACME_EMAIL}"
set_kv UBYHOST_OPERATOR_EMAIL "${OPERATOR_EMAIL}"
set_kv UBYHOST_GUEST_PIN "1"
set_kv UBYHOST_ENABLE_SCHEDULER "1"
set_kv UBYHOST_BOOTSTRAP_ADMIN "1"

chmod +x scripts/*.sh
./scripts/deploy.sh

echo "==> Public health check"
curl -sS -m 20 "https://${DOMAIN}/healthz" || curl -sS -m 10 "http://127.0.0.1/healthz" || true

CRON_LINE="0 3 * * * cd ${INSTALL_DIR}/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1"
if ! crontab -l 2>/dev/null | grep -q ubyhost-backup; then
  (crontab -l 2>/dev/null; echo "${CRON_LINE}") | crontab -
  echo "==> Backup cron installed"
fi

echo "Done. URL: https://${DOMAIN}"
