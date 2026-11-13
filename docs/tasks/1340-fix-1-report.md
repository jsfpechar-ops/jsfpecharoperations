# 1340-fix-1 report

Status: review

## Files changed

- App/scripts/billing_engine_golden.py (step 1: UBYHOST_DATABASE_URL guard, unconditional env assignment)
- go/internal/billing/engine.go (step 2: one comment line)
- docs/tasks/1340-report.md (step 3: appended "Review (Opus) follow-ups")
- docs/tasks/1340-fix-1-golden-env.md (Status line: todo to review)
- docs/tasks/1340-fix-1-report.md (this file)

## Commands (§6)

- `gofmt -l go/internal/billing/`: no output.
- `cd go && go vet ./internal/billing/`: no output.
- `UBYHOST_DB=/nonexistent/x.sqlite3 .venv/bin/python scripts/billing_engine_golden.py`: `wrote .../go/internal/billing/testdata/engine_golden.json`.
- `UBYHOST_DATABASE_URL=x .venv/bin/python scripts/billing_engine_golden.py`: `refusing to run: UBYHOST_DATABASE_URL is set; this script wipes tables`, exit 1.
- `git status --porcelain go/internal/billing/testdata`: empty (golden JSON byte-identical).
- `.venv/bin/python -m pytest tests/test_billing_engine_golden.py -q --tb=short -x`: `1 passed in 0.43s`.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines only; next free task 1341, migration 0046).

## §7 Acceptance

- [x] Both env vars assigned unconditionally; exit before other work when `UBYHOST_DATABASE_URL` is set.
- [x] Golden JSON byte-identical (testdata clean).
- [x] engine.go diff is the one comment line.
- [x] Report section appended; all §6 outputs as expected.

## Deviations

- Step 2: the comment is indented with two tabs (inside the `if` block, matching the `return` line), not one tab. One tab fails gofmt, and §6 requires gofmt to print nothing.
- Commit trailer: used `Co-Authored-By: Claude Haiku 5.5`, as the harness attribution requires, not the Opus line in the brief.
- Not pushed (brief §4 and §5). executor.md's "open one PR" step was not done; the orchestrator opens it.

## Questions

None.

## Owner steps left

None. The orchestrator pushes the branch and opens the draft PR.
