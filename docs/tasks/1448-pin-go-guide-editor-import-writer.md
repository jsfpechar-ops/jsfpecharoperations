# 1448: pin the Go guide editor's `guide_import.status` writer (CI fix for 1446)

Status: review
Depends on: 1446 (on this branch) | Base commit: the current branch head | Branch: none (one big PR mode)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B. Test file only: no behaviour changes.

**One big PR mode.** Work on the current branch. Commit `1448 step k` after each step that changes a file. Never create a branch, never push, never open a PR.

## 1. Objective

CI on the big PR fails in one test, in both `test` and `test-postgres-full`: `tests/test_sm_queues.py::test_guide_import_writers_match_import_transitions`. Brief 1446 added a new writer of `guide_import.status` in Go (`requestImports` in `go/internal/web/ai/guide_import.go`, the port of Python's `request_imports`). The test pins every writer; add the new one to the pins.

## 2. Context

The new writer, from `go/internal/web/ai/guide_import.go` (function `requestImports`):

```go
		if _, err := s.pool.Exec(ctx, `INSERT INTO guide_import (apartment_id, source, url, status, created_at) VALUES ($1, $2, $3, 'queued', $4)`,
```

It inserts a new row as `queued`, the same move as Python's `request_imports` (`NEW` to `queued`).

The assertion message from CI:

```
Left contains 1 more item:
{('go/internal/web/ai/guide_import.go', 'requestImports'): 1}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_sm_queues.py` | edit | one constant, one site pin, one move |
| `docs/tasks/1448-report.md` | new | your report |
| `docs/tasks/1448-pin-go-guide-editor-import-writer.md` | exists | Status line only |

No other file may change. This is a test-only edit under `App/tests/`; nothing under `App/app/` changes.

## 4. Steps

1. Check the anchors. Command: `grep -c 'RETENTION = "go/internal/retention/steps.go"' App/tests/test_sm_queues.py; grep -c '(RETENTION, "stepGuideImports"): 1,' App/tests/test_sm_queues.py; grep -cF "(RETENTION, \"stepGuideImports\", \"WHEN status = 'done' THEN 'expired'\", (\"done\",), \"expired\")," App/tests/test_sm_queues.py; grep -c 'GOGUIDEWEB' App/tests/test_sm_queues.py; grep -c "VALUES (\$1, \$2, \$3, 'queued', \$4)" go/internal/web/ai/guide_import.go`. Expected: `1`, `1`, `1`, `0`, `1`. Anything else: stop.

2. In `App/tests/test_sm_queues.py`, after the line

   ```python
   RETENTION = "go/internal/retention/steps.go"
   ```

   add the line

   ```python
   GOGUIDEWEB = "go/internal/web/ai/guide_import.go"
   ```

3. In the same file, in `IMPORT_SITES`, after the line

   ```python
       (RETENTION, "stepGuideImports"): 1,
   ```

   add the line

   ```python
       (GOGUIDEWEB, "requestImports"): 1,
   ```

4. In the same file, in `IMPORT_MOVES`, after the line

   ```python
       (RETENTION, "stepGuideImports", "WHEN status = 'done' THEN 'expired'", ("done",), "expired"),
   ```

   add the line

   ```python
       (GOGUIDEWEB, "requestImports", "INSERT INTO guide_import (apartment_id, source, url, status, created_at) VALUES ($1, $2, $3, 'queued', $4)", NEW, "queued"),
   ```

   Command: `git diff --stat | tail -2`. Expected: 1 file changed, 3 insertions.

5. Run section 6. If it passes, commit: `1448 step 5`. Then write the report, set `Status: review`, commit `1448 step 6`.

## 5. Do not touch

Any Go file, anything under `App/app/`, any other test. Do not change how `_check` works to make the test pass.

## 6. Commands

From `App/` (create the virtualenv first if `App/.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
.venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short 2>&1 | tail -6
.venv/bin/python -m ruff check tests/test_sm_queues.py 2>&1 | tail -3
```

Expected: every test in the file passes, 0 failed; ruff reports no error (if ruff is not installed in the venv, say so in the report).

If `test_guide_import_writers_match_import_transitions` still fails, the message names what differs (for example the move text not found in the function body, or the `NEW` rule). Copy the message into the report and stop with `Status: blocked`. Do not guess a different pin.

## 7. Acceptance

- [ ] `tests/test_sm_queues.py`: all passed.
- [ ] `git log --oneline --grep='^1448 step'` shows the commits, and `git show --stat` on them lists only section 3 files.

## 8. Stop and ask

Stop and write the report if an anchor count differs, the test still fails after the three lines are added, or you reach 25 tool calls.

## 9. Report

`docs/tasks/1448-report.md`, 300 tokens at most: the diff stat, the last lines of each command, section 7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

`App/tests/test_sm_queues.py`: the three added lines only.

## Owner steps

None.
