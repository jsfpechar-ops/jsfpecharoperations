# UbyHost on AWS Lightsail

**Production** lives here (`UBYHOST_DEPLOYMENT=production`, real UbyPort).

| Environment | Platform | UbyPort |
|-------------|----------|---------|
| **Staging** | Render `ubyhost-staging` | `mock` |
| **Production** | This Lightsail stack | `test` → `prod` |

Production Docker stack with HTTPS. **Guides:**

- Server: [docs/LIGHTSAIL.md](../../docs/LIGHTSAIL.md)
- Domain (Cloudflare): [docs/CLOUDFLARE.md](../../docs/CLOUDFLARE.md)

Quick start (on the server, after DNS points at your static IP):

```bash
cp .env.example .env && nano .env
chmod +x scripts/*.sh
./scripts/preflight.sh
./scripts/deploy.sh
```

Useful later: `./scripts/status.sh`, `./scripts/backup.sh`, `./scripts/restore.sh`, `./scripts/smoke-remote.sh`.


## Encrypted backups (OPS-1)

Production snapshots are encrypted with [age](https://age-encryption.org/).
Before the first production backup:

1. Generate one identity **offline**: `age-keygen -o ubyhost-backup.agekey`.
   Keep the private key in the owner's password manager and one offline copy.
   It never goes on the server and never into a snapshot.
2. Put the printed public `age1...` recipient in `.env` as
   `UBYHOST_BACKUP_AGE_RECIPIENT`. With `UBYHOST_DEPLOYMENT=production` the
   backup **fails closed** without it, so no unencrypted copy is ever written.
3. Optionally set `UBYHOST_BACKUP_RETENTION_DAYS` (default **30**). Snapshots
   older than the window are removed on each run; the newest is always kept.

The snapshot folder then holds a single `ubyhost-backup.tar.age`. Restore it
with the private identity on the host:

```bash
AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/restore.sh <stamp>
```

Legacy plaintext snapshots still restore without the identity.

## Weekly backup to Google Drive (bare minimum)

**One-time (on the server, SSH):**

1. Install rclone and connect your Google account:

```bash
sudo apt-get update && sudo apt-get install -y rclone
rclone config
```

Choose: **n** (new remote) → name **`gdrive`** → storage **Google Drive** → defaults → **auto config** (opens a link; sign in as the Google account that owns the Drive).

2. Copy the backup script if your server was deployed from an older tarball (otherwise `git pull` in `/opt/ubyhost`):

```bash
chmod +x /opt/ubyhost/deploy/lightsail/scripts/backup-gdrive.sh
```

3. Test once:

```bash
cd /opt/ubyhost/deploy/lightsail
./scripts/backup-gdrive.sh
```

Check Google Drive for folder **`UbyHost-backups`** with a dated subfolder
(`ubyhost-backup.tar.age` — an encrypted archive; the key is not in it).

4. Weekly cron (Sundays 04:00 UTC):

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh >> /var/log/ubyhost-gdrive.log 2>&1") | crontab -
```

Local `./scripts/backup.sh` still runs daily at 03:00 if you added that cron earlier; this uploads the **newest** snapshot to Drive once a week.

## S3 backup (encrypted archive, EU region)

S3 is the EU-region off-site target (`eu-central-1`) and runs alongside the
Google Drive copy when you use both. `backup-s3.sh` uploads **only** the
encrypted `ubyhost-backup.tar.age` and refuses a plaintext snapshot.

<details>
<summary>Enable S3 (click to expand)</summary>

Uses **rclone** with an **IAM access key** (no browser login).

**One-time in AWS:**

1. **S3** → Create bucket (e.g. `ubyhost-backups-yourname`) in **eu-central-1**
   (Frankfurt). Block public access: **on**. Default encryption: **SSE-S3**.
   Add a **lifecycle rule** that expires objects after
   `UBYHOST_BACKUP_RETENTION_DAYS` days (default 30) — the bucket, not the
   script, bounds off-site retention.
2. **IAM** → User → programmatic access → attach a policy limited to that
   bucket: `s3:PutObject`, `s3:ListBucket`, `s3:GetObject` on
   `arn:aws:s3:::bucket-name` and `arn:aws:s3:::bucket-name/*`
   (`DeleteObject` is not needed; the lifecycle rule expires objects).
3. Save **Access key ID** + **Secret access key** (shown once).

**On the server:**

```bash
rclone config
```

**n** → name **`s3`** → **Amazon S3** → **AWS access key** (not anonymous) → paste key + secret → region **`eu-central-1`** → endpoint blank → **no** advanced ACL unless you know you need it.

Test:

```bash
cd /opt/ubyhost/deploy/lightsail
export UBYHOST_S3_BUCKET=your-bucket-name
./scripts/backup-s3.sh
```

**`No such file or directory`?** Run these on the server:

```bash
ls -la /opt/ubyhost/deploy/lightsail/scripts/backup-s3.sh   # missing → git pull in /opt/ubyhost
cd /opt/ubyhost/deploy/lightsail && test -f .env || echo "need .env here"
docker compose ps    # ubyhost must be Up
```

If the script exists but `docker cp` fails, set the container name explicitly:

```bash
export UBYHOST_CONTAINER="$(docker compose ps --format '{{.Names}}' ubyhost | head -1)"
UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh
```

Weekly cron (example; set your bucket name):

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1") | crontab -
```

You can use **both** Drive and S3 (two cron lines). Pick one off-site copy if you want bare minimum.

</details>
