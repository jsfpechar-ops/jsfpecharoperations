# 1741: Go filing F2: host send and re-file buttons on Go

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
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

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_submit_golden.py` seeds a throwaway database, renders the real FastAPI app, and writes `go/internal/web/stays/testdata/submit_golden.json`; `submit_test.go` replays the seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Accepted differences belong in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1741-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `c428616db9b286d5a118acbdff47b157d144f44629c171e94db8bfc8a2d7df0f` | `App/scripts/go_submit_golden.py` | create |
| `1dcc8e7206b6f69536c887413ad8707d8fbc5ec6b6407ad9e62a3ab614721c42` | `App/tests/test_go_submit_golden.py` | create |
| `ac6fe852b8b52ed4fc81ac4579ac0211a0fd9cf9e9367a95a668f888bb7b2142` | `go/cmd/ubyhost-web/register_web_stays_submit.go` | create |
| `625d7c564752cb0fa70a6c1fe46f7a09da38b4454ec7c85994dd9d3874cc9cf9` | `go/cmd/ubyhost-web/register_web_stays_submit_test.go` | create |
| `28f75b51f6d2497c2d8c5ae459578cf5af31c55f0bf6b5ca8733a1f07e1cc103` | `go/internal/web/stays/submit.go` | create |
| `14e5e0c6b478be97609beba8c1279b56a5d7ef74140279a4a3739080ca44e7d5` | `go/internal/web/stays/submit_test.go` | create |
| `199fd899bf9f8b5fc1bffa9c883b4366d120fd35c81e9f0ff767b7cbab79cea4` | `go/internal/web/stays/testdata/submit_golden.json` | create |

Full manifest: `docs/tasks/1741-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1741-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/stays/` silent; `go test ./internal/web/stays/... -count=1 -run 'Submit|PluralKey'` OK; `go test ./cmd/ubyhost-web/... -run TestSubmitRoutesRegistered` OK; `pytest tests/test_go_submit_golden.py` OK when `App/.venv` exists. Executor step 3 must add `flash.reservations.sent`, `flash.reservations.reported`, and `flash.reservations.accepted` plural lines to the stays catalog via `go_host_i18n.py` (Python host strings are the source of truth).

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

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1741-files/ANCHORS.txt`):

   - `grep -cF '@router.post("/reservations/submit-ready")' App/app/routes/admin.py | tail -1`
   - `grep -cF '@router.post("/reservations/{reservation_id}/submit")' App/app/routes/admin.py | tail -1`
   - `ls go/internal/web/stays/submit.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1741-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1741-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1741 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_submit_golden.py -q --tb=short -x 2>&1 | tail -30` passes
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
