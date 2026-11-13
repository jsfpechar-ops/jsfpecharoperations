# 1174: Alert when a queued job row sits unclaimed

Status: todo
Depends on: none | Base commit: 748098d | Branch: claude/1174-stuck-queue-alert
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When an open row in the `job` table stays unclaimed far past its schedule, raise the existing `job_failed:<kind>` alert, whichever runtime (Python or Go) should claim it. On 2026-11-12 `posthog`, `meta_capi` and `deadlines` rows sat unclaimed for about 7 h (Python skips `UBYHOST_GO_JOB_KINDS`, the Go container had the old env, `enqueue()` keeps one open row per kind) and no alert fired.

## 2. Context

Tier B (jobs). The PR states: no new outbound request, no new personal data, no new dependency, no new translation string.

Facts (verified at the base commit):

- `App/app/jobqueue.py` imports `logging, os, socket, threading`, `datetime, timedelta, timezone`, `Callable, Optional`, and `from . import config, db`. `log = logging.getLogger("ubyhost.jobqueue")`. `LEASE_MINUTES = 60`.
- `_stamp(delta)` returns ISO UTC text with no microseconds, the same format `db.utcnow()` writes; `claim()` compares `run_at`/`locked_at` as strings against `_stamp(...)`.
- `_interval(kind)` imports `scheduler` lazily inside the function. `scheduler.job_intervals()` maps kind to minutes (`deadlines` 30, `posthog` 15, `push` 1, ...). `scheduler.late_after_minutes(m)` is `2*m`, plus 15 when `m < 15`.
- `scheduler._job_failed(job_id)` raises or refreshes the alert with `dedupe_key=f"job_failed:{job_id}"` (level from `_JOB_LEVELS`). It is resolved when the job next succeeds (Python `_job_ok` or Go `recordOK`), so this brief adds no resolve code.
- `drain()` ends with this exact text (the insertion point is its first lines):

```python
def drain(run: Callable[[str], None], stop: threading.Event, limit: int = 50) -> int:
    """Claim and run up to ``limit`` due jobs; the number run."""
    ran = 0
```

- Module docstring ends with `lock, so a slow job never holds a row\nlock.\n"""`.
- Tests: `App/tests/test_job_queue.py` has fixture `job_db`, helper `_insert(kind, run_at=None, locked_at=None, locked_by=None, done_at=None, attempts=0)`, decorator `needs_postgres`, and imports `config, db, jobqueue, scheduler`, `threading`, `timedelta`, `pytest`. Last test in the file is `test_fourteen_kinds_queued_still_takes_the_scheduler_lock_once`.
- `docs/ENVIRONMENT.md` line 52 is the `UBYHOST_JOB_QUEUE_KINDS` row and ends `unknown ids stop the worker. |`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/jobqueue.py | edit | `import time`, constants, `stuck_kinds`, `watch_stuck`, throttled call in `drain`, docstring sentence |
| App/tests/test_job_queue.py | edit | append 5 tests |
| docs/ENVIRONMENT.md | edit | one sentence on line 52 |
| docs/tasks/1174-report.md | create | your report (§9) |

No other file may change.

## 4. Steps

**Step 1: jobqueue.py, imports, docstring, constants.**

1a. `grep -nF "import threading" App/app/jobqueue.py`. Directly after that line add a line `import time`.

1b. `grep -nF "lock, so a slow job never holds a row" App/app/jobqueue.py`. The docstring's last text line is `lock.` Replace that line `lock.` with:

```
lock. ``drain`` also checks, at most every 5 minutes, for open rows nobody has
claimed past twice their interval and raises the ``job_failed`` alert for
them, so a missing consumer (for example a Go container with an old
``UBYHOST_GO_JOB_KINDS``) is noticed.
```

1c. `grep -nF "WORKER_ID = " App/app/jobqueue.py`. Directly after that line add:

```python
STUCK_CHECK_SECONDS = 300
_last_stuck_check = 0.0
```

**Step 2: jobqueue.py, add two functions.** Insert them directly before the line `def drain(run: Callable[[str], None], stop: threading.Event, limit: int = 50) -> int:` (leave two blank lines before it and after the new code):

```python
def stuck_kinds() -> list[str]:
    """Queued kinds with an open, unleased row older than twice the job interval."""
    _require_postgres()
    from . import scheduler

    intervals = scheduler.job_intervals()
    rows = db.query(
        "SELECT kind, MIN(run_at) AS run_at FROM job "
        "WHERE done_at IS NULL AND dead_at IS NULL "
        "AND (locked_at IS NULL OR locked_at < ?) GROUP BY kind",
        (_stamp(-timedelta(minutes=LEASE_MINUTES)),),
    )
    stuck = []
    for row in rows:
        kind = row["kind"]
        if kind not in config.JOB_QUEUE_KINDS or kind not in intervals:
            continue
        limit = _stamp(-timedelta(minutes=scheduler.late_after_minutes(intervals[kind])))
        if row["run_at"] < limit:
            stuck.append(kind)
    return sorted(stuck)


def watch_stuck() -> list[str]:
    """Raise the ``job_failed`` alert for every stuck kind; never raises."""
    try:
        from . import scheduler

        kinds = stuck_kinds()
        for kind in kinds:
            log.warning(
                "queued job %s unclaimed past twice its interval; "
                "is its consumer running? (UBYHOST_GO_JOB_KINDS here: %s)",
                kind,
                sorted(config.GO_JOB_KINDS),
            )
            try:
                scheduler._job_failed(kind)
            except Exception:
                log.exception("stuck job alert for %s not raised", kind)
        return kinds
    except Exception:
        log.exception("stuck job check failed")
        return []
```

**Step 3: jobqueue.py, throttled call in `drain`.** Replace

```python
    """Claim and run up to ``limit`` due jobs; the number run."""
    ran = 0
```

with

```python
    """Claim and run up to ``limit`` due jobs; the number run."""
    global _last_stuck_check
    if time.monotonic() - _last_stuck_check >= STUCK_CHECK_SECONDS:
        _last_stuck_check = time.monotonic()
        watch_stuck()
    ran = 0
```

Run: `cd App && .venv/bin/python -c "import app.jobqueue" 2>&1 | tail -30`. Commit `1174 step 1-3`.

**Step 4: tests.** Append to the end of `App/tests/test_job_queue.py` (two blank lines before the first new test):

```python
def _clear_alert(kind):
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (f"job_failed:{kind}",))


@needs_postgres
def test_old_unclaimed_row_is_stuck_and_raises_the_job_failed_alert(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    monkeypatch.setattr(config, "GO_JOB_KINDS", frozenset({"deadlines"}))
    _insert("deadlines", run_at=jobqueue._stamp(-timedelta(hours=3)))
    _clear_alert("deadlines")
    try:
        assert jobqueue.stuck_kinds() == ["deadlines"]
        assert jobqueue.watch_stuck() == ["deadlines"]
        alert = db.query_one(
            "SELECT id FROM alert WHERE dedupe_key = 'job_failed:deadlines' AND resolved_at IS NULL"
        )
        assert alert is not None
    finally:
        _clear_alert("deadlines")


@needs_postgres
def test_fresh_row_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert("deadlines")
    assert jobqueue.stuck_kinds() == []


@needs_postgres
def test_old_row_under_a_live_lease_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert(
        "deadlines",
        run_at=jobqueue._stamp(-timedelta(hours=3)),
        locked_at=jobqueue._stamp(),
        locked_by="other:1",
    )
    assert jobqueue.stuck_kinds() == []


@needs_postgres
def test_old_row_of_a_kind_off_the_queue_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"posthog"}))
    _insert("deadlines", run_at=jobqueue._stamp(-timedelta(hours=3)))
    assert jobqueue.stuck_kinds() == []


def test_drain_checks_for_stuck_rows_at_most_once_per_window(monkeypatch):
    calls = []
    monkeypatch.setattr(jobqueue, "watch_stuck", lambda: calls.append(1) or [])
    monkeypatch.setattr(jobqueue, "claim", lambda: None)
    monkeypatch.setattr(jobqueue, "_last_stuck_check", 0.0)
    assert jobqueue.drain(lambda kind: None, threading.Event()) == 0
    assert jobqueue.drain(lambda kind: None, threading.Event()) == 0
    assert calls == [1]
```

Run the §6 command.

**Step 5: docs/ENVIRONMENT.md.** `grep -nF "unknown ids stop the worker. |" docs/ENVIRONMENT.md`. On that line (the `UBYHOST_JOB_QUEUE_KINDS` row) replace `unknown ids stop the worker. |` with `unknown ids stop the worker. An open row unclaimed past twice its interval (Python or Go consumer missing) raises the `job_failed` alert for that job. |`. Run `cd .. && python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root. Commit `1174 step 4-5`.

## 5. Do not touch

- App/app/scheduler.py, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/reporting.py, App/app/filing_watchdog.py, anything under go/: other open PRs change them.
- `claim()`, `enqueue()`, `fail()`, `finish()`, `purge()` bodies.
- AGENTS.md rules 4 and 5: no new dependency; SQL only through `db.query`/`db.execute`.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_job_queue.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass. The Postgres tests are skipped when `UBYHOST_DATABASE_URL` is unset; say so in the report (do not call that a failure). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error for this file.

## 7. Acceptance

- [ ] `grep -nF "def stuck_kinds" App/app/jobqueue.py` and `grep -nF "def watch_stuck" App/app/jobqueue.py` each find one line.
- [ ] `git diff --stat` lists only the four §3 files.
- [ ] The §6 pytest command ends with no failures.
- [ ] `watch_stuck` has a `try/except Exception` around its whole body.
- [ ] The ENVIRONMENT.md sentence is on the `UBYHOST_JOB_QUEUE_KINDS` row only.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change (for example `scheduler._job_failed` raising `KeyError` for a kind: report it, do not edit scheduler.py);
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1174-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- App/app/jobqueue.py (the new `drain` hook runs every 15 s; check the throttle and that `watch_stuck` cannot raise).
- App/tests/test_job_queue.py (alert rows cleaned up).

## Owner steps

1. Merge the PR when CI is green (`scripts/merge-pr-on-green.sh`).
2. After the deploy, an unclaimed queued row older than twice its interval shows as the existing "job failed" alert in the host alerts; it clears when the job next succeeds.
