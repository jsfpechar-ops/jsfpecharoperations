#!/usr/bin/env bash
# Homeserver side of the Lightsail backup vault (see README.md in this directory).
# Run once as root ON THE HOMESERVER:
#   sudo bash setup-vault.sh
# Creates a dedicated sftp-only user "vault", chrooted into
# /storage/backups/lightsail, key-only auth, no forwarding. The restic repo is
# /storage/backups/lightsail/restic on disk (sftp path /restic inside the chroot).
set -euo pipefail

VAULT_USER="vault"
BASE="/storage/backups/lightsail"
REPO_DIR="${BASE}/restic"
CONF="/etc/ssh/sshd_config.d/90-ubyhost-vault.conf"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash setup-vault.sh" >&2
  exit 1
fi

if ! grep -Eq '^Include\s+/etc/ssh/sshd_config.d/' /etc/ssh/sshd_config; then
  echo "/etc/ssh/sshd_config has no 'Include /etc/ssh/sshd_config.d/...' line; add it first." >&2
  exit 1
fi

if ! id "${VAULT_USER}" >/dev/null 2>&1; then
  useradd -m -s /usr/sbin/nologin "${VAULT_USER}"
  echo "Created user ${VAULT_USER} (no login shell)."
fi

mkdir -p "${REPO_DIR}"
# ChrootDirectory requires every path component root-owned and not group/world-writable.
chown root:root /storage /storage/backups "${BASE}"
chmod 755 /storage /storage/backups "${BASE}"
chown "${VAULT_USER}:${VAULT_USER}" "${REPO_DIR}"
chmod 750 "${REPO_DIR}"

mkdir -p /etc/ssh/sshd_config.d
cat > "${CONF}" <<EOF
# UbyHost Lightsail backups: sftp-only vault user, chrooted, key-only (deploy/homeserver/setup-vault.sh).
Match User ${VAULT_USER}
  ChrootDirectory ${BASE}
  ForceCommand internal-sftp
  PasswordAuthentication no
  PubkeyAuthentication yes
  AllowTcpForwarding no
  AllowAgentForwarding no
  X11Forwarding no
  PermitTTY no
EOF

if sshd -t; then
  systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null \
    || echo "Reload sshd manually: sudo systemctl reload ssh"
  echo "sshd config valid, sshd reloaded. Existing sessions are not dropped."
else
  echo "sshd -t rejected ${CONF}; fix it before reloading (sudo systemctl reload ssh)." >&2
  exit 1
fi

echo "Vault ready: ${VAULT_USER} can only reach ${REPO_DIR} over sftp (chroot ${BASE})."
echo "Next, on the Lightsail server (deploy/lightsail): UBYHOST_HS_HOST=<this server> ./scripts/homeserver-vault-init.sh"
