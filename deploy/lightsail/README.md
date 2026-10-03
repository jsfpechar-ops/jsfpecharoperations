# UbyHost on AWS Lightsail

**Production** lives here (`UBYHOST_DEPLOYMENT=production`, real UbyPort) on
Lightsail **General purpose 8 GB** (Frankfurt) — see [LIGHTSAIL.md](../../docs/LIGHTSAIL.md).

| Environment | Platform | UbyPort |
|-------------|----------|---------|
| **Staging** | Render `ubyhost-staging` | `mock` |
| **Staging (Lightsail)** | This stack on a second instance, `UBYHOST_DEPLOYMENT=staging` | `mock` (service `mock-ubyport`, default) or `test` |
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

Useful later: `./scripts/status.sh`, `./scripts/backup.sh`, `./scripts/restore.sh`, `./scripts/restore_test.sh`, `./scripts/smoke-remote.sh`.


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

## Litestream: continuous S3 replica (WP05)

The `litestream` service (image `litestream/litestream:0.5.17`, config
`litestream.yml`) streams every change of `/data/ubyhost.db` to
`s3://$LITESTREAM_S3_BUCKET/$LITESTREAM_S3_PATH` in `eu-central-1`, about
every 10 seconds. That is the data-loss window if the VM is lost. The nightly
age-encrypted backup above stays as a second, independent copy.

What the replica does **not** hold:

- the secret key (`UBYHOST_SECRET_KEY` in `.env` or `/data/secret_key`). It
  decrypts document numbers, signatures, TOTP secrets and UbyPort passwords.
  Keep a copy in the owner's password manager. Without it a restored database
  opens but every encrypted field is unreadable;
- passport photos under `/data/passport_photos` (short-lived by design);
- client-side encryption. Litestream 0.5 has none. The bucket's default
  encryption (SSE-S3), Block Public Access and the dedicated IAM user protect
  it. Guest names and stay dates are in it in the clear, like in the live file.

### One-time AWS setup

1. S3 → Create bucket, for example `ubyhost-litestream-<suffix>`, region
   **eu-central-1**. Block all public access: **on**. Bucket versioning:
   **enable**. Default encryption: **SSE-S3**.
2. Bucket → Management → Lifecycle rule `expire-noncurrent`, whole bucket:
   "Permanently delete noncurrent versions of objects" after **30** days, and
   "Delete expired object delete markers". Do not add a rule that expires
   current versions: Litestream removes old files itself (7-day window).
3. IAM → Users → Create user `ubyhost-litestream` (no console access). Attach
   an inline policy (replace the bucket name; the prefix must match
   `LITESTREAM_S3_PATH`; `ubyhost/*` also covers the new prefix you switch to
   after a restore):

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "ListReplicaPrefix",
         "Effect": "Allow",
         "Action": "s3:ListBucket",
         "Resource": "arn:aws:s3:::ubyhost-litestream-SUFFIX",
         "Condition": {"StringLike": {"s3:prefix": ["ubyhost/*", "ubyhost"]}}
       },
       {
         "Sid": "ReadWriteReplicaObjects",
         "Effect": "Allow",
         "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::ubyhost-litestream-SUFFIX/ubyhost/*"
       }
     ]
   }
   ```

4. Create an access key for that user ("Application running outside AWS").
   Put it in the server `.env` as `LITESTREAM_ACCESS_KEY_ID` and
   `LITESTREAM_SECRET_ACCESS_KEY`, and the bucket as `LITESTREAM_S3_BUCKET`.
5. Optional: a healthchecks.io check with period 5 min and grace 10 min; put
   its ping URL in `LITESTREAM_HEARTBEAT_URL`.

Then `./scripts/deploy.sh` (preflight refuses a production deploy while the
bucket or keys are empty), and:

```bash
docker compose logs --tail=30 litestream   # expect "snapshot complete"
./scripts/restore_test.sh                  # must end with "Restore drill passed"
```

Run `./scripts/restore_test.sh` again once per quarter. It restores the
newest replica into a temporary file inside a throwaway container, checks
`PRAGMA integrity_check`, compares row counts of the main tables with the live
database and deletes the copy. Non-zero exit on any mismatch.

### Runbook: the VM is lost

1. Create a new Lightsail instance (Frankfurt, same bundle) and follow
   [docs/LIGHTSAIL.md](../../docs/LIGHTSAIL.md) up to, but not including,
   `./scripts/deploy.sh`. Restore `.env` from the password manager, including
   `UBYHOST_SECRET_KEY`. If production kept the key only in
   `/data/secret_key`, set `UBYHOST_SECRET_KEY` in `.env` to the saved copy.
2. Build the image and create the data volume with the app's ownership,
   without starting the app (an app start would create an empty database):

   ```bash
   cd /opt/ubyhost/deploy/lightsail
   docker compose build
   docker compose run --rm --no-deps --entrypoint true ubyhost
   ```

3. Restore the newest replica into the volume:

   ```bash
   docker compose run --rm --no-deps litestream \
     restore -config /etc/litestream.yml -integrity-check full /data/ubyhost.db
   ```

   For a point in time, add `-timestamp 2026-10-01T12:00:00Z`.
4. In `.env`, set `LITESTREAM_S3_PATH` to a new prefix, for example
   `ubyhost/production-YYYYMMDD`. The new server must never replicate into
   the old prefix: two histories under one path can make it unrestorable.
5. `./scripts/deploy.sh`, sign in, open one stay, then
   `./scripts/restore_test.sh`.
6. Move the static IP (or DNS) to the new instance.

If the replica is unusable, fall back to the newest age-encrypted snapshot
(`restore.sh`, or the S3/Drive off-site copy). `restore.sh` stops Litestream
and leaves it stopped; set a new `LITESTREAM_S3_PATH`, then
`docker compose up -d litestream`.

## Staging server (Step 0)

A second Lightsail instance runs this same stack with
`UBYHOST_DEPLOYMENT=staging`, and either the mock UbyPort (default) or the real
UbyPort test environment. It never holds real guest data. Every HIGH RISK change is deployed here and clicked through before it is
merged.

Differences from production, all in the staging `.env`:

```bash
UBYHOST_DEPLOYMENT=staging
UBYHOST_UBYPORT_ENV=mock                 # or test; each workflow run sets it
COMPOSE_PROFILES=staging                 # starts the mock-ubyport service
UBYHOST_MOCK_URL=http://mock-ubyport:8081/ws_uby/ws_uby.svc
UBYHOST_DOMAIN=staging.example.com        # its own domain
UBYHOST_PUBLIC_BASE_URL=https://staging.example.com
LITESTREAM_S3_PATH=staging/ubyhost        # its own prefix, its own IAM user
UBYHOST_MAIL_BACKEND=console              # claim links appear in Settings
UBYHOST_ALLOW_SMALL_HOST=1                # 1 GB bundle; limits are caps, traffic is tiny
```

`preflight.sh` refuses a staging `.env` whose UbyPort is neither `mock` nor
`test`, a `mock` staging without the profile or the mock URL, or a Litestream
prefix containing `production`, and refuses `COMPOSE_PROFILES=staging` on
production.

Deploy from GitHub: Actions → **Deploy staging** → Run workflow → pick the
branch and the **ubyport_env** input:

- `mock` (default): the `mock-ubyport` service answers. Use it for everything
  that does not need the police server.
- `test`: the real UbyPort test environment
  (`https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc`). Submissions use the test
  web-service credentials saved on the staging property, so set those first.
  Test data only, as everywhere on staging.

The run uses the `staging` environment's secrets and checks, on the server,
that `.env` says `UBYHOST_DEPLOYMENT=staging` and a UbyPort of `mock` or
`test` before it changes anything. It then writes the chosen value into the
server's `.env` as `UBYHOST_UBYPORT_ENV`. The mock service keeps running with
`test`; it is simply not used.
