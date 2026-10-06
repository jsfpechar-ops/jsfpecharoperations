# WP05: Litestream continuous backup to S3

## Summary
Adds a `litestream` sidecar to the Lightsail stack that streams `/data/ubyhost.db` to S3 (eu-central-1) every 10 s, a restore drill script, and a runbook for losing the VM. Pinned to `litestream/litestream:0.5.17` (latest release, 31 Aug 2026) by tag and multi-arch index digest. Config uses the 0.5 format (single `replica:` per db, global `snapshot:`, `retention:`, `validation:`, `heartbeat-url`). The nightly age-encrypted backup is unchanged. Stacked: WP06, WP07 and STEP0 build on this commit.

## Files changed
- `deploy/lightsail/litestream.yml`: new. 0.5 config: S3 replica from env vars, sync 10 s, snapshot every 6 h, 7-day retention, validation every 6 h, health-gated heartbeat, busy-timeout 5 s.
- `deploy/lightsail/docker-compose.yml`: new `litestream` service (uid 10001, same volume, config mounted read-only, only the LITESTREAM_* variables passed, not the whole .env, `mem_limit: 128m`, `stop_grace_period: 40s`, starts after the app is healthy).
- `deploy/lightsail/scripts/restore_test.sh`: new restore drill (see below).
- `deploy/lightsail/scripts/restore.sh`: stops litestream before an age restore, deletes `/data/.ubyhost.db-litestream`, leaves litestream stopped and prints how to switch to a new prefix.
- `deploy/lightsail/scripts/preflight.sh`: production refuses empty bucket or keys; warns on empty heartbeat; validates the prefix.
- `deploy/lightsail/.env.example`: LITESTREAM_* placeholders.
- `deploy/lightsail/README.md`: AWS setup with IAM policy, restore drill, VM-loss runbook.
- `.github/workflows/deploy-preflight.yml`: prints whether the LITESTREAM_* keys are set (never the values).

## Tests added
None in the app suite (spec). Local run against a real S3 API instead: Litestream 0.5.17 (linux arm64 binary) replicating a database created by the app's own `db.init_db()` to a moto S3 server, with `restore_test.sh` in `RESTORE_TEST_LOCAL=1` mode. The container has no sqlite3 CLI, so a small Python shim stood in for `sqlite3 -readonly DB SQL`; the litestream image ships the real sqlite3.

## Test commands and results
Positive run (production config, sync 10 s, default settle 15 s):
```
integrity_check: ok
table            live_before   restored live_after  result
user_account              0          0          0  ok
legal_entity              0          0          0  ok
apartment                 8          8          8  ok
reservation               0          0          0  ok
guest                     0          0          0  ok
submission                0          0          0  ok
Restore drill passed. The temporary copy was deleted.
exit=0
```
Negative run (litestream stopped, one row written after): `apartment 9 8 9 MISMATCH`, `Restore drill FAILED`, exit=1.
Litestream log confirmed `snapshot complete` and that an empty `heartbeat-url` is accepted. `shellcheck -S error` on all deploy scripts: clean. `yaml.safe_load` on compose and litestream.yml: ok. `pytest tests/test_backup_offsite.py tests/test_env_guard.py`: 19 passed. Docker is not available here, so `docker compose config` was not run.

## Deviations from the spec and why
- No client-side encryption: Litestream 0.5.x rejects the `age:` block at startup since 0.5.1 (docs, Configuration File, Encryption). The replica relies on SSE-S3, Block Public Access and a dedicated IAM user. Document and visa numbers, signatures, TOTP secrets and UbyPort passwords are encrypted inside the database with a key that is not in the database. Guest names and dates are in the replica in the clear, as in the live file.
- No PRAGMA change. The app already uses WAL, `foreign_keys=ON` and a 30 s busy timeout (`timeout=30`, above the 5 s Litestream recommends). `wal_autocheckpoint=0` is only recommended for very high write load, and `synchronous=NORMAL` is optional.
- `retention.enabled: true` (Litestream deletes old LTX files), so the IAM user needs `s3:DeleteObject`, as the spec lists. Bucket versioning with a 30-day non-current expiry still protects against a leaked key deleting history.
- The count check allows the restored count to lie between the live counts read before and after the restore, because the app keeps writing during the drill. A plain equality check would fail at random.
- `restore.sh` now also stops Litestream: restoring an older file under a live replica would mix two histories under one prefix. After any restore the runbook switches `LITESTREAM_S3_PATH` to a new prefix.

## What Cursor must verify or adapt when applying on the real main
- Run `docker compose config` in `deploy/lightsail` with a filled `.env`.
- Confirm the database path in production is `/data/ubyhost.db` (compose passes `${UBYHOST_DB:-/data/ubyhost.db}`).
- If a newer 0.5.x is out, re-pin both tag and digest together (`docker buildx imagetools inspect litestream/litestream:<tag>`).
- Passport photos (`/data/passport_photos`) and the secret key are not in the replica. The README says so. Keep it that way.

## Manual steps for the owner
1. S3, eu-central-1: create bucket `ubyhost-litestream-<suffix>`. Turn on Block all public access, versioning, and default encryption SSE-S3.
2. Lifecycle rule on the whole bucket: permanently delete non-current versions after 30 days, and delete expired delete markers. Do not add a rule that expires current versions.
3. IAM user `ubyhost-litestream`, no console access, inline policy (replace the bucket name):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "ListReplicaPrefix", "Effect": "Allow", "Action": "s3:ListBucket",
     "Resource": "arn:aws:s3:::ubyhost-litestream-SUFFIX",
     "Condition": {"StringLike": {"s3:prefix": ["ubyhost/*", "ubyhost"]}}},
    {"Sid": "ReadWriteReplicaObjects", "Effect": "Allow",
     "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
     "Resource": "arn:aws:s3:::ubyhost-litestream-SUFFIX/ubyhost/*"}
  ]
}
```
4. Create an access key for that user. On the server, set `LITESTREAM_S3_BUCKET`, `LITESTREAM_ACCESS_KEY_ID` and `LITESTREAM_SECRET_ACCESS_KEY` in `.env`, and keep `LITESTREAM_S3_PATH=ubyhost/production`.
5. Optional: create a healthchecks.io check (period 5 min, grace 10 min) and put its URL in `LITESTREAM_HEARTBEAT_URL`.
6. Make sure `UBYHOST_SECRET_KEY` (or the contents of `/data/secret_key`) is saved in the password manager. Without it, a restored database cannot decrypt anything.
7. Deploy, then run `docker compose logs --tail=30 litestream` (expect `snapshot complete`) and `./scripts/restore_test.sh`. Run the drill again once per quarter.
