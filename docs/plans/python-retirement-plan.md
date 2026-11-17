# Python retirement plan (owner + SSH AI)

Written 2026-11-17 from `main` (`336acd2`) and the project notes of 11-16. Docs only: nothing here was run. Where a fact could not be read from the repository it says **UNVERIFIED** and the SSH AI checks it first (step R0).
Companion: [SQLite retirement plan](sqlite-retirement-plan.md) (same dates, same owner). Decisions already made: [go-sqlite-final §6](go-sqlite-final.md), [sqlite-retirement §7](sqlite-retirement.md). Briefs this plan runs: [1780](../tasks/1780-go-ops-scripts-subcommands.md), [1781](../tasks/1781-stripe-webhook-path-decision.md), [1790](../tasks/1790-route-completeness-gate.md), [1782](../tasks/1782-go-caddy-everything-to-go.md), [1479](../tasks/1479-delete-sqlite-runtime.md).

## 0. Read this first

**Goal:** the `ubyhost` (web) and `worker` containers leave compose, Caddy sends every path to Go, and `App/` is deleted from the repo. `/dev/ui` dies with Python (decision 3, 11-15).

**What Python still does today (read from the repo, so check it on the server in R0):**

| Python still does | Where it shows | Must be replaced before the container leaves |
|---|---|---|
| Runs every backup: `backup.sh` calls `backup_data.sh` inside the `ubyhost` container (age-encrypts the snapshot and the `secret_key`); `backup-s3.sh` and `backup-gdrive.sh` list `/data/backups` with `docker compose exec ubyhost` | `deploy/lightsail/scripts/backup*.sh` | brief 1780 (ops scripts as Go subcommands) **plus** a shell backup of `secret_key` that does not need Python |
| Runs deploy checks: `deploy.sh` execs `ubyhost` for counts, secret-key check, `migrate_encrypt_doc_fields.py`, `backfill_legal_acceptance.py`, and waits for `worker.alive` | `deploy.sh` lines 130-470 | 1780 plus a `deploy.sh` without those calls (part of 1782) |
| Restores backups: `pg-restore.sh` stops and starts `worker ubyhost` and runs a one-off `ubyhost` container | `pg-restore.sh` 72-95 | 1780 / 1782 (same PR) |
| Receives Stripe booking events forwarded by Go (`UBYHOST_PY_WEBHOOK_URL`) and keeps `/webhooks/stripe` | compose `ubyhost-go` env, [1781](../tasks/1781-stripe-webhook-path-decision.md) | brief 1554 (booking events on Go) and Stripe out of test mode |
| Serves every route not yet on Go, by Caddy default upstream | `Caddyfile.cloudflare` line 113 and 136 | the 1790 allow-list is empty, or each remaining line is a decision "drop" signed by Josef |
| Is scraped by monitoring (`ubyhost:8080`) | `monitoring/config.alloy:65` | 1782 removes the target |
| Holds the SQLite rollback (`pg-cutover.sh` starts Python on SQLite) | plan S11 | **Python stays until the SQLite rollback ends on 2026-12-15** |

**Hard ordering rule:** the Python containers are the SQLite rollback path. They are not removed before 2026-12-15 and the SQLite S11 PR ([1476](../tasks/1476-end-sqlite-rollback-path.md)). Before that day they may be made idle and dark (stages 1 and 2), not deleted.

**Not proven on Go yet (11-17), each is a gate:** first real police filing (not apartment 7), first `billing` and `stay_fee_mail` runs (11-18 06:00 and 07:00 Prague), `guide_import`, guest-code lifecycle of door codes, one real invoice, SES mail at volume. Retention is Go dry-run only; the purge is Josef's decision and is not part of this plan.

## 1. Who does what

| Who | Does |
|---|---|
| **SSH AI** (Josef pastes the block) | every step marked SSH: reads, edits `.env`, runs `docker compose`, writes `RETIREMENT_STATE` file (below) |
| **Orchestrator** (Claude) | writes the exact-diff passes of 1780, 1782, 1790; reviews; never touches the server |
| **Haiku executor** | runs one brief at a time (1780, 1790, 1782, 1479) |
| **Josef** | merges, browser checks, the go/no-go decisions marked OWNER, deletes nothing on the server himself |

State file for the SSH AI: `/opt/ubyhost/retirement-state.md` (no secrets): one line per step, `kept`, `rolled back`, or `skipped` with date and time. Each paste starts by reading it and never repeats a `kept` step.

## 2. Timeline

| Date (Prague) | Step | Gate |
|---|---|---|
| Tue 11-17 | R0 inventory (read only) | none |
| Wed 11-18 | Watch: first `billing` 06:00, `stay_fee_mail` 07:00; check the four unproven items | W1 |
| 11-18 to 11-30 | Briefs 1790, 1780, 1781 exact-diff pass and PRs; first real filing observed | G1, G2 |
| by Fri 11-27 | Ops scripts off Python deployed (1780): stage A | G3 |
| Mon 11-30 | Stage 1: stop the Python `worker` | G4 |
| Mon 12-07 | Stage 2: Caddy default upstream to Go, Python idle as cold fallback | G5 |
| **Tue 12-15** | SQLite rollback ends ([SQLite plan](sqlite-retirement-plan.md) S11) | G6 |
| Wed 12-16 to Fri 12-18 | Stage 3: `ubyhost` leaves compose, image kept (1782) | G7 |
| 12-18 to 12-25 | Quiet week | none |
| Mon 12-28 | End of quiet week (stage 4); PR 1479 may be opened as a draft | G8 |
| **on or after Mon 2027-01-18** | Stage 5: merge 1479, `App/` deleted (30 days after the stage 3 deploy, rounded up) | G9 |
| 2027-01-18 + 30 days | delete the kept Python image tag (2027-02-17) | none |

If a gate fails, the next date moves one day per day of delay. The SQLite dates in the companion plan move with it only where the table says so.

## 3. Go and no-go gates

| Gate | Passes when | How checked |
|---|---|---|
| W1 | `billing` ran at 06:00 and `stay_fee_mail` at 07:00 on 11-18 on Go, status ok, with no `job_failed` alert; an invoice or mail produced matches what Python produced the previous month (counts, not values) | SSH AI: job-run table, Alerts page; OWNER looks at `/admin/fakturace` and one stay-fee mail in his own inbox |
| G1 | `guide_import` ran once from a real host action on Go; photo sweep ran | SSH AI: logs; OWNER one guide import |
| G2 | **One real police filing** (not apartment 7) went through Go submit with outcome known, and no `submission_outcome_unknown` alert is open | OWNER names the stay; SSH AI reads submission row state and the Alerts page |
| G3 | 1780 merged and deployed; `backup.sh`, `backup-s3.sh`, `backup-gdrive.sh` produce a fresh encrypted snapshot **with the `ubyhost` and `worker` containers stopped** (tested on a quiet night, see 5.1) and `secret_key` is in it | SSH AI test, then the next 03:30 log shows ok |
| G4 | G1, G2, W1 passed; all 15 job kinds each ran at least once on Go (SSH AI list); 7 days with no stalled-queue alert | SSH AI |
| G5 | 1790 gate in CI: allow-list is empty, or each remaining line has Josef's "drop" in the PR; `/webhooks/stripe` question of 1781 decided (see 7); Caddy `X-Ubyhost-Not-Ported` fallback count in the last 7 days is 0 for real users | SSH AI: Caddy fallback and `ubyhost` container request logs; OWNER browser tour (10 pages) |
| G6 | SQLite plan S11 merged; the four backup proofs recorded | companion plan |
| G7 | 5 quiet days after stage 2: Python `ubyhost` access count for real paths is 0 | SSH AI |
| G8 | Quiet week after stage 3: no rollback used, no 5xx beyond baseline, backups ok 7 of 7 nights | SSH AI |
| G9 | At least 30 days since the stage 3 deploy; Josef says "delete App/" in the thread | OWNER |

## 4. Steps

### R0. Inventory (SSH AI, read only, today)

Purpose: replace the **UNVERIFIED** items above with facts. Paste:

```
You are the server operator for UbyHost. READ ONLY today: change nothing, restart nothing.
Report in 25 lines, no secrets, no values of variables (names and yes/no only).
1. cd /opt/ubyhost/deploy/lightsail; docker compose ps; cat .go-slot; grep -c . /opt/ubyhost/retirement-state.md 2>/dev/null
2. Names only of: UBYHOST_GO_PATHS (count of words), UBYHOST_GO_JOB_KINDS, UBYHOST_JOB_QUEUE_KINDS, UBYHOST_SCHEDULER, UBYHOST_SCHEMA_APPLY, UBYHOST_PY_WEBHOOK_URL (set yes/no), UBYHOST_ENABLE_SCHEDULER, COMPOSE_PROFILES.
3. Python web container: how many requests did it serve in the last 24 h and last 7 days (docker compose logs --since 24h ubyhost | grep -c ' HTTP/' ), top 15 paths with counts, and how many are real users versus /healthz and monitoring.
4. Caddy fallbacks: count of responses with X-Ubyhost-Not-Ported in the last 24 h, per path (Caddy log if on; else say "log off").
5. Python worker: docker compose logs --since 24h worker | tail -20 (job lines only). Is it doing anything while UBYHOST_SCHEDULER=go?
6. Backup chain: which container each of backup.sh, backup-s3.sh, backup-gdrive.sh, walg-backup.sh needs (grep "compose exec\|compose run"); last 3 lines of /var/log/ubyhost-s3.log; the newest folder name in /data/backups; does it hold secret_key (names only: tar -t of the .age is NOT allowed here, just ls).
7. Images: docker images | grep -E 'ubyhost' (names, tags, sizes) and whether ubyhost:previous exists. df -h / | tail -1.
8. Disk of the ubyhost-data volume: du -sh of the volume, split /data/backups versus the rest.
9. Anything in cron or systemd that names ubyhost, worker, or python (crontab -l; ls /etc/cron.d; systemctl list-timers | grep -i ubyhost).
Write the answers to /opt/ubyhost/retirement-r0-2026-11-17.md (no secrets) and print it.
```

Go/no-go: Josef reads it. Rollback: none needed (read only).

### Stage A. Make everything that needs Python independent of it (before any container change)

| # | Who | Step | Check | Rollback |
|---|---|---|---|---|
| A1 | Orchestrator, Haiku | Brief 1790 (route gate) exact-diff pass, merge. It shows the real list of routes Python still owns. | CI test green, allow-list file in the repo | revert PR |
| A2 | Orchestrator, Haiku | Brief 1780: backup, restore and deploy helpers become `ubyhost-web` subcommands or plain shell that runs in the `ubyhost-go` container, which already mounts `/data` writable (1640). **Scope addition to 1780:** the `secret_key` and age encryption of `backup_data.sh`; `backup-s3.sh` and `backup-gdrive.sh` use `exec ubyhost-go`; `pg-restore.sh` stops only Go services; `deploy.sh` loses `ubyhost` and `worker` calls except behind `if docker compose ps -q ubyhost`. | `shellcheck` green, new test of each script against a compose with no `ubyhost` | revert PR; scripts return to Python |
| A3 | Josef | Merge 1780 (draft PR to ready; merge script) | CI green | revert |
| A4 | SSH AI | Deploy the normal way; then run the proof below. | proof prints `BACKUP INDEPENDENT OK` | `git revert` deploy |
| A5 | Orchestrator | Brief 1781: write the Stripe webhook decision (see 7). | doc merged | n/a |

Proof for A4 (paste; it stops Python for about 2 minutes on a quiet moment, outside 03:00-07:30 Prague, and starts it again):

```
cd /opt/ubyhost/deploy/lightsail
echo "A4 start $(date -Is)" >> /opt/ubyhost/retirement-state.md
docker compose stop worker ubyhost
./scripts/backup.sh 2>&1 | tail -5
./scripts/backup-s3.sh 2>&1 | tail -5
./scripts/backup-gdrive.sh 2>&1 | tail -5
docker compose start ubyhost worker
docker compose ps | grep -E 'ubyhost|worker'
# newest snapshot names only
docker compose exec -T ubyhost-go sh -c 'ls -1 /data/backups | sort | tail -1; ls /data/backups/$(ls -1 /data/backups | sort | tail -1)'
```
Expected: three scripts end without error, newest folder is today and holds `ubyhost-pg.dump.age` and `ubyhost-backup.tar.age`; both containers Up again. Any error: say `A4 NO-GO`, leave everything started, stop. Rollback: containers are started again; nothing else changed.

### Stage 1. Stop the Python worker (Mon 11-30, gate G4)

Why safe: `UBYHOST_SCHEDULER=go` and all 15 kinds are on Go since 11-16; the worker should have no work (confirm in R0 item 5). Why it matters: it removes the last Python writer of background rows.

```
cd /opt/ubyhost/deploy/lightsail
read the state file; stop if "stage1" is already kept.
PRECHECK: grep -E '^(UBYHOST_SCHEDULER|UBYHOST_JOB_QUEUE_KINDS)=' .env (names and count only: SCHEDULER=go, 15 kinds).
Not between 03:00 and 07:30 Prague. Backup first: ./scripts/backup.sh 2>&1 | tail -3
docker compose stop worker
docker compose ps | grep worker      # Exited
WAIT 10 min, then: docker compose logs --since 10m ubyhost-go 2>&1 | grep -ciE 'error|panic'   # at most 3 error lines, 0 panics
Check the Alerts page count is not higher than before (ask Josef for a screenshot or read the alerts table, count only).
Write "stage1 kept <date>" to the state file.
Keep it stopped (not removed) for 7 days. The next 06:00, 07:00 and 03:30 runs must be ok.
```
Rollback: `docker compose start worker`. Change no scheduler variable: with `UBYHOST_SCHEDULER=go` the worker idles, so starting it is harmless. If a job runs twice, stop and ask the orchestrator.

### Stage 2. Caddy default upstream to Go; Python idle (Mon 12-07, gates G5)

1. Orchestrator/Haiku: **first half of 1782 only**: both Caddyfiles use Go as default upstream; `UBYHOST_GO_PATHS` stays in the file but is no longer needed; the `ubyhost` service stays in compose; `X-Ubyhost-Not-Ported` fallback stays (so a route Go lacks still reaches Python as GET). Split 1782 in two briefs (1782a: Caddy; 1782b: compose and scripts) in its exact-diff pass.
2. Josef merges 1782a. SSH AI deploys with the normal deploy.
3. SSH AI paste:

```
cd /opt/ubyhost/deploy/lightsail
./scripts/caddy-validate.sh 2>&1 | tail -5     # must end without error
Note the current .env UBYHOST_GO_PATHS line in the state file (rollback).
docker compose up -d caddy
./scripts/smoke-remote.sh 2>&1 | tail -20
curl -sI https://<domain>/ | head -5            # Go served (header per brief 1630 if present)
For 5 days, each morning: count of requests that reached ubyhost (python) from real users = must be 0; count X-Ubyhost-Not-Ported answers per path.
WAIT 10 min soak as in stage 1; write "stage2 kept <date>".
```
OWNER: 10-page browser tour (login with passkey, dashboard, stays, a stay detail, invoices, `/stay-fees`, guest page with a test link, `/havel`, `/predplatne`, `/admin/fakturace`).
Rollback: put the noted Caddyfile back from git (revert 1782a), `docker compose up -d caddy`. Python is still running, so rollback is instant.

### Stage 3. The `ubyhost` container leaves compose (12-16 to 12-18, gates G6, G7)

Only after the SQLite S11 PR is merged (G6). Merge 1782b (compose without `ubyhost`, `worker`, `mock-ubyport` image reference, monitoring target, docs). Then SSH AI:

```
cd /opt/ubyhost/deploy/lightsail
Backup first; check the 03:30 log of the night before is ok.
Keep the last Python image, never prune it:
  docker tag ubyhost:local ubyhost:python-final-$(date +%Y%m%d)
  docker save ubyhost:python-final-$(date +%Y%m%d) | gzip > /opt/ubyhost/archive/ubyhost-python-final.tar.gz
  ls -l /opt/ubyhost/archive/ubyhost-python-final.tar.gz   # a few hundred MB; df -h / first, must stay below 70%
Deploy the normal way (it now runs the new deploy.sh): watch the whole deploy.
docker compose ps    # no ubyhost, no worker; ubyhost-go, caddy, postgres up
./scripts/smoke-remote.sh 2>&1 | tail -20
Run backup.sh once by hand; then check the monitoring dashboard shows no missing target.
docker image prune -f   # dangling only, NEVER -a
Write "stage3 kept <date>".
```
Rollback (until 12-25): `git revert` 1782b, `docker tag ubyhost:python-final-<date> ubyhost:local`, deploy, then stage 2 rollback. Because the SQLite rollback has ended, the rollback only brings Python back on PostgreSQL (UBYHOST_DATABASE_URL), never on SQLite.

### Stage 4. Quiet week and checks (12-18 to 12-28, gate G8)

SSH AI each morning writes one line: backups 03:30 ok, error count, alerts count, disk percent. OWNER: 3 browser checks mid-week. Any 5xx cluster: stop the clock (the 30-day window restarts from the fix).

### Stage 5. Delete `App/` (on or after 2027-01-18, gate G9)

Orchestrator writes the exact-diff pass of [1479](../tasks/1479-delete-sqlite-runtime.md) (it also does the SQLite S14 half, see the companion plan). It must also list: `Dockerfile` and `docker-entrypoint.sh`, `render.yaml` and `render_start.sh`, `requirements*.txt`, `.github/workflows/ci.yml` Python jobs, `scripts/py_routes.py`, `scripts/go_parity_check.py`, `scripts/e2e/diff_harness.py`, `AGENTS.md` test rows and `docs/context/test-map.md`. Rules of AGENTS.md (parity fixtures move to `go/testdata` first; no skip).
Josef merges after CI is green on Go and PostgreSQL only. After deploy: `smoke-remote.sh`, three pages. Rollback: revert the PR; `App/` returns from git; the Python image tag is still there.
Then on 2027-02-17 the SSH AI deletes the kept tag and the archive:
```
docker rmi ubyhost:python-final-<date>; rm /opt/ubyhost/archive/ubyhost-python-final.tar.gz; df -h / | tail -1
```

## 5. Notes for the SSH AI

1. Never `docker image prune -a`, `docker compose down -v`, or any volume command: `ubyhost-data`, `ubyhost-pgdata`, `ubyhost-walspool` hold real data.
2. Not between 03:00 and 07:30 Prague (backups and jobs).
3. Every `.env` line you change is copied first into the state file (names and values of switches only; never keys).
4. Container restarts you cannot explain (11-16: 21:26 and 22:22 UTC): record the time and the deploy log before and after; open question from the cutover.

## 6. Risks

| Risk | Prevented by |
|---|---|
| Backups stop silently when the Python container leaves | Stage A proof with containers stopped; the 03:30 log |
| `secret_key` no longer in the backup | A2 scope line; tar listing in proof (names only) |
| A route nobody ported (guest registration, stay edit) breaks | 1790 gate, G5, the 7-day not-ported count |
| Stripe booking events lost | G5 / section 7; never move `/webhooks/stripe` without 1554 |
| Python image pruned | named tag plus `docker save` archive, no `prune -a` |
| Disk full | `df` before saving the image; the image is a few hundred MB |
| Double-running jobs | stage 1 only stops the worker; never edit scheduler variables in this plan |

## 7. Decisions

1. **`/webhooks/stripe`** (open): it stays on Python until brief 1554 and Stripe leaves test mode ([1781](../tasks/1781-stripe-webhook-path-decision.md)). Python retirement cannot finish before 1554. Recommend 1554 before stage 3; if Stripe stays in test mode, stage 3 waits.
2. **Unported routes:** Josef 2026-11-17: decided later, at gate G5 when the 1790 allow-list shows the leftovers (port or drop per route).
3. **Staging:** none exists (Josef 2026-11-17). Every "staging" check in this plan runs on production with test accounts and the read-only variants given in the steps.
4. **Dates:** stage 5 is 30 days after the stage 3 deploy (decision 5, 11-15). The SQLite offline copy and server file both end 2027-01-14 ([SQLite plan](sqlite-retirement-plan.md)).
