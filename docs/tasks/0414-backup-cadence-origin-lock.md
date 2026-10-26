# 0414: Backup cadence, Cloudflare-only origin, fresh-instance restore from Litestream

Status: review
Depends on: none | Base commit: 838bec1 | Branch: task/0414-backup-cadence-origin-lock
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Cut backup cost by taking Litestream snapshots and validation once a day instead of every 6 hours, and make Caddy refuse connections that do not come from Cloudflare. Document how to rebuild production on a fresh Lightsail instance from the Litestream replica, with the secret key from the owner's password manager.

## 2. Context

- Owner decision (2026-10-26, architecture review): backups run too often and cost too much; origin must not be reachable around Cloudflare; the fresh-instance restore must be written down and drilled. The secret key is kept in the owner's password manager (Bitwarden).
- `deploy/lightsail/litestream.yml` today:

```
# A full snapshot every 6 hours keeps a restore short (fewer LTX files to
# replay); snapshots and the LTX files between them are kept for 7 days, so a
# point-in-time restore can go back a week. Durations accept s, m and h only.
snapshot:
  interval: 6h
  retention: 168h
```

```
# Check the replica's LTX chain for gaps and overlaps a few times a day.
validation:
  interval: 6h
```

- `deploy/lightsail/caddy/Caddyfile.cloudflare` lines 19-20 (the site block starts here; lines are tab-indented):

```
{$UBYHOST_DOMAIN} {$UBYHOST_APP_DOMAIN} {
	tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin-key.pem
```

- In Caddy, `remote_ip` matches the TCP peer address; `client_ip` is the forwarded address. The peer of every real request is a Cloudflare edge, so `not remote_ip <Cloudflare ranges>` matches only direct hits. `abort` closes the connection with no response. `deploy/lightsail/caddy/Caddyfile.acme` (no Cloudflare) must not change.
- `docs/LIGHTSAIL.md` section `### Restore onto a **new** Lightsail instance` (line 248) restores from a Drive copy only, and step 2 does not warn that `deploy.sh` generates a NEW `UBYHOST_SECRET_KEY` when `.env` leaves it empty, which would make the restored data unreadable.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/litestream.yml` | edit | snapshot and validation every 24h |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | abort non-Cloudflare peers |
| `docs/LIGHTSAIL.md` | edit | backup layers table; new-instance restore from Litestream; key warning |
| `docs/tasks/0414-report.md` | create | report |

No other file may change.

## 4. Steps

1. In `deploy/lightsail/litestream.yml`, replace the 6-line snapshot excerpt above with exactly:

```
# A full snapshot once a day: a restore replays at most one day of LTX files,
# which takes seconds at this database's size. 0414: a snapshot every 6 hours
# stored four full copies a day in S3 for little gain. Snapshots and the LTX
# files between them are kept for 7 days, so a point-in-time restore can go
# back a week. Durations accept s, m and h only.
snapshot:
  interval: 24h
  retention: 168h
```

   Command: `grep -n "interval: 24h" deploy/lightsail/litestream.yml 2>&1 | tail -30` → one line.

2. In the same file, replace the 3-line validation excerpt with exactly:

```
# Check the replica's LTX chain for gaps and overlaps once a day. 0414: each
# check reads the replica back from S3 (requests plus transfer to Lightsail),
# so every 6 hours cost four times as much for no faster recovery.
validation:
  interval: 24h
```

   Command: `grep -c "interval: 24h" deploy/lightsail/litestream.yml 2>&1 | tail -30` → `2`.

3. In `deploy/lightsail/caddy/Caddyfile.cloudflare`, directly after the line `	tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin-key.pem` (line 20), insert these lines (one leading TAB each, matching the file):

```
	# 0414: only Cloudflare may reach the app. A request straight to the
	# server's IP would skip Cloudflare's WAF, bot checks and rate limits.
	# remote_ip is the TCP peer, not the forwarded client IP. Same ranges as
	# trusted_proxies above: when Cloudflare publishes new ones, update both.
	@not_cloudflare not remote_ip 173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32
	abort @not_cloudflare
```

   Command: `python3 -c "import re;t=open('deploy/lightsail/caddy/Caddyfile.cloudflare').read();a=re.search(r'trusted_proxies static (.*)',t).group(1).split();b=re.search(r'not remote_ip (.*)',t).group(1).split();print('same' if a==b else 'DIFFERENT')" 2>&1 | tail -30` → `same`.

4. In `docs/LIGHTSAIL.md`, directly after the line `Passport photos are **not** in the DB backup. After restore, unverified uploads may be missing; hosts re-check IDs if needed.` insert a blank line and then:

```
**Backup layers (0414).** One continuous copy, one quick local copy and one independent copy are enough:

| Layer | How often | Kept | Used for |
|---|---|---|---|
| Litestream → S3 | continuous (10 s), full snapshot daily, check daily | 7 days | main recovery, including a new instance |
| `backup.sh` on the volume | daily 03:00 UTC | `UBYHOST_BACKUP_RETENTION_DAYS` (set `7` in production `.env`) | quick restore on the same server |
| `backup-gdrive.sh` | weekly | 30 days | copy outside AWS |
| Lightsail automatic snapshots | daily | 7 | optional; they copy the whole disk, including every local backup, and are billed per GB on top of the bundle |
```

   Command: `grep -n "Backup layers (0414)" docs/LIGHTSAIL.md 2>&1 | tail -30` → one line.

5. In `docs/LIGHTSAIL.md`, replace the line `2. Copy `.env` (do not commit it) and `caddy/certs/origin*.pem` from the old host or a secrets store.` with:

```
2. Copy `.env` (do not commit it) and `caddy/certs/origin*.pem` from the old host or a secrets store. **Before the first deploy**, set `UBYHOST_SECRET_KEY` in `.env` to the production key from the password manager: with it empty, `deploy.sh` generates a new key and the restored guest data and UBY-WS passwords cannot be decrypted.
```

   Command: `grep -n "Before the first deploy" docs/LIGHTSAIL.md 2>&1 | tail -30` → one line.

6. In `docs/LIGHTSAIL.md`, replace the line `5. Place backup files on the host (from Drive): `ubyhost.db` and `secret_key`.` with:

~~~~
5. Restore the database. **From Litestream (preferred, newest data):** `.env` must have the `LITESTREAM_*` values and `COMPOSE_PROFILES=litestream`. Then:

```bash
docker compose stop worker litestream
docker compose run --rm --no-deps -T --entrypoint sh litestream -c \
  'rm -rf /data/ubyhost.db /data/ubyhost.db-wal /data/ubyhost.db-shm /data/.ubyhost.db-litestream &&
   litestream restore -config /etc/litestream.yml -o /data/ubyhost.db "$LITESTREAM_DB_PATH"'
```

   Then go to step 7. **From a Drive copy instead:** place `ubyhost.db` and `secret_key` on the host and run:
~~~~

   (The existing ```bash block that follows, which copies from `/backup`, stays as it is.)

   Command: `grep -n "From Litestream (preferred" docs/LIGHTSAIL.md 2>&1 | tail -30` → one line.

7. In `docs/LIGHTSAIL.md`, directly after the line `8. Point Cloudflare A record at the **new** static IP. Keep Full (strict).` insert a blank line and then:

```
**Rebuild drill (once a quarter).** Run steps 1 to 7 on a throwaway instance, skip step 8, sign in through `curl --resolve` or a hosts-file entry, and note how long it took in [status](context/status.md). Delete the instance afterwards. The drill proves the replica, the `.env` copy and the password-manager key together; `restore_test.sh` only proves the replica.
```

   Command: `grep -n "Rebuild drill" docs/LIGHTSAIL.md 2>&1 | tail -30` → one line.

8. Run the tests in §6, write the report, commit.

## 5. Do not touch

`deploy/lightsail/caddy/Caddyfile.acme`, `docker-compose.yml`, every script, `App/`. Never commit `.env`, keys or IPs. Never push, merge or deploy.

## 6. Commands

From the repo root:

- `python3 scripts/context_lint.py 2>&1 | tail -30` → no errors.
- From `App/`: `.venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_backup_data.py -q --tb=short -x 2>&1 | tail -30` → all pass. (If `.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt 2>&1 | tail -5` first.)

## 7. Acceptance

- [ ] `litestream.yml` has `interval: 24h` twice and no `interval: 6h`.
- [ ] Caddy `not remote_ip` list equals the `trusted_proxies` list (step 3 command prints `same`).
- [ ] `docs/LIGHTSAIL.md` has the backup layers table, the key warning, the Litestream restore and the drill paragraph.
- [ ] §6 tests pass.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, you reach 25 tool calls or about 50k tokens, a file outside §3 needs a change, or a step is unclear.

## 9. Report

Write `docs/tasks/0414-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Commit; the orchestrator pushes and opens the PR.

## Risk list (for the reviewer)

`deploy/lightsail/caddy/Caddyfile.cloudflare` (a wrong range locks out real users), `deploy/lightsail/litestream.yml`.

## Owner steps

1. After merge and deploy, open `https://ubyhost.com` in a browser: it loads as before.
2. From your laptop run `curl -sk --max-time 10 https://<server static IP>/healthz -H "Host: ubyhost.com"`: it must fail with an empty reply or a reset, not answer `ok`.
3. In the production `.env` on the server set `UBYHOST_BACKUP_RETENTION_DAYS=7` if it still says 30.
4. Keep Lightsail automatic snapshots on (owner decision 2026-10-26): they are the only copy of the whole server.
5. In the S3 bucket's lifecycle rule, consider expiring non-current versions after 7 days instead of 30.
6. Once a quarter, run the rebuild drill in `docs/LIGHTSAIL.md`.
