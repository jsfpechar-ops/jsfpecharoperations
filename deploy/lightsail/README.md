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
./scripts/deploy.sh
```

## Weekly backup to Google Drive (bare minimum)

**One-time (on the server, SSH):**

1. Install rclone and connect your Google account:

```bash
sudo apt-get update && sudo apt-get install -y rclone
rclone config
```

Choose: **n** (new remote) → name **`gdrive`** → storage **Google Drive** → defaults → **auto config** (opens a link; sign in as **jsf.pechar@gmail.com** or the Google account that owns the Drive).

2. Copy the backup script if your server was deployed from an older tarball (otherwise `git pull` in `/opt/ubyhost`):

```bash
chmod +x /opt/ubyhost/deploy/lightsail/scripts/backup-gdrive.sh
```

3. Test once:

```bash
cd /opt/ubyhost/deploy/lightsail
./scripts/backup-gdrive.sh
```

Check Google Drive for folder **`UbyHost-backups`** with a dated subfolder (`ubyhost.db`, `secret_key`).

4. Weekly cron (Sundays 04:00 UTC):

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && ./scripts/backup-gdrive.sh >> /var/log/ubyhost-gdrive.log 2>&1") | crontab -
```

Local `./scripts/backup.sh` still runs daily at 03:00 if you added that cron earlier; this uploads the **newest** snapshot to Drive once a week.

## Monthly S3 backup

S3 is the second off-site copy, once a month. Google Drive remains weekly. The
same data (`ubyhost.db` + `secret_key`) is uploaded through **rclone** with an
IAM access key (no browser login).

**One-time in AWS:**

1. **S3** → Create bucket (e.g. `ubyhost-backups-yourname`) in **eu-central-1** (Frankfurt). Keep **Block all public access** on, enable default SSE-S3 encryption, and enable versioning.
2. **IAM** → User → programmatic access → attach policy limited to that bucket (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on that bucket and its objects).
3. Save **Access key ID** + **Secret access key** (shown once).

**On the server:**

```bash
rclone config
```

**n** → name **`s3`** → **Amazon S3** → **AWS access key** (not anonymous) → paste key + secret → region **`eu-central-1`** → endpoint blank → **no** advanced ACL unless you know you need it.

Test:

```bash
cd /opt/ubyhost/deploy/lightsail
printf '\nUBYHOST_S3_BUCKET=your-bucket-name\n' >> .env
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

Install both schedules (safe to run again; it replaces old Drive/S3 cron lines):

```bash
chmod +x scripts/install-offsite-backup-cron.sh
./scripts/install-offsite-backup-cron.sh
crontab -l
```

This keeps Drive on Sundays at 04:00 UTC and runs S3 on the first day of each
month at 05:00 UTC. Each upload creates a new timestamped folder.
