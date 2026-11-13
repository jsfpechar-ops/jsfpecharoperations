# 1340-fix-1: golden script env guard and review follow-ups

Status: review
Depends on: 1340 | Base commit: 8be0d4333 | Branch: task/1340-go-billing-pages (stay on it; no push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The golden script must never touch a real database: it ignores an exported `UBYHOST_DB` today and would wipe tables there. Also add one comment in engine.go and a follow-ups section in the 1340 report.

## 2. Context

Rule 5 and 3: no real data touched. Excerpts must match verbatim, else STOP (§8).

`App/scripts/billing_engine_golden.py` (end of file, at base commit `8be0d4333`):
```python
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "billing_engine_golden.sqlite3"))
```
`go/internal/billing/engine.go` (in `periodState.total`):
```go
	if err != nil {
		return 0, fmt.Errorf("%w: %v", ErrUnknownPlan, err)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/scripts/billing_engine_golden.py | edit | step 1 |
| go/internal/billing/engine.go | edit | step 2, comment only |
| docs/tasks/1340-report.md | edit | step 3, append |
| docs/tasks/1340-fix-1-golden-env.md | edit | Status line only |
| docs/tasks/1340-fix-1-report.md | create | §9 |

No other file may change.

## 4. Steps

1. In billing_engine_golden.py replace the three lines above with:
```python
    if os.environ.get("UBYHOST_DATABASE_URL"):
        sys.exit("refusing to run: UBYHOST_DATABASE_URL is set; this script wipes tables")
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ["UBYHOST_DATA_DIR"] = str(tmp)
    os.environ["UBYHOST_DB"] = str(tmp / "billing_engine_golden.sqlite3")
```
Keep the two following `setdefault` lines (SECRET_KEY, ENABLE_SCHEDULER) and the rest unchanged.
2. In engine.go insert, between `if err != nil {` and the `return 0, fmt.Errorf("%w: %v", ErrUnknownPlan, err)` line, this line (one tab indent):
```go
		// An out-of-range discount also lands here; the billing_account discount CHECK makes that unreachable.
```
3. Append to the end of docs/tasks/1340-report.md (blank line first):
```markdown

## Review (Opus) follow-ups

For the page brief:

- Go adds `ORDER BY id` to the open-invoice reissue query; Python has none. Harmless.
- Place check-then-update is not atomic: a double submit can issue two invoices, same as Python.
- A zero `today` means local now.
- CI has no guard that fails when the Go DB tests skip.
```
4. Run §6, write the report, commit once per step: message `1340-fix-1 step k` plus a blank line and the two trailer lines:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7PxGCxDzrj8mFfHxiP
```

## 5. Do not touch

Everything outside §3, `go/internal/billing/testdata`, secrets, `.env`. Do not push.

## 6. Commands

From repo root unless noted; each ends `| tail -30`.
- `gofmt -l go/internal/billing/ | tail -30` : no output.
- `cd go && go vet ./internal/billing/ 2>&1 | tail -30` : no output.
- `cd App && UBYHOST_DB=/nonexistent/x.sqlite3 .venv/bin/python scripts/billing_engine_golden.py 2>&1 | tail -30` : `wrote .../engine_golden.json` (proves the env DB is ignored).
- `cd App && UBYHOST_DATABASE_URL=x .venv/bin/python scripts/billing_engine_golden.py 2>&1 | tail -30` : `refusing to run: ...`, exit 1.
- `git status --porcelain go/internal/billing/testdata | tail -30` : empty.
- `cd App && .venv/bin/python -m pytest tests/test_billing_engine_golden.py -q --tb=short -x 2>&1 | tail -30` : `1 passed`.
- `python3 scripts/context_lint.py | tail -30` : `context lint: OK` (a status.md WARN is fine).

## 7. Acceptance

- [ ] Both env vars assigned unconditionally; exit before any other work when `UBYHOST_DATABASE_URL` is set.
- [ ] Golden JSON byte-identical (testdata clean).
- [ ] engine.go diff is the one comment line.
- [ ] Report section appended; all §6 outputs as expected.

## 8. Stop and ask

Stop and write the report as `blocked` if: an excerpt is not found; a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change; push, merge or secrets are needed.

## 9. Report

Write `docs/tasks/1340-fix-1-report.md` (600 tokens at most), set `Status: review`: files changed (`git diff --stat`), each command with last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

App/scripts/billing_engine_golden.py (the guard and the unconditional env).

## Owner steps

None (the orchestrator pushes with the rest of the branch).
