# Report 1451: Go scheduler switch

Status: review
Branch: the executor worktree branch (one big PR mode; no push, no PR).

## 1. Files changed

- `3596b657e 1451 step 1`: `App/app/scheduler.py` (185 lines), `deploy/lightsail/docker-compose.yml` (7), `docs/ENVIRONMENT.md` (3), `go/cmd/ubyhost-web/register_scheduler.go` (16). Total 209 insertions, 2 deletions.
- `8c8006cc2 1451 step 2`: `App/tests/test_scheduler_go_switch.py`, `go/cmd/ubyhost-web/register_scheduler_kill_test.go` (new).
- `1451 report`: this file, and the brief's Status line set to `review`.

## 2. Commands (last lines of output)

- Step 0: `sha256sum -c` on the three files of `docs/tasks/1451-files/`: three `OK` lines. `git apply --check` on `1451.patch`: no output (passed). Anchors: `registerBackground(` in `registry.go` = 1, `func Enabled(...)` in `scheduler.go` = 1, `def go_scheduler` in `scheduler.py` = 0. Worktree status was empty.
- Step 1: `git apply` then `git diff --stat`: `4 files changed, 209 insertions(+), 2 deletions(-)`, as expected.
- Step 2: `git status --short`: two `??` lines for the new test files, as expected.
- Test run, SQLite (`tests/test_scheduler_go_switch.py tests/test_scheduler.py tests/test_worker.py`): `33 passed, 8 skipped in 9.43s`. The 8 skips are the watch tests ("needs UBYHOST_DATABASE_URL"). No failures.
- Test run, PostgreSQL 16 (disposable server on port 5608, data in `/var/tmp/pg1451`, stopped and removed afterwards; `UBYHOST_DATABASE_URL` pointed at a throwaway test database): `tests/test_scheduler_go_switch.py` alone: `16 passed in 4.46s`. The three files together: `41 passed in 31.19s`, 0 skipped.
- Compose grep: `5`. ENVIRONMENT grep: `1`.
- `gofmt -l`: no output. `go vet ./cmd/...`: no output. `go test -run 'KillSwitch|Scheduler' ./cmd/ubyhost-web/`: `--- PASS` for `TestKillSwitchStopsTheGoScheduler`, `TestSchedulerIsRegisteredAsBackgroundTask`, `TestSchedulerTaskSetup`, `TestSchedulerCoversEveryGoKind`, then `ok`.
- `go test ./internal/scheduler/ ./cmd/ubyhost-web/`: two `ok` lines.
- `python3 scripts/context_lint.py`: `context lint: OK`. Its WARN lines are about other open briefs (1451 among them on ENVIRONMENT.md); no error names 1451.

## 3. Section 7 acceptance

- [x] Commit subjects `1451 step 1`, `1451 step 2`, `1451 report` exist.
- [x] Step 1 touches only the four patched files.
- [x] The brief's test files are byte-identical copies of the checksummed originals (checked by `sha256sum`).
- [x] Section 6 output as stated (counts above). The PostgreSQL run exceeds the brief's minimum (`16 passed`) and also covers the other two files.

## 4. Deviations

- Step 0 `git` commands were split into single commands and the `cd docs/tasks/1451-files && sha256sum` block was run with absolute paths in a checksum file in the scratchpad. The worktree guard refused the compound forms. Checks and hashes were the same.
- The brief's "Owner steps" are appended below unchanged, copied from the brief's section (lines 446 to 480). The report is longer than the 600-token limit of section 9, because section 9 item 6 requires those steps verbatim.
- Python venv was created at `App/.venv` (not committed).

## 5. Questions

None.

## 6. Owner steps left

The change is off until the owner sets the variable. The owner steps below are copied unchanged from the brief.

Do these only after 1452, 1450 and 1451 are merged and deployed (`./scripts/deploy.sh` as usual). Pick a quiet time that is not between 03:00 and 07:30 Prague time (the daily jobs run then). Keep the server terminal open for 20 minutes. Every `docker compose up` below has `--no-deps`: without it, Docker would also restart the web container (`ubyhost`), because it reads the same `.env` file. With `--no-deps` only the one named container restarts. The web container picks up the new line at the next normal deploy, and it does not use it.

**Switch to Go**

1. Open a terminal on the server and run `cd /opt/ubyhost/deploy/lightsail`.
2. Run `git -C /opt/ubyhost log -1 --oneline` and check that the merge with 1451 (or a later one) is shown. If not, deploy first.
3. Run `grep -E '^UBYHOST_(JOB_QUEUE_KINDS|GO_JOB_KINDS|SCHEDULER|SUBMIT_SWEEP_MINUTES|ICAL_POLL_MINUTES)=' .env`. The `UBYHOST_JOB_QUEUE_KINDS` line must contain all 15 names: `ical submit deadlines mail photo_sweep meta_capi retention stay_fee_mail stripe_sweep billing billing_snapshot door_codes posthog push guide_import`. There must be no `UBYHOST_SCHEDULER` line yet. If a name is missing, stop and send the output to the orchestrator: moving a kind onto the queue is a separate step.
4. Run `date -u +%Y-%m-%dT%H:%M:%S` and write the time down (below: START).
5. Run `nano .env`, add the line `UBYHOST_SCHEDULER=go` at the end, save with Ctrl+O and Enter, and close with Ctrl+X.
6. Start Go first: `docker compose up -d --no-deps ubyhost-go`. For about a minute both sides enqueue; that is harmless.
7. Wait 90 seconds, then run `docker compose logs --since 3m ubyhost-go 2>&1 | grep -E 'background task|scheduler (started|enqueued|enqueue failed)' | tail -8`. You must see `background task started task=scheduler`, `msg="scheduler started" owner=go kinds=15 timezone=Europe/Prague`, and `msg="scheduler enqueued"` lines (`job=ical` and `job=photo_sweep` about 20 seconds after the start, `job=push` within about a minute). If you see `background task not started task=scheduler`, the line explains why. Then do the rollback below and send the output to the orchestrator.
8. Now stop Python enqueuing: `docker compose up -d --no-deps worker`.
9. Wait 60 seconds, then run `docker compose logs --since 2m worker 2>&1 | grep -E 'UBYHOST_SCHEDULER=go|Go scheduler|Error' | tail -5`. You must see `UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none`, and no `is ignored` line and no error. Then run `docker compose ps`: `worker` and `ubyhost-go` show `Up`, and after two minutes `worker` shows `(healthy)`. The `ubyhost` line still shows its old "Created" time (it was not restarted).
10. Wait 15 minutes, then check the queue (replace START with the time from step 4): `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT kind, count(*) AS rows, count(*) FILTER (WHERE done_at IS NOT NULL) AS done, count(*) FILTER (WHERE dead_at IS NOT NULL) AS dead FROM job WHERE created_at >= 'START' GROUP BY kind ORDER BY kind;"`. Expected, roughly: `push` about 15 rows; `mail` and `door_codes` about 3 each; `submit` and `meta_capi` 1 or 2; `posthog` about 1; `ical` and `photo_sweep` 1; `deadlines` 0 or 1. `done` is close to `rows` (the newest row of a kind may still be open), and `dead` is 0 everywhere. `door_codes` and `mail` being done proves Python still runs the kinds Go does not.
11. Check that the Python safety net is quiet: `docker compose logs --since 20m worker 2>&1 | grep -c 'Go scheduler is not enqueuing'` prints `0`. In the app, the dashboard shows no red card "Background job 'job queue' failed".
12. The next morning, after 07:15 Prague time, run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT kind, created_at FROM job WHERE kind IN ('retention','stripe_sweep','billing','billing_snapshot','stay_fee_mail') ORDER BY id DESC LIMIT 5;"`. Each of the five must appear once with today's date. The `created_at` is in UTC: in winter 02:30, 03:15, 05:00, 05:15 and 06:00, which is 03:30, 04:15, 06:00, 06:15 and 07:00 Prague time; in summer each is one hour earlier in UTC. Also open the admin Operations page: no job is shown as late.
13. Send the orchestrator the outputs of steps 7, 9, 10 and 12. After one clean week, a later brief removes the worker's enqueue code (not part of this brief).

**If the red card "Background job 'job queue' failed" appears after the switch**

It means the Go service stopped writing some jobs, and the Python worker took them over, so they still run on time. The card closes by itself within about a minute after the Go service writes jobs again, also if the worker restarted meanwhile.

1. Open the admin Operations page. The alert there names the jobs and the first step, for example `Go scheduler is not enqueuing any job. First check that the ubyhost-go container is running (docker compose ps ubyhost-go on the server).`
2. On the server run `cd /opt/ubyhost/deploy/lightsail` and then `docker compose ps ubyhost-go`.
3. If it does not show `Up`, the jobs the Go service runs (filing among them) wait for it. Run `docker compose logs --tail 50 ubyhost-go`, send the output to the orchestrator, and do the rollback below now.
4. If it shows `Up` and the card stays more than 10 minutes, send the orchestrator the output of `docker compose logs --since 15m ubyhost-go 2>&1 | grep -E 'background task|scheduler' | tail -10`.

**Rollback** (any time; about 2 minutes)

1. Run `cd /opt/ubyhost/deploy/lightsail`, then `nano .env`. Delete the line `UBYHOST_SCHEDULER=go`, save with Ctrl+O and Enter, and close with Ctrl+X.
2. Start Python first: `docker compose up -d --no-deps worker`. Wait 60 seconds, then `docker compose logs --since 2m worker 2>&1 | grep -E 'scheduler started|UBYHOST_SCHEDULER=go' | tail -3` must show `scheduler started (ical every 60 min, submit every 10 min)` (your own minutes if you changed them) and no `UBYHOST_SCHEDULER=go` line.
3. Then stop Go enqueuing: `docker compose up -d --no-deps ubyhost-go`. Wait 30 seconds, then `docker compose logs --since 1m ubyhost-go 2>&1 | grep -c 'scheduler started'` must print `0`.
4. After 15 minutes, run the query of step 10 again with a new START: the same kinds keep getting rows. After a rollback the watch no longer runs, so a card it left open stays. Close it with `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "UPDATE alert SET resolved_at = to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS') || '+00:00' WHERE dedupe_key = 'job_failed:job_queue' AND resolved_at IS NULL AND message LIKE 'Go scheduler%';"`. It prints `UPDATE 1`, or `UPDATE 0` when there was none. Tell the orchestrator.
