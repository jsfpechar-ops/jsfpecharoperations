# 1451: Python side of `UBYHOST_SCHEDULER=go` (worker stops enqueuing), compose lines and ENVIRONMENT row; owner switch steps

Status: todo
Depends on: 1450 (merged) | Base commit: 34738084 plus the 1450 merge | Branch: task/1451-go-scheduler-switch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make `App/app/scheduler.py` enqueue nothing when `UBYHOST_SCHEDULER=go` (the Python `worker` then only drains the queued rows Python claims), pass the switch and the two variables the Go scheduler reads into `ubyhost-go`, and document the variable. With the variable unset nothing changes; the production switch is the owner steps at the end of this brief (plan step J7, tier A: filing and deadline timing).

## 2. Context

Rules (AGENTS.md): 1 filing correctness first: exactly one side enqueues, and during the switch and the rollback both may enqueue for a minute, never neither; 3 no secret in the repo (the compose lines are bare pass-through keys); 4 no new dependency; 5 no SQL and no schema change here.

**How the switch works.**
- Go (brief 1450, merged): with `UBYHOST_SCHEDULER=go` and every kind in `UBYHOST_JOB_QUEUE_KINDS`, `ubyhost-go` enqueues all 15 kinds and logs `scheduler started owner=go kinds=15`. Otherwise it logs `scheduler not started` (bad configuration) or nothing (switch off).
- Python (this brief): `go_scheduler()` reads the same variable with the same test (`"go"`, case and spaces ignored). When it is on, `start()` refuses unless every kind is in `UBYHOST_JOB_QUEUE_KINDS` (`RuntimeError`: the worker exits and Docker restarts it, so the problem is visible). It adds the 15 jobs as today, then removes them from the not yet started scheduler, keeps the 15 s `job_queue` drain and logs `UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none`. The worker stays healthy: `scheduler.running()` is true with only the drain job. `App/app/worker.py` needs no change.
- Why every kind must be queued: a kind outside `UBYHOST_JOB_QUEUE_KINDS` runs in-process in Python, and Python's `jobqueue.claim` takes any kind not in `UBYHOST_GO_JOB_KINDS`, so a Go row for it would run that job twice.
- Double enqueue: `job_one_open_per_kind` (`App/migrations_pg/00003_job.sql`) plus `ON CONFLICT ... DO NOTHING` on both sides allow one open row per kind. Both sides on at once write one row per kind at a time, and runs of one kind never overlap. Because each side has its own phase, a kind may run twice in one interval during that minute, one run after the other, as after any restart. A daily kind may run twice on that day only if the switch happens across its cron time; billing, billing_snapshot, stripe_sweep, retention and stay_fee_mail all tolerate a second run on the same day (the 1222 and 1242 goldens run them twice). Never neither: the owner steps start Go first on the switch and Python first on the rollback.
- `ubyhost-go` gets only the variables listed under its `environment:`, so `UBYHOST_SCHEDULER`, `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_ICAL_POLL_MINUTES` are added as bare keys (passed through only when set in `.env`). `UBYHOST_SUBMIT_SWEEP_MINUTES` is already there. The `worker` service reads `.env` whole (`env_file`). The explicit `UBYHOST_SCHEDULER: ${UBYHOST_SCHEDULER:-}` line makes the switch visible in compose; an empty value means off.

**Other open briefs on the same files** (lint warns): `App/app/scheduler.py` is named by 0347, 0348, 0417, 1290 and 1290-fix-1 (todo, but their code is already in the tree), 1171b (todo, not applied) and 1078, 1082 (review). `deploy/lightsail/docker-compose.yml` is named by 1201, 1202 and 1208 (todo; their changes appear already applied). `docs/ENVIRONMENT.md` is named by 0347, 0348, 0350, 0897, 1167, 1290 and others in review. 1450 goes first, then this brief; none of the others needs to run before it. This brief touches other lines, and `git apply --check` (step 0) proves the context is still there. If 1171b lands first, this patch still applies (it touches `_log_run` lines only); run step 0 again.

**The exact change** is `docs/tasks/1451-files/1451.patch` (sha256 below), produced and applied by the brief writer on 34738084 plus the 1450 files. It is reproduced here for the reviewer; apply the file, never retype it:

````diff
diff --git a/App/app/scheduler.py b/App/app/scheduler.py
index bbcaa996..9dd436dc 100644
--- a/App/app/scheduler.py
+++ b/App/app/scheduler.py
@@ -5,6 +5,7 @@ import fcntl
 import functools
 from datetime import datetime, timezone
 import logging
+import os
 import threading
 import time
 
@@ -534,6 +535,14 @@ def _queued(kind: str) -> bool:
     return config.DB_BACKEND == "postgresql" and kind in config.JOB_QUEUE_KINDS
 
 
+def go_scheduler() -> bool:
+    """True when UBYHOST_SCHEDULER=go: the Go service enqueues every job (J7).
+
+    Same test as go/internal/scheduler Enabled: "go", case and spaces ignored.
+    """
+    return os.environ.get("UBYHOST_SCHEDULER", "").strip().lower() == "go"
+
+
 def _target(kind: str):
     """The callable APScheduler runs for kind: enqueue a row, or the job itself."""
     if _queued(kind):
@@ -577,6 +586,16 @@ def start() -> bool:
         )
     if config.JOB_QUEUE_KINDS and config.DB_BACKEND != "postgresql":
         raise RuntimeError("UBYHOST_JOB_QUEUE_KINDS needs PostgreSQL")
+    go_enqueues = go_scheduler()
+    if go_enqueues:
+        # A kind off the queue runs here in-process, so a Go row for it would
+        # run it twice. Go refuses the same configuration.
+        missing = set(JOB_KINDS) - config.JOB_QUEUE_KINDS
+        if missing:
+            raise RuntimeError(
+                "UBYHOST_SCHEDULER=go needs every job in UBYHOST_JOB_QUEUE_KINDS; missing: "
+                + ", ".join(sorted(missing))
+            )
     if config.DB_BACKEND != "postgresql":
         log.warning("no deadline watch runs here: the deadlines job runs only in the Go service (PostgreSQL, 1290)")
     elif "deadlines" not in config.GO_JOB_KINDS:
@@ -650,6 +669,14 @@ def start() -> bool:
         _target("guide_import"), "interval", minutes=minutes["guide_import"],
         id="guide_import", max_instances=1, coalesce=True,
     )
+    if go_enqueues:
+        # The Go service enqueues every kind on this same schedule; this
+        # process only drains the queued rows Python claims (not in
+        # UBYHOST_GO_JOB_KINDS). Rollback: unset UBYHOST_SCHEDULER.
+        for kind in JOB_KINDS:
+            if _scheduler.get_job(kind):
+                _scheduler.remove_job(kind)
+        log.info("UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none")
     if any(_queued(kind) for kind in JOB_KINDS):
         _scheduler.add_job(
             _job_queue, "interval", seconds=15, id="job_queue",
diff --git a/deploy/lightsail/docker-compose.yml b/deploy/lightsail/docker-compose.yml
index b099b977..bf101437 100644
--- a/deploy/lightsail/docker-compose.yml
+++ b/deploy/lightsail/docker-compose.yml
@@ -155,6 +155,9 @@ services:
     environment:
       UBYHOST_DATA_DIR: /data
       UBYHOST_ROLE: worker
+      # J7: "go" makes this worker enqueue nothing (the Go service does);
+      # unset or anything else, this worker enqueues every job.
+      UBYHOST_SCHEDULER: ${UBYHOST_SCHEDULER:-}
     command: ["python", "-m", "app.worker"]
     volumes:
       - ubyhost-data:/data
@@ -226,7 +229,9 @@ services:
       UBYHOST_HEARTBEAT_ICAL_URL:
       UBYHOST_HEARTBEAT_URL:
       UBYHOST_ICAL_ALLOW_PRIVATE:
+      UBYHOST_ICAL_POLL_MINUTES:
       UBYHOST_IMPERSONATION_MAX_HOURS:
+      UBYHOST_JOB_QUEUE_KINDS:
       UBYHOST_MAIL_BACKEND:
       UBYHOST_MAX_BATCH:
       UBYHOST_META_ACCESS_TOKEN:
@@ -239,6 +244,7 @@ services:
       UBYHOST_PRIVACY_VERSION:
       UBYHOST_PUBLIC_BASE_URL:
       UBYHOST_PY_WEBHOOK_URL:
+      UBYHOST_SCHEDULER:
       UBYHOST_SECRET_KEY:
       UBYHOST_SOAP_WSA_HEADER:
       UBYHOST_STRIPE_MONTHLY_API_CALLS:
diff --git a/docs/ENVIRONMENT.md b/docs/ENVIRONMENT.md
index ec7a61fb..b1c258d2 100644
--- a/docs/ENVIRONMENT.md
+++ b/docs/ENVIRONMENT.md
@@ -51,6 +51,7 @@ Optional host subdomain: [deployment, exact values and rollback](APP_SUBDOMAIN.m
 | --- | --- | --- |
 | `UBYHOST_JOB_QUEUE_KINDS` | empty | PostgreSQL only. Comma list of scheduler job ids that go through the job table instead of running directly; unknown ids stop the worker. An open row unclaimed past twice its interval (Python or Go consumer missing) raises the `job_failed` alert for that job. |
 | `UBYHOST_GO_JOB_KINDS` | empty | PostgreSQL only. Kinds the Go service runs instead of Python; each must also be in `UBYHOST_JOB_QUEUE_KINDS`. Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi` and `deadlines` (the Go service reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`). `deadlines` is the deadline watch plus the filing watchdog and its heartbeat; it must stay in both lists, because Python no longer has this job (1290): without Go it only raises the `job_failed` alert. Rollback: `git revert` the 1290 PR, merge and deploy, then remove `deadlines` from this list (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`. The `ubyhost-go` service receives only the variables listed under its `environment:` in `docker-compose.yml`, not the whole `.env`; a new variable read in `go/` must be added there. |
+| `UBYHOST_SCHEDULER` | unset | PostgreSQL only. Who enqueues the timed job rows (J7). `go`: the Go service enqueues all 15 kinds on the schedule of `App/app/scheduler.py` (same intervals, cron times and Europe/Prague time zone) and the Python `worker` enqueues none but still runs the queued kinds that are not in `UBYHOST_GO_JOB_KINDS`. Both sides refuse `go` unless every kind is in `UBYHOST_JOB_QUEUE_KINDS` (the worker stops at start; Go logs `scheduler not started`). Unset or any other value: Python enqueues, Go does not. A second enqueue of a kind with an open row does nothing (index `job_one_open_per_kind`), so both sides running for a minute during the switch or the rollback is harmless. Rollback: remove the line, recreate `worker`, then `ubyhost-go`. |
 | `UBYHOST_ENABLE_SCHEDULER` | `1` | `0` stops **all** background work: calendar polling, automatic submission, the deadline watch, the guest e-mail outbox, claim-hold expiry and the passport-photo sweep. |
 | `UBYHOST_ROLE` | `web` | What the process runs (WP06). `web`: HTTP only, never starts the scheduler (the Docker image, two uvicorn workers). `worker`: only the background jobs, started with `python -m app.worker` (the Lightsail `worker` container). `all`: both in one process (`run.sh` and `render_start.sh` default to it). Only one scheduler can run per data directory: it holds `DATA_DIR/scheduler.lock`. |
 | `UBYHOST_WEB_WORKERS` | `2` | uvicorn workers in the Docker image's web process (WP32). `4` on the 8 GB / 2 vCPU production server. `docker-entrypoint.sh` and `preflight.sh` refuse anything but 1 to 16. |
````

**Verified by the brief writer** in a throwaway worktree: `git apply --check` clean on 34738084; `pytest tests/test_scheduler_go_switch.py tests/test_scheduler.py -q` 20 passed; `tests/test_worker.py tests/test_job_queue.py` 17 passed, 17 skipped (the job-queue tests need PostgreSQL); `docker compose config` with a scratch `.env` (`UBYHOST_SCHEDULER=go`) renders `UBYHOST_SCHEDULER: go` in `ubyhost-go` and `worker` and `UBYHOST_JOB_QUEUE_KINDS` in `ubyhost-go`.

Anchors (step 0): `go/internal/scheduler/scheduler.go` exists (1450 merged); `grep -cF 'func Enabled(getenv func(string) string) bool {' go/internal/scheduler/scheduler.go` prints 1; `grep -cF 'def go_scheduler' App/app/scheduler.py` prints 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/scheduler.py` | edit (patch) | `import os`; `go_scheduler()`; the queue check and the job removal in `start()` |
| `deploy/lightsail/docker-compose.yml` | edit (patch) | `worker`: `UBYHOST_SCHEDULER`; `ubyhost-go`: `UBYHOST_ICAL_POLL_MINUTES`, `UBYHOST_JOB_QUEUE_KINDS`, `UBYHOST_SCHEDULER` |
| `docs/ENVIRONMENT.md` | edit (patch) | one row `UBYHOST_SCHEDULER` after the `UBYHOST_GO_JOB_KINDS` row |
| `App/tests/test_scheduler_go_switch.py` | create (copy) | the switch, both ways, and the queue check |
| `docs/tasks/1451-report.md` | create | the report |

`docs/tasks/1451-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git branch --show-current` prints `task/1451-go-scheduler-switch`; `git status --short | tail -5` is empty; the anchors of section 2 as stated; then

```bash
cd docs/tasks/1451-files && sha256sum -c <<'EOF2' 2>&1 | tail -3; cd ../../.. && git apply --check docs/tasks/1451-files/1451.patch 2>&1 | tail -5 && echo APPLY_OK
9220aaac24f05e1e6c0fb36c03ccc9c30738aaeda025cac05135fbabbb093d2a  1451.patch
7e843834856f3a5d246c84670620d9e2fc5dedc4f81b000b454b2b3ab388d14c  App/tests/test_scheduler_go_switch.py
EOF2
```

   Expected: two `OK` lines and `APPLY_OK`. Anything else: STOP. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`.

1. Apply the patch: `git apply docs/tasks/1451-files/1451.patch && git diff --stat | tail -4`. Expected: `App/app/scheduler.py | 27`, `deploy/lightsail/docker-compose.yml | 6`, `docs/ENVIRONMENT.md | 1`, `3 files changed, 34 insertions(+)`. Commit `1451 step 1`.

2. Copy the test: `cp docs/tasks/1451-files/App/tests/test_scheduler_go_switch.py App/tests/test_scheduler_go_switch.py && git status --short | tail -3`. Expected: `?? App/tests/test_scheduler_go_switch.py`. Commit `1451 step 2`.

3. Run section 6. Write the report (section 9), commit it as `1451 report`, open one draft PR. The change is off until the owner sets the variable, so the owner may merge it when CI is green.

## 5. Do not touch

`App/app/worker.py`, `App/app/config.py`, `App/app/jobqueue.py`, every other file under `App/app/`; `App/tests/conftest.py`, `App/tests/test_scheduler.py`; everything under `go/`; `deploy/` except `deploy/lightsail/docker-compose.yml`; `deploy/lightsail/.env` and `.env.example`; `docs/context/*`; `docs/tasks/1451-files/`. Never set `UBYHOST_SCHEDULER` on a server: that is the owner's switch below. Rules 1, 3, 4 and 5 as in section 2.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_scheduler_go_switch.py tests/test_scheduler.py tests/test_worker.py -q --tb=short -x 2>&1 | tail -30` ends with `passed` and no `failed` (the brief writer saw 20 passed for the first two files; `test_worker.py` is the Filing row of the test-map).

From the repo root:

- `grep -cE '^      UBYHOST_(SCHEDULER|JOB_QUEUE_KINDS|ICAL_POLL_MINUTES)' deploy/lightsail/docker-compose.yml 2>&1 | tail -1` prints `4`.
- `grep -c '^| `UBYHOST_SCHEDULER` |' docs/ENVIRONMENT.md 2>&1 | tail -1` prints `1`.
- `cd go && go test -count=1 ./internal/scheduler/ ./cmd/ubyhost-web/ 2>&1 | tail -5` prints two `ok` lines (unchanged Go code, as a check that 1450 is in).
- `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error naming 1451.

## 7. Acceptance

- [ ] `git diff --stat origin/main..HEAD -- . ':!docs/tasks/1451-go-scheduler-switch.md' ':!docs/tasks/1451-files'` lists exactly the files of section 3.
- [ ] `git diff origin/main..HEAD -- App/app/scheduler.py deploy/lightsail/docker-compose.yml docs/ENVIRONMENT.md` equals the patch: `git diff origin/main..HEAD -- App/app/scheduler.py deploy/lightsail/docker-compose.yml docs/ENVIRONMENT.md | grep '^[+-][^+-]' | sha256sum` equals `grep '^[+-][^+-]' docs/tasks/1451-files/1451.patch | sha256sum`.
- [ ] `cmp docs/tasks/1451-files/App/tests/test_scheduler_go_switch.py App/tests/test_scheduler_go_switch.py` prints nothing.
- [ ] Section 6 output as stated.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a sha256 differs, or `git apply --check` fails;
- a test fails twice (never change the patch or the test);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1451-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left (copy the owner steps below unchanged).

## Risk list (for the reviewer)

Read the full diff of:

- `App/app/scheduler.py`: with the switch on, every enqueue job is removed and only `job_queue` stays; with it off, nothing changes; the queue check raises before the scheduler exists.
- `deploy/lightsail/docker-compose.yml`: the four lines, bare keys in `ubyhost-go` (never `${NAME:-}` there).
- `App/tests/test_scheduler_go_switch.py`: proves both directions and the refusal.

## Owner steps

Do these only after 1450 and 1451 are merged and deployed (`./scripts/deploy.sh` as usual). Pick a quiet time that is not 03:00 to 07:30 Prague time (the daily jobs run then). Keep the server terminal open for 20 minutes.

**Switch to Go**

1. Open a terminal on the server and run `cd /opt/ubyhost/deploy/lightsail`.
2. Run `git -C /opt/ubyhost log -1 --oneline` and check that the merge of 1451 (or a later one) is shown. If not, deploy first.
3. Run `grep -E '^UBYHOST_(JOB_QUEUE_KINDS|GO_JOB_KINDS|SCHEDULER)=' .env`. The `UBYHOST_JOB_QUEUE_KINDS` line must contain all 15 names: `ical submit deadlines mail photo_sweep meta_capi retention stay_fee_mail stripe_sweep billing billing_snapshot door_codes posthog push guide_import`. There must be no `UBYHOST_SCHEDULER` line yet. If a name is missing, stop here and send the output to the orchestrator: moving a kind onto the queue is a separate step.
4. Run `date -u +%Y-%m-%dT%H:%M:%S` and write the time down (below: START).
5. Run `nano .env`, add the line `UBYHOST_SCHEDULER=go` at the end, save with Ctrl+O, Enter, and close with Ctrl+X.
6. Start Go first: `docker compose up -d ubyhost-go`. For about a minute both sides enqueue; that is harmless (one open row per kind).
7. Wait 90 seconds, then run `docker compose logs --since 3m ubyhost-go 2>&1 | grep -E 'scheduler (started|enqueued|not started)' | tail -8`. You must see `msg="scheduler started" owner=go kinds=15 timezone=Europe/Prague` and `msg="scheduler enqueued"` lines (`job=ical` and `job=photo_sweep` about 20 seconds after the start, `job=push` within about a minute). If you see `scheduler not started`, or no `scheduler started` line, do the rollback below and send the output to the orchestrator.
8. Now stop Python enqueuing: `docker compose up -d worker`.
9. Wait 60 seconds, then run `docker compose logs --since 2m worker 2>&1 | grep -E 'UBYHOST_SCHEDULER=go|RuntimeError|Error' | tail -5`. You must see `UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none` and no error. Then `docker compose ps worker ubyhost-go` shows both `Up`, and after two minutes `worker` shows `(healthy)`. A `RuntimeError` line or a restarting worker: do the rollback.
10. Wait 15 minutes, then check the queue (replace START with the time from step 4): `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT kind, count(*) AS rows, count(*) FILTER (WHERE done_at IS NOT NULL) AS done, count(*) FILTER (WHERE dead_at IS NOT NULL) AS dead FROM job WHERE created_at >= 'START' GROUP BY kind ORDER BY kind;"`. Expected, roughly: `push` about 15 rows, `mail` and `door_codes` about 3 each, `submit` and `meta_capi` 1 or 2, `posthog` about 1, `ical` and `photo_sweep` 1, `deadlines` 0 or 1; `done` close to `rows` (the newest row of a kind may still be open); `dead` 0 everywhere. `door_codes` and `mail` being done proves Python still claims the kinds Go does not run.
11. Run `docker compose logs --since 20m worker 2>&1 | grep -c 'queued job .* unclaimed'`. It must print `0`.
12. The next morning, after 07:15 Prague time, run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT kind, created_at FROM job WHERE kind IN ('retention','stripe_sweep','billing','billing_snapshot','stay_fee_mail') ORDER BY id DESC LIMIT 5;"`. Each of the five must appear once with today's date, at 03:30, 04:15, 06:00, 06:15 and 07:00 Prague time (in winter that is 02:30, 03:15, 05:00, 05:15 and 06:00 in the UTC `created_at`; in summer one hour less still). Also open the admin Operations page: no job is shown as late.
13. Tell the orchestrator the outputs of steps 7, 9, 10 and 12. After one clean week a later brief removes the `worker` enqueue code (out of scope here).

**Rollback** (any time; about 2 minutes)

1. `cd /opt/ubyhost/deploy/lightsail`, then `nano .env`, delete the line `UBYHOST_SCHEDULER=go`, save with Ctrl+O, Enter, close with Ctrl+X.
2. Start Python first: `docker compose up -d worker`. Wait 60 seconds, then `docker compose logs --since 2m worker 2>&1 | grep -E 'scheduler started|UBYHOST_SCHEDULER=go' | tail -3` must show `scheduler started (ical every 60 min, submit every 10 min)` (your own minutes if you changed them) and no `UBYHOST_SCHEDULER=go` line.
3. Then stop Go enqueuing: `docker compose up -d ubyhost-go`. Wait 30 seconds, then `docker compose logs --since 1m ubyhost-go 2>&1 | grep -c 'scheduler started'` must print `0`.
4. Run the query of step 10 again with a new START after 15 minutes: the same kinds keep getting rows. Tell the orchestrator.
