# 1250-fix-2: pin the Go guide_import.status writers

Status: review
Depends on: [1250-fix-1](1250-fix-1-go-guide-import-review.md) | Base commit: a83df541 | Branch: task/1250-go-guide-import
Executor: Haiku 5.5 | Fits one session: yes | Tier B

## 1. Objective

CI `test` fails until `App/tests/test_sm_queues.py` pins the Go writers in `go/internal/guideimport/job.go` (`ProcessQueue` 2, `runOne` 4, `merge` 1, `noteFailure` 1), the same way the file already pins Python and other Go jobs.

## 2. Context

The scanner names a writer by its enclosing Go func. Every pinned writer needs a move; each move's fragment must appear in that func's text. `runOne` has 4 writes: claim (queued→running), cancelled fetch (running→failed, fix-1), fetch error (running→failed), done (running→done).

Exact anchors in `App/tests/test_sm_queues.py` before this edit:

```text
IMPORT = "App/app/guest_guide_import.py"
MERGE = "App/app/guest_guide_merge.py"
```

Inside `IMPORT_SITES`, after `(MERGE, "_note_failure"): 1,` (still present after the edit).

Inside `IMPORT_MOVES`, insert the new rows after this line (exact text):

```text
    (MERGE, "_note_failure", "SET status = 'failed', error = ?, raw_json = NULL", ("done",), "failed"),
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_sm_queues.py` | edit | guide_import `GOIMPORT` pins only |

No other file may change.

## 4. Steps

### Step 1. Pins

After the line `MERGE = "App/app/guest_guide_merge.py"` add:

```python
GOIMPORT = "go/internal/guideimport/job.go"
```

In `IMPORT_SITES`, after `(MERGE, "_note_failure"): 1,` add:

```python
    (GOIMPORT, "ProcessQueue"): 2,
    (GOIMPORT, "runOne"): 4,
    (GOIMPORT, "merge"): 1,
    (GOIMPORT, "noteFailure"): 1,
```

In `IMPORT_MOVES`, after the `(MERGE, "_note_failure", "SET status = 'failed', error = ?, raw_json = NULL", ("done",), "failed"),` line add:

```python
    (GOIMPORT, "ProcessQueue", "SET status = 'failed', error = 'budget'", ANY, "failed"),
    (GOIMPORT, "ProcessQueue", "SET status = 'failed', error = 'stale'", ("running",), "failed"),
    (GOIMPORT, "runOne", "SET status = 'running', started_at = $1 WHERE id = $2 AND status = 'queued'", ("queued",), "running"),
    (GOIMPORT, "runOne", "SET status = 'failed', error = 'network'", ("running",), "failed"),
    (GOIMPORT, "runOne", "SET status = 'failed', error = $1, finished_at = $2 WHERE id = $3 AND status = 'running'", ("running",), "failed"),
    (GOIMPORT, "runOne", "SET status = 'done', raw_json = $1", ("running",), "done"),
    (GOIMPORT, "merge", "SET status = 'used', raw_json = NULL", ("done",), "used"),
    (GOIMPORT, "noteFailure", "SET status = 'failed', error = $1, raw_json = NULL", ("done",), "failed"),
```

Command:

```bash
cd App && .venv/bin/python -m pytest tests/test_sm_queues.py::test_guide_import_writers_match_import_transitions -q --tb=short 2>&1 | tail -5
```

Expected: `1 passed`. Commit: `1250-fix-2 step 1: pin Go guide_import writers`.

## 5. Do not touch

Go code, every other test file, `App/app/`. Hard rule 5 (SQL fragments must match Go source text).

## 6. Commands

From `App/`:

```bash
.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short 2>&1 | tail -30
```

Expected: all tests in the file pass (including `test_guide_import_writers_match_import_transitions`).

## 7. Acceptance

- [ ] `test_sm_queues.py` passes; only that file changed.
- [ ] Every `GOIMPORT` fragment in §4 appears verbatim in `go/internal/guideimport/job.go`.

## 8. Stop and ask

Stop, and write the report, if:

- a fragment assert fails (report the message; do not change Go code);
- a test fails twice;
- you reach 25 tool calls;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1250-fix-2-report.md` (600 tokens at most, `Status: review`): diff stat, command tail, §7 ticked, deviations, questions, owner steps. Set this brief `Status: review`. Commit.

## Risk list (for the reviewer)

`App/tests/test_sm_queues.py` guide_import rows only: wrong func name or SQL fragment breaks CI on the next queue-writer change.

## Owner steps

None. The orchestrator pushes the branch.
