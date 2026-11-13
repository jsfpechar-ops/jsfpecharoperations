# 1250-fix-2: pin the Go guide_import.status writers

Status: review
Depends on: 1250-fix-1 | Branch: task/1250-go-guide-import
Executor: Haiku 5.5 | Fits one session: yes. Tier B.

## 1. Objective
CI `test` fails: `tests/test_sm_queues.py::test_guide_import_writers_match_import_transitions` now finds the Go writers in `go/internal/guideimport/job.go` (ProcessQueue 2, runOne 4, merge 1, noteFailure 1). Pin them, as the file already does for pushsend and metacapi.

## 2. Context
The scanner names a writer by its enclosing Go func. Every pinned writer needs a move; each move's fragment must appear in that func's text. `runOne` has 4 writes: claim (queued→running), cancelled fetch (running→failed, fix-1), fetch error (running→failed), done (running→done).

## 3. Files
- `App/tests/test_sm_queues.py` (edit, only the guide_import section)

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
In `IMPORT_MOVES`, after the `(MERGE, "_note_failure", ...)` line add:
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
Commit: `1250-fix-2 step 1: pin Go guide_import writers`.

## 5. Do not touch
Go code, every other test file, App/app/.

## 6. Commands
From `App/`: `.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short 2>&1 | tail -30`

## 7. Acceptance
- [ ] test_sm_queues.py passes; only that file changed.

## 8. Stop and ask
A fragment assert fails: stop and report the message, do not change Go code.

## 9. Report
Write `docs/tasks/1250-fix-2-report.md` (Status: review, commands and tail), set this brief to Status: review, commit.
