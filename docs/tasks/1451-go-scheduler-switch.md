# 1451: Python side of `UBYHOST_SCHEDULER=go` (worker stops enqueuing and watches Go), compose lines, ENVIRONMENT row; owner switch steps

Status: todo
Depends on: 1452, 1450 | Base: the orchestrator's branch (claude/happy-babbage-2zeeam); `git apply --check` in step 0 | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out. Commit `1451 step k` after each step. Do not create a branch, do not push, do not open a PR.

## 1. Objective

When `UBYHOST_SCHEDULER=go` is set and usable, the Python `worker` enqueues nothing. It still drains the queued rows Python claims, and every minute it checks that the Go scheduler wrote each kind in time; a kind Go left out it enqueues itself, with a critical alert. The brief also passes the switch to `ubyhost-go` and documents it. With the variable unset nothing changes. The production switch is the owner steps at the end (plan step J7, tier A: filing and deadline timing).

## 2. Context

Rules (AGENTS.md): 1 filing correctness first: there is no state in which neither side enqueues without the worker enqueuing and alerting; 3 no secret in the repo (bare pass-through keys); 4 no new dependency; 5 SQL only through `db.py` helpers, Postgres-portable, no schema change and no migration (the `job` and `alert` tables exist).

**Why Python changes** ([go-first](../context/go-first.md) exception 1, port plumbing a Go brief needs): reading the switch, refusing a configuration Go cannot use, and the watch that keeps the jobs enqueued while Go is not. No Python behaviour changes while the variable is unset.

**How it works** (`App/app/scheduler.py`):
- `go_scheduler()`: the variable says `go` (case and spaces ignored), the same test as Go `scheduler.Enabled`.
- `go_scheduler_problem()`: the reason the switch cannot be used, or empty. The reasons are: not PostgreSQL; a kind missing from `UBYHOST_JOB_QUEUE_KINDS` (a kind off the queue runs in-process here, so a Go row would run it twice); `UBYHOST_ICAL_POLL_MINUTES` or `UBYHOST_SUBMIT_SWEEP_MINUTES` at or below 0. Go's `scheduler.Setup` refuses exactly these. The switch is then ignored on both sides: this worker logs `<reason>; UBYHOST_SCHEDULER=go is ignored and this worker enqueues every job` and enqueues as before, and Go logs `background task not started task=scheduler`. A value Python's `int()` refuses stops Python at import, as it does today.
- `go_enqueues()` (switch usable): `start()` adds the 15 jobs as today, then removes them. It keeps the 15 s `job_queue` drain, adds `go_watch` (every 60 s), and logs `UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none`.
- `watch_go_scheduler()` decides per kind. A kind is "left out" when it has no open row and its newest `created_at`/`done_at` is older than twice its interval plus one minute (push 3 min, submit 21 min, deadlines 61 min). For a daily job, the test is no row since its last local cron time in Europe/Prague, after 15 minutes of grace. For a left-out kind the worker calls `jobqueue.enqueue` (one open row per kind, so never a duplicate) and remembers the stamp. While any kind is in that state, it keeps the system alert `job_failed:job_queue` open at level critical, with message `Go scheduler is not enqueuing: <kinds>`. Hosts and the operator see the existing card "Background job 'job queue' failed. Automatic reporting may be delayed until it runs again." in Python and in Go pages, so no new copy is needed. A row this worker did not write, created after its stamp, means Go writes that kind again; when no kind is left out, the alert is resolved. This covers Go down, crash-looping on pending goose files, dropped from `COMPOSE_PROFILES`, set up wrong, or failing its database inserts.
- Limit (pre-existing, unchanged): if `ubyhost-go` is down, the kinds it *claims* (`UBYHOST_GO_JOB_KINDS`, `submit` and `deadlines` among them) are enqueued but not run by anyone. The 1174 stuck-row alert and the heartbeats report that, as today.
- Why this design and not a "who enqueues" lock: it needs no schema change, it keeps the jobs running instead of only alarming, and it fails safe if the watch itself breaks (Go still enqueues).

**Double enqueue.** `job_one_open_per_kind` plus `ON CONFLICT ... DO NOTHING` on both sides allow one open row per kind, so runs of one kind never overlap. During the minute both sides enqueue (switch or rollback), a kind can run twice in one interval, one after the other, as after any restart. A daily kind may run twice on that day only if the switch crosses its cron time; the owner steps avoid 03:00 to 07:30. Never neither: Go starts first on the switch, Python first on the rollback.

**Compose.** `ubyhost-go` receives only the variables listed under its `environment:`, so `UBYHOST_SCHEDULER`, `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_ICAL_POLL_MINUTES` are added as bare keys (passed only when set in `.env`); `UBYHOST_SUBMIT_SWEEP_MINUTES` is already there. `worker` reads `.env` whole; its explicit `UBYHOST_SCHEDULER: ${UBYHOST_SCHEDULER:-}` makes the switch visible (empty means off). Restarts, read from `deploy/lightsail/docker-compose.yml` (not run: no Docker daemon was available): `ubyhost` (web) has `env_file: .env`, and both `worker` and `ubyhost-go` have `depends_on: ubyhost: condition: service_healthy`. So `docker compose up -d worker` after an `.env` edit would also recreate the web container. The owner steps use `--no-deps`, which recreates only the named service.

**Other open briefs on the same files** (lint warns): `App/app/scheduler.py` is named by 0347, 0348, 0417, 1290 and 1290-fix-1 (todo, but their code is already in the tree), 1171b (todo, not applied) and 1078, 1082 (review). `deploy/lightsail/docker-compose.yml` is named by 1201, 1202 and 1208 (todo; their changes appear already applied). `docs/ENVIRONMENT.md` is named by 0347, 0348, 0350, 0897, 1167, 1290 and others in review. Order: 1452, 1450, then this brief; none of the others needs to run first. `git apply --check` (step 0) proves the context is still there.

**The exact change** is `docs/tasks/1451-files/1451.patch`. It is reproduced here for the reviewer; apply the file, never retype it:

````diff
diff --git a/App/app/scheduler.py b/App/app/scheduler.py
index bbcaa9969..dd340bf8c 100644
--- a/App/app/scheduler.py
+++ b/App/app/scheduler.py
@@ -3,8 +3,9 @@ from __future__ import annotations
 
 import fcntl
 import functools
-from datetime import datetime, timezone
+from datetime import datetime, timedelta, timezone
 import logging
+import os
 import threading
 import time
 
@@ -534,6 +535,133 @@ def _queued(kind: str) -> bool:
     return config.DB_BACKEND == "postgresql" and kind in config.JOB_QUEUE_KINDS
 
 
+def go_scheduler() -> bool:
+    """True when UBYHOST_SCHEDULER says go (J7); go_enqueues() also checks it can be used.
+
+    Same test as go/internal/scheduler Enabled: "go", case and spaces ignored.
+    """
+    return os.environ.get("UBYHOST_SCHEDULER", "").strip().lower() == "go"
+
+
+def go_scheduler_problem() -> str:
+    """Why UBYHOST_SCHEDULER=go cannot be used here, or "" when it can.
+
+    go/internal/scheduler Setup refuses the same configurations, so both
+    sides agree the switch is off and this worker keeps enqueuing. A kind off
+    the queue runs here in-process, so a Go row for it would run it twice.
+    """
+    if config.DB_BACKEND != "postgresql":
+        return "UBYHOST_SCHEDULER=go needs PostgreSQL"
+    missing = set(JOB_KINDS) - config.JOB_QUEUE_KINDS
+    if missing:
+        return "UBYHOST_SCHEDULER=go needs every job in UBYHOST_JOB_QUEUE_KINDS; missing: " + ", ".join(sorted(missing))
+    for name, value in (
+        ("UBYHOST_ICAL_POLL_MINUTES", config.ICAL_POLL_MINUTES),
+        ("UBYHOST_SUBMIT_SWEEP_MINUTES", config.SUBMIT_SWEEP_MINUTES),
+    ):
+        if value <= 0:
+            return f"{name} must be a whole number of minutes above 0"
+    return ""
+
+
+def go_enqueues() -> bool:
+    """True when the Go service enqueues every job and this worker none."""
+    return go_scheduler() and not go_scheduler_problem()
+
+
+# The daily jobs and their local times, as start() adds them
+# (test_scheduler_go_switch checks the two agree).
+CRON_TIMES = {
+    "retention": (3, 30),
+    "stay_fee_mail": (7, 0),
+    "stripe_sweep": (4, 15),
+    "billing": (6, 0),
+    "billing_snapshot": (6, 15),
+}
+GO_WATCH_SECONDS = 60
+# A daily job counts as missed this long after its local time.
+GO_WATCH_CRON_GRACE_MINUTES = 15
+# The card hosts and the operator see: "Background job 'job queue' failed."
+GO_WATCH_ALERT = "job_failed:job_queue"
+# kind -> created_at of the newest row this worker enqueued for it in place of Go.
+_go_fallback: dict = {}
+
+
+def _go_due_since(kind: str, now: datetime) -> str:
+    """The stamp by which Go should have written or finished a row of kind."""
+    if kind in CRON_TIMES:
+        from zoneinfo import ZoneInfo
+
+        hour, minute = CRON_TIMES[kind]
+        local = (now - timedelta(minutes=GO_WATCH_CRON_GRACE_MINUTES)).astimezone(ZoneInfo(config.TIMEZONE))
+        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
+        if due > local:
+            due -= timedelta(days=1)  # wall-clock arithmetic: the same local time a day earlier
+        moment = due
+    else:
+        moment = now - timedelta(minutes=2 * job_intervals()[kind] + 1)
+    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()
+
+
+def watch_go_scheduler(now: datetime | None = None) -> list:
+    """With UBYHOST_SCHEDULER=go: enqueue every kind Go left out; the kinds enqueued.
+
+    A kind is left out when it has no open row and its newest row was neither
+    created nor finished within twice its interval (plus a minute), or, for a
+    daily job, since its last local time (15 minutes of grace). This worker
+    then enqueues it itself (one open row per kind, so never a duplicate) and
+    keeps the critical alert open until a row it did not write appears for
+    every such kind. Go down, crash-looping or set up wrong all end here.
+    """
+    now = now or datetime.now(timezone.utc)
+    had_fallback = bool(_go_fallback)
+    rows = {
+        row["kind"]: row
+        for row in db.query(
+            "SELECT kind, MAX(created_at) AS created, MAX(done_at) AS done, "
+            "SUM(CASE WHEN done_at IS NULL AND dead_at IS NULL THEN 1 ELSE 0 END) AS open_rows "
+            "FROM job GROUP BY kind"
+        )
+    }
+    added = []
+    for kind in JOB_KINDS:
+        row = rows.get(kind)
+        created = (row["created"] if row else None) or ""
+        if kind in _go_fallback and created > _go_fallback[kind]:
+            del _go_fallback[kind]
+            log.info("the Go scheduler enqueues %s again", kind)
+        if row and row["open_rows"]:
+            continue
+        last = max(created, (row["done"] if row else None) or "")
+        if last >= _go_due_since(kind, now):
+            continue
+        if jobqueue.enqueue(kind):
+            _go_fallback[kind] = db.utcnow()
+            added.append(kind)
+    if _go_fallback:
+        kinds = ", ".join(sorted(_go_fallback))
+        log.error("the Go scheduler is not enqueuing %s; this worker enqueues them (UBYHOST_SCHEDULER=go)", kinds)
+        alerts.raise_alert(
+            "critical",
+            "job_failed",
+            f"Go scheduler is not enqueuing: {kinds}",
+            "The Python worker enqueues these jobs until the Go scheduler runs again.",
+            dedupe_key=GO_WATCH_ALERT,
+        )
+    elif had_fallback:
+        alerts.resolve(GO_WATCH_ALERT)
+        log.info("the Go scheduler enqueues every job again; alert resolved")
+    return added
+
+
+def _job_go_watch() -> None:
+    """APScheduler wrapper for watch_go_scheduler. Never raises."""
+    try:
+        watch_go_scheduler()
+    except Exception:
+        log.exception("Go scheduler watch failed")
+
+
 def _target(kind: str):
     """The callable APScheduler runs for kind: enqueue a row, or the job itself."""
     if _queued(kind):
@@ -577,6 +705,9 @@ def start() -> bool:
         )
     if config.JOB_QUEUE_KINDS and config.DB_BACKEND != "postgresql":
         raise RuntimeError("UBYHOST_JOB_QUEUE_KINDS needs PostgreSQL")
+    go_on = go_enqueues()
+    if go_scheduler() and not go_on:
+        log.error("%s; UBYHOST_SCHEDULER=go is ignored and this worker enqueues every job", go_scheduler_problem())
     if config.DB_BACKEND != "postgresql":
         log.warning("no deadline watch runs here: the deadlines job runs only in the Go service (PostgreSQL, 1290)")
     elif "deadlines" not in config.GO_JOB_KINDS:
@@ -650,6 +781,19 @@ def start() -> bool:
         _target("guide_import"), "interval", minutes=minutes["guide_import"],
         id="guide_import", max_instances=1, coalesce=True,
     )
+    if go_on:
+        # J7: the Go service enqueues every kind on this same schedule; this
+        # process drains the queued rows Python claims (not in
+        # UBYHOST_GO_JOB_KINDS) and watches that Go keeps enqueuing.
+        # Rollback: unset UBYHOST_SCHEDULER.
+        for kind in JOB_KINDS:
+            if _scheduler.get_job(kind):
+                _scheduler.remove_job(kind)
+        _scheduler.add_job(
+            _job_go_watch, "interval", seconds=GO_WATCH_SECONDS, id="go_watch",
+            max_instances=1, coalesce=True,
+        )
+        log.info("UBYHOST_SCHEDULER=go: the Go service enqueues every job; this worker enqueues none")
     if any(_queued(kind) for kind in JOB_KINDS):
         _scheduler.add_job(
             _job_queue, "interval", seconds=15, id="job_queue",
diff --git a/deploy/lightsail/docker-compose.yml b/deploy/lightsail/docker-compose.yml
index b099b977e..8686d3461 100644
--- a/deploy/lightsail/docker-compose.yml
+++ b/deploy/lightsail/docker-compose.yml
@@ -155,6 +155,9 @@ services:
     environment:
       UBYHOST_DATA_DIR: /data
       UBYHOST_ROLE: worker
+      # J7: "go" makes this worker enqueue nothing (the Go service does) and
+      # watch that Go keeps enqueuing; unset, it enqueues every job.
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
index ec7a61fbe..744d4f5ad 100644
--- a/docs/ENVIRONMENT.md
+++ b/docs/ENVIRONMENT.md
@@ -51,6 +51,7 @@ Optional host subdomain: [deployment, exact values and rollback](APP_SUBDOMAIN.m
 | --- | --- | --- |
 | `UBYHOST_JOB_QUEUE_KINDS` | empty | PostgreSQL only. Comma list of scheduler job ids that go through the job table instead of running directly; unknown ids stop the worker. An open row unclaimed past twice its interval (Python or Go consumer missing) raises the `job_failed` alert for that job. |
 | `UBYHOST_GO_JOB_KINDS` | empty | PostgreSQL only. Kinds the Go service runs instead of Python; each must also be in `UBYHOST_JOB_QUEUE_KINDS`. Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi` and `deadlines` (the Go service reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`). `deadlines` is the deadline watch plus the filing watchdog and its heartbeat; it must stay in both lists, because Python no longer has this job (1290): without Go it only raises the `job_failed` alert. Rollback: `git revert` the 1290 PR, merge and deploy, then remove `deadlines` from this list (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`. The `ubyhost-go` service receives only the variables listed under its `environment:` in `docker-compose.yml`, not the whole `.env`; a new variable read in `go/` must be added there. |
+| `UBYHOST_SCHEDULER` | unset | PostgreSQL only. Who enqueues the timed job rows (J7). `go`: the Go service enqueues all 15 kinds on the schedule of `App/app/scheduler.py` (same intervals, cron times and Europe/Prague time zone); the Python `worker` enqueues none, still runs the queued kinds not in `UBYHOST_GO_JOB_KINDS`, and every minute checks that each kind got a row in time. A kind Go left out (Go down, crash-looping or set up wrong) is enqueued by the worker itself and raises the critical alert "Background job 'job queue' failed" until Go writes that kind again. `go` is ignored on both sides (the worker enqueues as before and both log the reason) unless every kind is in `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_ICAL_POLL_MINUTES` and `UBYHOST_SUBMIT_SWEEP_MINUTES` are above 0. One open row per kind (index `job_one_open_per_kind`), so both sides enqueuing at once write no duplicate. Rollback: remove the line, recreate `worker`, then `ubyhost-go` (both with `--no-deps`). |
 | `UBYHOST_ENABLE_SCHEDULER` | `1` | `0` stops **all** background work: calendar polling, automatic submission, the deadline watch, the guest e-mail outbox, claim-hold expiry and the passport-photo sweep. |
 | `UBYHOST_ROLE` | `web` | What the process runs (WP06). `web`: HTTP only, never starts the scheduler (the Docker image, two uvicorn workers). `worker`: only the background jobs, started with `python -m app.worker` (the Lightsail `worker` container). `all`: both in one process (`run.sh` and `render_start.sh` default to it). Only one scheduler can run per data directory: it holds `DATA_DIR/scheduler.lock`. |
 | `UBYHOST_WEB_WORKERS` | `2` | uvicorn workers in the Docker image's web process (WP32). `4` on the 8 GB / 2 vCPU production server. `docker-entrypoint.sh` and `preflight.sh` refuse anything but 1 to 16. |
````

**Verified by the brief writer** in a throwaway worktree of the branch head (fd4075b47), with 1452 and 1450 applied by their steps first: `git apply --check` clean. Under SQLite, `pytest tests/test_scheduler_go_switch.py tests/test_scheduler.py tests/test_worker.py -q` gave 32 passed, 4 skipped (the four watch tests need PostgreSQL). Against a disposable PostgreSQL 16, `UBYHOST_DATABASE_URL=... pytest tests/test_scheduler_go_switch.py` gave 11 passed. Three mutations were each caught: never fall back, never resolve, threshold 0.

Anchors (step 0): `grep -cF 'func registerBackground(' go/cmd/ubyhost-web/registry.go` and `grep -cF 'func Enabled(getenv func(string) string) bool {' go/internal/scheduler/scheduler.go` print 1 (1452 and 1450 are in); `grep -cF 'def go_scheduler' App/app/scheduler.py` prints 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/scheduler.py` | edit (patch) | `import os`, `timedelta`; `go_scheduler`, `go_scheduler_problem`, `go_enqueues`, `CRON_TIMES`, `watch_go_scheduler`, `_job_go_watch`; in `start()` the ignored-switch log and the go branch |
| `deploy/lightsail/docker-compose.yml` | edit (patch) | `worker`: `UBYHOST_SCHEDULER`; `ubyhost-go`: `UBYHOST_ICAL_POLL_MINUTES`, `UBYHOST_JOB_QUEUE_KINDS`, `UBYHOST_SCHEDULER` |
| `docs/ENVIRONMENT.md` | edit (patch) | one row `UBYHOST_SCHEDULER` after the `UBYHOST_GO_JOB_KINDS` row |
| `App/tests/test_scheduler_go_switch.py` | create (copy) | switch both ways, ignored switch, cron times, the watch (PostgreSQL) |
| `docs/tasks/1451-report.md` | create | the report |

`docs/tasks/1451-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git status --short -- App/app/scheduler.py App/tests deploy docs/ENVIRONMENT.md | tail -5` is empty; the anchors of section 2 as stated; then

```bash
cd docs/tasks/1451-files && sha256sum -c <<'EOF2' 2>&1 | tail -3; cd ../../.. && git apply --check docs/tasks/1451-files/1451.patch 2>&1 | tail -5 && echo APPLY_OK
ab4ee0227d048fa2d9e673577fbf4c3a308af5260c6459bf02810745dd20d009  1451.patch
e61ca201f839d285456c3b9636c81c027fe39b22bc69275d4cee090adfcb0022  App/tests/test_scheduler_go_switch.py
EOF2
```

   Expected: two `OK` lines and `APPLY_OK`. Anything else: STOP. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`.

1. Apply the patch: `git apply docs/tasks/1451-files/1451.patch && git diff --stat -- App/app/scheduler.py deploy docs/ENVIRONMENT.md | tail -4`. Expected: `App/app/scheduler.py | 146`, `deploy/lightsail/docker-compose.yml | 6`, `docs/ENVIRONMENT.md | 1`, `3 files changed, 152 insertions(+), 1 deletion(-)`. Commit: `git add App/app/scheduler.py deploy/lightsail/docker-compose.yml docs/ENVIRONMENT.md && git commit -m "1451 step 1"`.

2. Copy the test: `cp docs/tasks/1451-files/App/tests/test_scheduler_go_switch.py App/tests/test_scheduler_go_switch.py && git status --short -- App/tests | tail -3`. Expected: `?? App/tests/test_scheduler_go_switch.py`. Commit: `git add App/tests/test_scheduler_go_switch.py && git commit -m "1451 step 2"`.

3. Run section 6. Write the report (section 9) and commit it: `git add docs/tasks/1451-report.md docs/tasks/1451-go-scheduler-switch.md && git commit -m "1451 report"`. The change is off until the owner sets the variable.

## 5. Do not touch

`App/app/worker.py`, `App/app/config.py`, `App/app/jobqueue.py`, `App/app/alerts.py`, `App/app/host_i18n.py` and every other file under `App/app/`; `App/tests/conftest.py`, `App/tests/test_scheduler.py`; `App/migrations*`; everything under `go/`; `deploy/` except `deploy/lightsail/docker-compose.yml`; `deploy/lightsail/.env` and `.env.example`; `docs/context/*`; `docs/tasks/1451-files/`. Never set `UBYHOST_SCHEDULER` on a server: that is the owner's switch below. Other writers commit on this branch: stage only your files by name, never `git add -A` or `git commit -a`.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_scheduler_go_switch.py tests/test_scheduler.py tests/test_worker.py -q --tb=short -x -rs 2>&1 | tail -30` prints `32 passed, 4 skipped` and no `failed` or `error`. The 4 skips are the watch tests ("needs UBYHOST_DATABASE_URL"). If `UBYHOST_DATABASE_URL` points at a test database, run `.venv/bin/python -m pytest tests/test_scheduler_go_switch.py -q --tb=short -x 2>&1 | tail -5` as well: `11 passed`. CI's PostgreSQL job runs them otherwise. `test_worker.py` is from the Filing row of the test-map.

From the repo root:

- `grep -cE '^      UBYHOST_(SCHEDULER|JOB_QUEUE_KINDS|ICAL_POLL_MINUTES)' deploy/lightsail/docker-compose.yml 2>&1 | tail -1` prints `4`.
- `grep -c '^| `UBYHOST_SCHEDULER` |' docs/ENVIRONMENT.md 2>&1 | tail -1` prints `1`.
- `cd go && go test -count=1 ./internal/scheduler/ ./cmd/ubyhost-web/ 2>&1 | tail -5` prints two `ok` lines (Go is unchanged here; a check that 1452 and 1450 are in).
- `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error naming 1451.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1451 '` lists `1451 step 1`, `1451 step 2` and `1451 report`, and `git show --stat --format=%s $(git log --format=%h --grep='^1451 step') | tail -8` names only the four files of section 3 that are not the report.
- [ ] `git show $(git log --format=%h --grep='^1451 step 1') -- App/app/scheduler.py deploy/lightsail/docker-compose.yml docs/ENVIRONMENT.md | grep '^[+-][^+-]' | sha256sum` equals `grep '^[+-][^+-]' docs/tasks/1451-files/1451.patch | sha256sum`.
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

1. The files changed (`git show --stat` of the step commits).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left (copy the owner steps below unchanged).

## Risk list (for the reviewer)

Read the full diff of:

- `App/app/scheduler.py`: `go_scheduler_problem` must refuse exactly what Go `scheduler.Setup` refuses. `watch_go_scheduler` thresholds: interval kinds twice the interval plus a minute; daily kinds the last local cron time plus 15 minutes, with wall-clock day arithmetic. It skips kinds with an open row, and its resolve rule is a newer row it did not write. In `start()`, the go branch removes every enqueue job and adds `go_watch`.
- `deploy/lightsail/docker-compose.yml`: the four lines, bare keys in `ubyhost-go` (never `${NAME:-}` there).
- `App/tests/test_scheduler_go_switch.py`: Go healthy means no Python row and no alert; Go silent means 15 rows, the critical alert, no duplicate, and the alert resolved when Go writes again; open rows and long runs are respected; a daily job waits for its grace.

## Owner steps

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
11. Check that the Python safety net is quiet: `docker compose logs --since 20m worker 2>&1 | grep -c 'Go scheduler is not enqueuing\|the Go scheduler is not enqueuing'` prints `0`. In the app, the dashboard shows no red card "Background job 'job queue' failed".
12. The next morning, after 07:15 Prague time, run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT kind, created_at FROM job WHERE kind IN ('retention','stripe_sweep','billing','billing_snapshot','stay_fee_mail') ORDER BY id DESC LIMIT 5;"`. Each of the five must appear once with today's date. The `created_at` is in UTC: in winter 02:30, 03:15, 05:00, 05:15 and 06:00, which is 03:30, 04:15, 06:00, 06:15 and 07:00 Prague time; in summer each is one hour earlier in UTC. Also open the admin Operations page: no job is shown as late.
13. Send the orchestrator the outputs of steps 7, 9, 10 and 12. After one clean week, a later brief removes the worker's enqueue code (not part of this brief).

**If the red card "Background job 'job queue' failed" appears after the switch**

It means the Go service stopped writing some jobs. The Python worker has taken them over, so they still run, and the card stays until Go writes them again. To see which jobs: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c "SELECT level, message, created_at FROM alert WHERE dedupe_key = 'job_failed:job_queue' AND resolved_at IS NULL;"`. The message names them, for example `Go scheduler is not enqueuing: push, submit`. Then run `docker compose ps ubyhost-go` and `docker compose logs --tail 50 ubyhost-go`, and send both outputs to the orchestrator. If `ubyhost-go` is not `Up`, do the rollback now: the jobs the Go service runs (filing among them) wait for it either way, but the rollback puts the timing back on Python.

**Rollback** (any time; about 2 minutes)

1. Run `cd /opt/ubyhost/deploy/lightsail`, then `nano .env`. Delete the line `UBYHOST_SCHEDULER=go`, save with Ctrl+O and Enter, and close with Ctrl+X.
2. Start Python first: `docker compose up -d --no-deps worker`. Wait 60 seconds, then `docker compose logs --since 2m worker 2>&1 | grep -E 'scheduler started|UBYHOST_SCHEDULER=go' | tail -3` must show `scheduler started (ical every 60 min, submit every 10 min)` (your own minutes if you changed them) and no `UBYHOST_SCHEDULER=go` line.
3. Then stop Go enqueuing: `docker compose up -d --no-deps ubyhost-go`. Wait 30 seconds, then `docker compose logs --since 1m ubyhost-go 2>&1 | grep -c 'scheduler started'` must print `0`.
4. After 15 minutes, run the query of step 10 again with a new START: the same kinds keep getting rows. If the red card is still open, dismiss it in the app. Tell the orchestrator.
