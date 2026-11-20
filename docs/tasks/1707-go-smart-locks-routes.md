# 1707: Go smart locks 2: smart-locks page and actions (replaces blocked 1526)

Status: todo — ready for executor (exact-diff pass 2026-11-20).
Depends on: 1706, 1704 | Base commit: current tip of the working branch | Branch: task/1707-go-smart-locks-routes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1707 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1707 step'`.

## 1. Objective

Port the four smart-lock routes. Brief 1526 is already marked `Status: replaced by 1707` (no edit here).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 712-858; `docs/plans/ttlock-door-codes.md` section 6 states.

**Routes in scope (method path, Python function):**

- GET /smart-locks (smart_locks_page)
- POST /smart-locks/setup
- POST /smart-locks/refresh
- POST /smart-locks/remove

**Risk:** Door codes.

**Parity method:** golden script `App/scripts/go_smart_locks_golden.py` records signed-out POST redirects; expand cases when the Go mux test harness grows (accepted difference until then).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1707-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `0b00459cc6836122f7fe2d2aa61c24c565ee0043035b99174cf1fbc5e598c466` | `App/scripts/go_smart_locks_golden.py` | create |
| `5089186a90dce97bfe570d13bc1faaf59f18098f75964c7cfadce4aecc462ed7` | `App/tests/test_go_smart_locks_golden.py` | create |
| `392c1276c73ee944cdd6bd39c49375fda3c9901e1790f3dba163de5fb20ab883` | `go/cmd/ubyhost-web/register_web_properties_smart_locks.go` | create |
| `710e3c50c5ef6f94ad46dd0b591f0acf617439ebdde4adad36e1c6779a3c41ed` | `go/cmd/ubyhost-web/register_web_properties_smart_locks_test.go` | create |
| `3f7c6c40cefaa5c66bc606db0e09759b25e96250535bcbb99695f72c409004ae` | `go/internal/web/properties/smart_locks.go` | create |
| `65c257b2b47caabdd130461eecb7c6ff1d1a5e84969c48efceee4f0a33089e46` | `go/internal/web/properties/smart_locks_test.go` | create |
| `5336dd66114ac9f54c9527186565c0d2c9e3b3e45f593ca7c7828758f2bcace2` | `go/internal/web/properties/testdata/smart_locks_golden.json` | create |
| `a3adcfceeee3be999301318ff68dbfe381a872eb8073bde9a47db499074c6cbb` | `go/internal/web/properties/smartlocks/i18n.json` | create |

Full manifest: `docs/tasks/1707-files/MANIFEST.sha256`.

**Verified by the brief writer (dry-run copy):** `gofmt -l` empty on copied `smart_locks.go`; `go build ./internal/web/properties/...` OK; `go test ./cmd/ubyhost-web/ -run TestSmartLocksPostRoutesRegistered` OK with sidecars copied.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/smart_locks.go` | create | routes |
| `go/internal/web/properties/smart_locks_test.go` | create | golden parity and route tests |
| `go/internal/web/properties/testdata/smart_locks_golden.json` | create | golden written by the Python script |
| `go/internal/web/properties/smartlocks/i18n.json` | create | flash strings for POST handlers |
| `go/cmd/ubyhost-web/register_web_properties_smart_locks.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_properties_smart_locks_test.go` | create | route registration test |
| `App/scripts/go_smart_locks_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_smart_locks_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1707-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1707-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). See `docs/tasks/1707-files/ANCHORS.txt` (`ls … No such file` → `1` for each new path; `find … | wc -l` → `9`).
1. Copy the sidecars to their repo paths and run `sha256sum -c docs/tasks/1707-files/MANIFEST.sha256`: all OK.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_smart_locks_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- State machine transitions use `go/internal/statemachine`; an ambiguous delete never reports success (as in brief 1155).
- Golden parity with the fake TTLock server.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1707 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1707-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Wave P2: add `/smart-locks /smart-locks/*` only after the owner acceptance test of the TTLock plan (section 12) and `ttlock-check.sh` is green.
- **Rollback:** Trim the path line.

## Owner steps

Run the section 12 acceptance test of the TTLock plan on staging with one real lock before the path is added.
