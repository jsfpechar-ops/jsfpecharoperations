# 1741: Go filing F2: host send and re-file buttons on Go

Status: todo — scoped (final brief 2026-11-15). Executable only after its exact-diff pass: sidecars in `docs/tasks/1741-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1740 soaked a week, 1732, 1742 | Base commit: current tip of the working branch | Branch: task/1741-go-filing-f2-buttons
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1741 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1741 step'`.

## 1. Objective

Port `reservation_submit` and `reservations_submit_ready` so they call the F1 code directly in Go; the buttons then no longer need Python.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 3965-4021 (submit-ready), 4418-4578 (submit).

**Routes in scope (method path, Python function):**

- POST /reservations/submit-ready
- POST /reservations/{reservation_id}/submit

**Risk:** HIGH RISK. Filing.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_go_filing_f2_buttons_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**AI legal review (2026-11-15, Opus-level, not a licensed lawyer; see [go-sqlite-final](../plans/go-sqlite-final.md) section 7):** K-F03 and K-F07 are not legal questions and do not block this brief. Port unchanged and keep the seven conditions listed there (never cancel a filed stay; keep the in-flight defer and the "suspect" early return; keep the deadline rule; send once and never inside a transaction; pause on UbyPort auth failure; keep `signature_dates_stale`). Remaining owner sign-off is per switch.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/submit.go` | create | submit handlers |
| `go/internal/web/stays/submit_test.go` | create | golden parity and route tests |
| `go/internal/web/stays/testdata/submit_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_stays_submit.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_stays_submit_test.go` | create | route registration test |
| `App/scripts/go_submit_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_submit_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1741-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1741-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). The exact-diff pass fills in the `grep -cF` anchor lines for every file this brief edits and the `ls` line proving the new files do not exist yet.
1. Copy the sidecars to their repo paths and run `sha256sum -c` on the table in §2: all OK.
2. Add the golden script and its freshness test; run the script and commit the golden.
3. Add the handlers, templates and i18n keys (`App/scripts/go_host_i18n.py` writes the catalog); `gofmt -l` prints nothing.
4. Register the routes in one new `go/cmd/ubyhost-web/register_web_*.go` file (`init()` through `registerRoutes`); the routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`.
5. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_go_filing_f2_buttons_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Same mock requests and same `submit_state` after each golden scenario; double click sends once (idempotency by state).
- The deadline watchdog (1159) still sees the stay.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1741 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1741-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** With wave H step (4) or after it; owner sign-off.
- **Rollback:** Trim `/reservations/*/submit` from the path line.

## Owner steps

Owner sign-off in the thread before the path is added.
