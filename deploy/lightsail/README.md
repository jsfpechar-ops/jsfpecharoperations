# UbyHost on AWS Lightsail

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

## Weekly backup to S3 (alternative to Drive)

Same data (`ubyhost.db` + `secret_key`); uses **rclone** with an **IAM access key** (no browser login).

**One-time in AWS:**

1. **S3** → Create bucket (e.g. `ubyhost-backups-yourname`) in **eu-central-1** (Frankfurt). Block public access: **on**. Versioning: optional but nice.
2. **IAM** → User → programmatic access → attach policy limited to that bucket (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:DeleteObject` on `arn:aws:s3:::bucket-name/*`).
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

Weekly cron (example; set your bucket name):

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 0 cd /opt/ubyhost/deploy/lightsail && UBYHOST_S3_BUCKET=your-bucket-name ./scripts/backup-s3.sh >> /var/log/ubyhost-s3.log 2>&1") | crontab -
```

You can use **both** Drive and S3 (two cron lines). Pick one off-site copy if you want bare minimum.
