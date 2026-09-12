#!/usr/bin/env bash
# One-time AWS Lightsail (Ubuntu) bootstrap for UbyHost Docker.
# Run as root on a fresh instance:
#   curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/deploy/lightsail/scripts/setup-server.sh | bash
# Or after cloning:
#   sudo bash deploy/lightsail/scripts/setup-server.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "==> Updating system packages"
apt-get update
apt-get upgrade -y

echo "==> Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

echo "==> Configuring firewall (SSH, HTTP, HTTPS)"
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi

INSTALL_DIR="${UBYHOST_INSTALL_DIR:-/opt/ubyhost}"
DEPLOY_USER="${UBYHOST_DEPLOY_USER:-ubuntu}"

echo "==> Preparing install directory: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
if id "${DEPLOY_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${DEPLOY_USER}" || true
  chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${INSTALL_DIR}"
fi

cat <<EOF

Server bootstrap complete.

Next steps (as ${DEPLOY_USER} or root):

  1. Clone the repository into ${INSTALL_DIR}:
       git clone https://github.com/YOUR_ORG/jsfpecharoperations.git ${INSTALL_DIR}
       cd ${INSTALL_DIR}/deploy/lightsail

  2. Configure environment:
       cp .env.example .env
       nano .env

  3. Deploy:
       ./scripts/deploy.sh

  4. Verify:
       curl -sS https://YOUR_DOMAIN/healthz

  5. Optional — daily backup cron (03:00 UTC):
       (crontab -l 2>/dev/null; echo "0 3 * * * cd ${INSTALL_DIR}/deploy/lightsail && ./scripts/backup.sh >> /var/log/ubyhost-backup.log 2>&1") | crontab -

Recommended Lightsail plan for ~10 properties: Micro (1 GB RAM, \$7/mo).
Point your domain A record at this instance's static IP before deploy.

EOF
