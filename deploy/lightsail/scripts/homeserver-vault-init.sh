#!/usr/bin/env bash
# One-time handshake from this Lightsail server to the homeserver backup vault
# (deploy/homeserver/README.md): ssh key, ~/.ssh/config alias, vault key install
# via the existing root login, restic password file, repo init.
#
# Prereq on the homeserver: sudo bash deploy/homeserver/setup-vault.sh
#
# Env (none of it is committed; values live in ~/.ssh/config and a root-only
# password file on this server):
#   UBYHOST_HS_HOST            homeserver address (required; LAN IP or name)
#   UBYHOST_HS_ALIAS           ssh alias, default homeserver-vault
#   UBYHOST_HS_USER            vault user, default vault
#   UBYHOST_HS_KEY             default ~/.ssh/<alias>_ed25519
#   UBYHOST_HS_REPO            default sftp:<alias>:/restic
#   UBYHOST_HS_PASSWORD_FILE   default ~/.ubyhost-hs-restic-password
set -euo pipefail

ALIAS="${UBYHOST_HS_ALIAS:-homeserver-vault}"
HOST_NAME="${UBYHOST_HS_HOST:?set UBYHOST_HS_HOST to the homeserver address}"
VAULT_USER="${UBYHOST_HS_USER:-vault}"
KEY="${UBYHOST_HS_KEY:-$HOME/.ssh/${ALIAS}_ed25519}"
REPO="${UBYHOST_HS_REPO:-sftp:${ALIAS}:/restic}"
PASSWORD_FILE="${UBYHOST_HS_PASSWORD_FILE:-$HOME/.ubyhost-hs-restic-password}"

if ! command -v restic >/dev/null 2>&1; then
  echo "Install restic first: sudo apt-get install -y restic" >&2
  exit 1
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [ ! -f "${KEY}" ]; then
  ssh-keygen -t ed25519 -f "${KEY}" -N "" -C "ubyhost-backup@${ALIAS}"
fi

if ! grep -q "^Host ${ALIAS}\$" "$HOME/.ssh/config" 2>/dev/null; then
  touch "$HOME/.ssh/config"
  cat >> "$HOME/.ssh/config" <<EOF

Host ${ALIAS}
  HostName ${HOST_NAME}
  User ${VAULT_USER}
  IdentityFile ${KEY}
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
fi
chmod 600 "$HOME/.ssh/config"

# Install the key for the vault user through the existing root login (the vault
# user itself is key-only, so ssh-copy-id cannot target it directly).
if ! ssh -i "${KEY}" -o BatchMode=yes "root@${HOST_NAME}" true 2>/dev/null; then
  echo "One root password prompt follows, to add this key for root:"
  ssh-copy-id -i "${KEY}.pub" "root@${HOST_NAME}"
fi
B64="$(base64 -w0 "${KEY}.pub")"
ssh -i "${KEY}" "root@${HOST_NAME}" "U=${VAULT_USER}; install -d -m 700 -o \$U -g \$U /home/\$U/.ssh; touch /home/\$U/.ssh/authorized_keys; echo '${B64}' | base64 -d | grep -qxF - /home/\$U/.ssh/authorized_keys || echo '${B64}' | base64 -d >> /home/\$U/.ssh/authorized_keys; chown \$U:\$U /home/\$U/.ssh/authorized_keys; chmod 600 /home/\$U/.ssh/authorized_keys"

if [ ! -f "${PASSWORD_FILE}" ]; then
  (umask 077; openssl rand -base64 48 > "${PASSWORD_FILE}")
  echo "Generated ${PASSWORD_FILE} (0600). Copy the password into the owner's password manager now; it is stored nowhere else."
fi
chmod 600 "${PASSWORD_FILE}"

export RESTIC_REPOSITORY="${REPO}"
export RESTIC_PASSWORD_FILE="${PASSWORD_FILE}"

echo "Testing sftp access as ${VAULT_USER} via ${ALIAS}..."
printf 'ls /restic\n' | sftp -b - "${ALIAS}" >/dev/null

if ! restic snapshots >/dev/null 2>&1; then
  restic init
fi
restic snapshots

echo "OK. Weekly cron (Sunday 03:30 UTC):"
echo "  30 3 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_HS_REPO=${REPO} ./scripts/backup-homeserver.sh >> /var/log/ubyhost-homeserver.log 2>&1"
