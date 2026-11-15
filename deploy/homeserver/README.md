# Homeserver (LAN server)

Two jobs for the homeserver:

1. **Backup vault** for the Lightsail production server — a weekly encrypted
   restic copy over SFTP. One-time setup: [setup-vault.sh](setup-vault.sh) here
   (as root), then `homeserver-vault-init.sh` + `backup-homeserver.sh` in
   [deploy/lightsail](../lightsail/README.md#weekly-backup-to-the-homeserver-vault-restic-over-sftp).
2. **Local AI** (Ollama + Open WebUI): [local-ai/](local-ai/README.md).

Never put the homeserver's address, the restic password or any key in git —
this repository is public; the values below live only in `~/.ssh/config` and a
root-only password file on the servers.

## 1. Backup vault — run once on the homeserver (as root)

```bash
sudo bash deploy/homeserver/setup-vault.sh
```

Creates user `vault` (no login shell, key-only), the chroot
`/storage/backups/lightsail`, and an sshd `Match User vault` block
(`ChrootDirectory` + `ForceCommand internal-sftp`, no forwarding). Nothing is
installed on the homeserver: restic's default `sftp-server` command is served
by `internal-sftp`. The restic repository is
`/storage/backups/lightsail/restic` on disk, seen as `/restic` over sftp.

Then on the **Lightsail server** (from `deploy/lightsail`):

```bash
sudo apt-get install -y restic
sudo UBYHOST_HS_HOST=<homeserver address> ./scripts/homeserver-vault-init.sh
```

`homeserver-vault-init.sh` generates the ssh key, adds the `homeserver-vault`
alias to `~/.ssh/config`, installs the key for `vault` (through the existing
root login — one password prompt), creates `~/.ubyhost-hs-restic-password`
(mode 0600), and initializes the repo `sftp:homeserver-vault:/restic`.

**Copy the restic password into the password manager now** — it is stored
nowhere else, and the repo is unreadable without it.

Weekly cron on Lightsail (Sunday 03:30 UTC, after the 03:00 daily snapshot) —
full steps in [deploy/lightsail/README.md](../lightsail/README.md):

```bash
(crontab -l 2>/dev/null; echo "30 3 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_HS_REPO=sftp:homeserver-vault:/restic ./scripts/backup-homeserver.sh >> /var/log/ubyhost-homeserver.log 2>&1") | crontab -
```

`backup-homeserver.sh` takes a fresh encrypted snapshot (`backup.sh`), refuses
plaintext, pushes it with `restic backup`, then prunes with
`restic forget --keep-weekly 8`.

## Restoring from the vault (on the homeserver, as root)

Only needed to browse or pull a snapshot here; install restic once
(`sudo apt-get install -y restic`):

```bash
sudo RESTIC_REPOSITORY=/storage/backups/lightsail/restic RESTIC_PASSWORD='<from the password manager>' restic snapshots
sudo RESTIC_REPOSITORY=/storage/backups/lightsail/restic RESTIC_PASSWORD='<from the password manager>' restic restore latest --target /tmp/ubyhost-restore
```

`/tmp/ubyhost-restore/<stamp>/` then holds `ubyhost-backup.tar.age` and
`ubyhost-pg.dump.age`; copy them back to Lightsail and restore there with
`restore.sh` / `pg-restore.sh`.
