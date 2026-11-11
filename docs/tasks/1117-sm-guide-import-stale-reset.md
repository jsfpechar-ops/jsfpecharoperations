# 1117: A guide import row left `running` by a dead worker: fail it after a cutoff

Status: todo
Depends on: PR #920 merged to main (tables and pin tests present) | Base commit: main after PR #920 | Branch: task/1117-sm-guide-import-stale-reset
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## Open questions

- **Timestamp column.** `guide_import.started_at` exists (migration `App/app/migrations/0016_guide_import.sql`) and `_run_one()` sets it in the same statement that sets `running`. So the reset needs no new column and no migration.
- **Not reproducible as a live crash, reproducible as a state.** The fault is "a row stays `running` when nothing is running it". The test builds that state by inserting the row; it does not kill a process. That is the whole fault, because nothing else ever reads or moves a `running` row.
- **Doc drift, not fixed here.** The docstring of `process_queue` says "Called by the worker every minute". The scheduler job `guide_import` runs every 60 minutes (`App/app/scheduler.py:104`, `docs/context/job-ownership.md`). So a stuck row is failed on the first hourly run after the cutoff: at most about 75 minutes after it started. The owner may want a shorter interval; not part of this brief.
- A worker restart during a deploy while a run is in flight also leaves that run's paid Apify call unfinished; it cannot be recovered, only the row can.

## 1. Objective

At the start of `process_queue()`, one guarded UPDATE moves every `guide_import` row that has been `running` for longer than a fixed cutoff to `failed` with `error = 'stale'`. Today such a row stays `running` for good.

## Decisions taken (owner may overrule)

1. **`failed`, not back to `queued`.** An import calls a paid AI-scraper (Apify) and fetches a host's URL. A run that died may already have been billed, and `_count_run()` has already counted it. An automatic re-run could pay twice per crash and could loop on a row that crashes the worker. A `failed` row does not use the property's one import up (`used_sources` ignores `failed`), so the host can start a new import with one click.
2. **Cutoff: `STALE_RUNNING = timedelta(seconds=5 * sum(HTTP_TIMEOUT))`.** `HTTP_TIMEOUT = (10, 150)`, so 5 x 160 s = 800 s, about 13 minutes. One run is bounded by `HTTP_TIMEOUT` (Apify answers 408 at `config.APIFY_TIMEOUT`, 120 s by default, before our 150 s read timeout). The factor 5 is the margin: a healthy run is never failed while it works. It stays far below the 60 minute job interval.
3. **The reset runs before the `enabled()` check.** It needs no Apify token, and a row must not stay `running` because the token was removed.
4. **Language: Python**, because the only writer of `guide_import.status` lives in the Python worker (plan, "Language rule"); there is no Go twin (`grep -rln guide_import go` finds nothing).
5. **Error text `stale`**: a short code like the others (`network`, `timeout`, `budget`); the host page shows its generic "Did not work" badge for any `failed` row and never prints the code.

## 2. Context

Rules that bind this brief (AGENTS.md): SQL through `db` helpers, Postgres-portable; no new dependency; no migration; no template change; never push to `main`; tests only from the test-map row.

### What the host sees today for a `running` row (verified in code)

`App/app/templates/guest_guide.html` line 37 and `App/app/templates/leon_setup/import.html` line 7 show the "running" badge for `queued` and `running`, and `request_imports()` refuses a new import for the property while a `queued` or `running` row exists ("busy"). So a stuck row shows "running" forever and blocks the host from starting another import.

### The fault, in code (verified)

`App/app/guest_guide_import.py`, `_run_one()` claims the row:

```python
    db.execute(
        "UPDATE guide_import SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
        (db.utcnow(), import_id),
    )
```

and only `_run_one()` then writes `done` or `failed` (`WHERE id = ?`). `process_queue()` selects only `status = 'queued'` rows. Nothing selects or moves a `running` row, so a process that dies between the claim and the finish (a deploy restarts the worker) leaves it `running`. `started_at` is `db.utcnow()`: ISO 8601 with `+00:00`, no microseconds, so text comparison with a cutoff in the same format is correct (the same form `mail.drain` uses).

### The pattern copied

`App/app/mail.py`, `drain()`:

```python
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).replace(microsecond=0).isoformat()
    db.execute(
        "UPDATE email_outbox SET state = ? WHERE state = ? AND updated_at < ?",
        (QUEUED, SENDING, stale),
    )
```

### Compare-and-swap and zero rows

The new statement is a single `UPDATE ... WHERE status = 'running' AND started_at < ?`: the old state is in the WHERE, no read first. If zero rows match (the normal case), `db.execute` returns 0, nothing is logged, and the function continues exactly as today with the queued rows. A row whose `started_at` is NULL never matches (NULL < x is not true); `_run_one()` always sets it at claim, so that cannot occur for a row it claimed. If a live `_run_one()` finishes the same instant, its row is `done` or `failed` already and the guard skips it; if the reset wins the race, `_run_one()`'s later unguarded `done` write overwrites `failed`, which is correct (the data was fetched).

Anchors: if an anchor or excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_guest_guide_import.py` | edit | import line, new test at the end |
| `App/app/guest_guide_import.py` | edit | constant `STALE_RUNNING`, reset in `process_queue`, one comment |
| `App/tests/test_sm_queues.py` | edit | pin count, new pinned move, docstring line |

No other file may change. `IMPORT_TRANSITIONS` gets no new entry (`running` to `failed` exists); only its comment changes.

## 4. Steps

Work from the repo root unless a step says `App/`. Commit after each step as `1117 step N`.

### Step 1: the import line in the guide import test

File: `App/tests/test_guest_guide_import.py`.

1. Anchor: `grep -nF 'from datetime import date' App/tests/test_guest_guide_import.py | tail -30`. Expected: exactly one line (`4:from datetime import date`).
2. Edit, `old_string` (one line): `from datetime import date`  `new_string`: `from datetime import date, datetime, timedelta, timezone`
3. Check: `grep -nF 'from datetime import date, datetime, timedelta, timezone' App/tests/test_guest_guide_import.py | tail -30`. Expected: one line.

### Step 2: the failing test

File: `App/tests/test_guest_guide_import.py`. Append the block below at the end of the file (keep two empty lines before it), with the Edit tool using this `old_string` (the last two lines of the file) and the `new_string` that repeats them and adds the block:

old_string:

```python
def test_next_leon_redirects_to_the_setup_import_step(ws):
    r = _post2(ws, booking=BOOKING, next_="leon")
    assert r.headers["location"].startswith(f"/apartments/{ws['home']}/leon/setup/import")
```

new_string:

```python
def test_next_leon_redirects_to_the_setup_import_step(ws):
    r = _post2(ws, booking=BOOKING, next_="leon")
    assert r.headers["location"].startswith(f"/apartments/{ws['home']}/leon/setup/import")


# --- 1117: a row left running by a dead worker --------------------------------


def test_a_row_left_running_is_failed_after_the_cutoff_and_a_fresh_one_is_not(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(gi.requests, "post", _fake_post(calls, body=[AIRBNB_ITEM]))
    now = datetime.now(timezone.utc)

    def stamp(seconds_ago):
        return (now - timedelta(seconds=seconds_ago)).replace(microsecond=0).isoformat()

    old = db.insert("guide_import", {
        "apartment_id": ws["home"], "source": "booking", "url": "https://www.booking.com/hotel/cz/vivus-3.html",
        "status": "running", "created_at": stamp(7200), "started_at": stamp(3600),
    })
    fresh = db.insert("guide_import", {
        "apartment_id": ws["home"], "source": "airbnb", "url": "https://www.airbnb.com/rooms/53997462",
        "status": "running", "created_at": stamp(60), "started_at": stamp(60),
    })
    assert gi.process_queue() == 0
    row = db.query_one("SELECT status, error, finished_at, raw_json FROM guide_import WHERE id = ?", (old,))
    assert (row["status"], row["error"], row["raw_json"]) == ("failed", "stale", None)
    assert row["finished_at"]
    row = db.query_one("SELECT status, error, finished_at FROM guide_import WHERE id = ?", (fresh,))
    assert (row["status"], row["error"], row["finished_at"]) == ("running", None, None)
    assert calls == []  # nothing was fetched again: a dead run is never re-run on its own
    assert gi.in_progress(ws["home"])  # the fresh row still counts as busy
```

4. Check: `grep -nF 'def test_a_row_left_running_is_failed_after_the_cutoff' App/tests/test_guest_guide_import.py | tail -30`. Expected: one line.

### Step 3: the test fails on today's code

From `App/`: `.venv/bin/python -m pytest tests/test_guest_guide_import.py -q --tb=short -x -k left_running 2>&1 | tail -30`.

Expected: FAIL at the first row assertion, `assert ('running', None, None) == ('failed', 'stale', None)` (the old row is still `running`). That is the fault shown on today's code. The test uses fixed ages (1 hour and 60 seconds) and does not name the new constant, so it runs before the fix.

If it fails with a different error (for example a fixture error), STOP.

Commit: `git add App/tests/test_guest_guide_import.py && git commit -m "1117 step 3" 2>&1 | tail -30`.

### Step 4: the cutoff constant

File: `App/app/guest_guide_import.py`.

1. Anchor: `grep -nF 'HTTP_TIMEOUT = (10, 150)' App/app/guest_guide_import.py | tail -30`. Expected: exactly one line.
2. Edit, `old_string` (one line): `HTTP_TIMEOUT = (10, 150)`  `new_string`:

```python
HTTP_TIMEOUT = (10, 150)
# 1117: a row `running` for longer than this has lost its worker (a deploy restart).
# One run is bounded by HTTP_TIMEOUT; the factor 5 is the margin (800 s).
STALE_RUNNING = timedelta(seconds=5 * sum(HTTP_TIMEOUT))
```

3. Check: `cd App && .venv/bin/python -c "from app import guest_guide_import as g; print(int(g.STALE_RUNNING.total_seconds()))" 2>&1 | tail -30`. Expected: `800`.

### Step 5: the reset in `process_queue`

File: `App/app/guest_guide_import.py`.

1. Anchor: `grep -nF '"""Run queued imports, oldest first. Called by the worker every minute."""' App/app/guest_guide_import.py | tail -30`. Expected: exactly one line, followed by `    if not enabled():`.
2. Edit, `old_string` (two lines):

```python
    """Run queued imports, oldest first. Called by the worker every minute."""
    if not enabled():
```

`new_string`:

```python
    """Run queued imports, oldest first. Called by the worker every minute."""
    # 1117: fail a row a dead worker left `running`. Failed, not queued again: a run
    # calls a paid actor, so it is never repeated on its own. Zero rows is the normal case.
    cutoff = (datetime.now(timezone.utc) - STALE_RUNNING).replace(microsecond=0).isoformat()
    reset = db.execute(
        "UPDATE guide_import SET status = 'failed', error = 'stale', finished_at = ? "
        "WHERE status = 'running' AND started_at < ?",
        (db.utcnow(), cutoff),
    )
    if reset:
        log.warning("guide import: %s stale running row(s) failed", reset)
    if not enabled():
```

3. Check and commit: `cd App && .venv/bin/python -c "import app.guest_guide_import" 2>&1 | tail -30` (expected: no output), then from the repo root `git add App/app/guest_guide_import.py && git commit -m "1117 step 4 and 5" 2>&1 | tail -30`.

### Step 6: the comment on the table entry

File: `App/app/guest_guide_import.py`. The table content does not change.

1. Anchor: `grep -nF '"running": {"done", "failed"},  # _run_one()' App/app/guest_guide_import.py | tail -30`. Expected: exactly one line.
2. Edit, `old_string` (one line): `    "running": {"done", "failed"},  # _run_one()`  `new_string`: `    "running": {"done", "failed"},  # _run_one(); process_queue() fails a stale one (1117)`
3. Check and commit: `grep -nF 'process_queue() fails a stale one (1117)' App/app/guest_guide_import.py | tail -30` (one line), then `git add App/app/guest_guide_import.py && git commit -m "1117 step 6" 2>&1 | tail -30`.

### Step 7: the new test passes

From `App/`: `.venv/bin/python -m pytest tests/test_guest_guide_import.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (0 failed). Fails twice: STOP.

### Step 8: pin test, the writer count

File: `App/tests/test_sm_queues.py`.

1. Anchor: `grep -nF '(IMPORT, "process_queue"): 1,' App/tests/test_sm_queues.py | tail -30`. Expected: one line.
2. Edit, `old_string` (one line): `    (IMPORT, "process_queue"): 1,`  `new_string`: `    (IMPORT, "process_queue"): 2,`

### Step 9: pin test, the new move

File: `App/tests/test_sm_queues.py`.

1. Anchor: `grep -nF "error = 'budget'\", ANY, \"failed\")," App/tests/test_sm_queues.py | tail -30`. Expected: one line.
2. Edit, `old_string` (one line):

```python
    (IMPORT, "process_queue", "SET status = 'failed', error = 'budget'", ANY, "failed"),
```

`new_string` (that line, then the new one):

```python
    (IMPORT, "process_queue", "SET status = 'failed', error = 'budget'", ANY, "failed"),
    (IMPORT, "process_queue", "SET status = 'failed', error = 'stale'", ("running",), "failed"),
```

### Step 10: pin test, the docstring

File: `App/tests/test_sm_queues.py`.

1. Anchor: `grep -nF 'Nothing moves a guide_import row out of running except _run_one() itself, so' App/tests/test_sm_queues.py | tail -30`. Expected: one line.
2. Edit, `old_string` (two lines):

```
- Nothing moves a guide_import row out of running except _run_one() itself, so
  a worker that dies mid-run leaves the row running for good.
```

`new_string`:

```
- guide_import: a worker that dies mid-run leaves the row running; since brief
  1117 process_queue() fails such a row (guarded, started_at older than
  STALE_RUNNING). _run_one() still writes done / failed with WHERE id = ? only.
```

3. Run and commit: from `App/`: `.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short -x 2>&1 | tail -30`. Expected: `4 passed`. Then from the repo root: `git add App/tests/test_sm_queues.py && git commit -m "1117 step 8 to 10" 2>&1 | tail -30`. Do not edit any other pin to make it pass; a "pinned code changed" message means STOP.

### Step 11: the test-map row

Row "Guest guide" in `docs/context/test-map.md`: `test_guest_guide*.py` (covers `test_guest_guide_import.py`), plus `test_sm_queues.py`. From `App/`: `.venv/bin/python -m pytest tests/test_guest_guide_import.py tests/test_sm_queues.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

### Step 12: context lint

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no errors.

### Step 13: report

Write `docs/tasks/1117-report.md` per §9, set `Status: review` at the top of this brief, commit as `1117 step 13`, open one draft PR.

## 5. Do not touch

`App/app/migrations/`, `App/migrations_pg/` (no schema change), templates, `scheduler.py` (the 60 minute interval stays), `guest_guide_merge.py`, `_run_one()`, any Go file, `db.py`. No new dependency (rule 4). No change to `IMPORT_TRANSITIONS` entries.

## 6. Commands

- Step 3: `cd App && .venv/bin/python -m pytest tests/test_guest_guide_import.py -q --tb=short -x -k left_running 2>&1 | tail -30` expects FAIL at `('failed', 'stale', None)`.
- Step 7: `cd App && .venv/bin/python -m pytest tests/test_guest_guide_import.py -q --tb=short -x 2>&1 | tail -30` expects pass.
- Step 10: `cd App && .venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short -x 2>&1 | tail -30` expects `4 passed`.
- Step 11: both files together, expects pass.
- Step 12: `python3 scripts/context_lint.py 2>&1 | tail -30`.
- No Go test: no Go file changes. No browser test: no template or CSS changes.

## 7. Acceptance

- [ ] Step 3 failed before the fix (old row still `running`), Step 7 passes.
- [ ] `guide_import` row `running` older than 800 s becomes `failed`, `error = 'stale'`, `finished_at` set; a row running for 60 s is untouched (test uses 1 hour and 60 s); no Apify call was made.
- [ ] `test_sm_queues.py`: 4 passed, `process_queue` pinned with 2 writes and the `('running',)` to `failed` move.
- [ ] `git diff --stat` shows only the three files in section 3.
- [ ] Context lint clean.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or excerpt is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency or a migration seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1117-report.md` (600 tokens at most) and set `Status: review`. It has: 1. files changed (`git diff --stat`); 2. each command with the last 5 lines of output; 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

Low risk. Read in full: the `process_queue` hunk in `App/app/guest_guide_import.py` (guard `status = 'running' AND started_at < ?`, cutoff format equals `db.utcnow()` format) and the new test. Check the test is in the `ws` fixture style and makes no real HTTP call.

## Owner steps

1. Overrule or accept the two decisions under "Decisions taken": `failed` instead of re-queue, and the 800 second cutoff.
2. After the PR is green, merge it with `scripts/merge-pr-on-green.sh <PR number>`. Nothing else to do: no setting, no migration.
