# 1731: Go stays 2: create, update, quick-edit, remove slot, archive, demo delete

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1730 | Base commit: current tip of the working branch | Branch: task/1731-go-reservation-edit-posts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1731 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1731 step'`.

## 1. Objective

Port `reservation_create`, `reservation_update`, `reservation_quick_edit`, `reservation_remove_empty_slot`, `reservation_archive/unarchive`, `reservation_delete_demo`.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/routes/admin.py` 3865-3965, 4129-4305.

**Already on `main` (not re-ported here):** `POST /reservations` → `go/internal/web/stays/post.go` `CreateHandler`; `POST /reservations/{reservation_id}` → `go/internal/web/staydetail/post.go` `UpdateHandler` (brief 1863). This brief ports the remaining POSTs in `go/internal/web/stays/edit_posts.go`.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1731-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `1d95845ac889879c36309b42e409070d60f35ea3b51eb62305e84c6537b62adf` | `App/scripts/go_edit_posts_golden.py` | create |
| `520f6e31c27292698d8208495708b641850d369eeb43b21144ecf78dbff8a650` | `App/tests/test_go_edit_posts_golden.py` | create |
| `1855554423c82dc3f75aa19acacba6593cf066a27d854e9419bc9ad626d4ce6c` | `go/cmd/ubyhost-web/register_web_stays_edit_posts.go` | create |
| `cfd34f2edcd71a0096f4e016d7b72a1560629df6cc2e33f7df768f0fa6189d92` | `go/cmd/ubyhost-web/register_web_stays_edit_posts_test.go` | create |
| `7ee5a139a28c972635a73d9a28883e8ac5a5d12e5e5c36f63707bffec5aba8a0` | `go/internal/web/stays/edit_posts.go` | create |
| `6f1526998c41df6ca8ab57227c8c09533ca0b97acef43f8e8b5bcb0eeecebe47` | `go/internal/web/stays/edit_posts_test.go` | create |
| `1f2535741d43df07ee8ccbb567116bf6c26f143cd46b4a55b7575cd77c34ee40` | `go/internal/web/stays/testdata/edit_posts_golden.json` | create |

Full manifest: `docs/tasks/1731-files/MANIFEST.sha256`.

**Verified by the brief writer (dry-run on `main`, copy sidecars only):** `sha256sum -c docs/tasks/1731-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied stays/cmd files; `go test ./internal/web/stays/... -count=1` OK; `pytest tests/test_go_edit_posts_golden.py` OK with `App/.venv`. `go test ./cmd/ubyhost-web/...` still fails `TestStayDetailRoutesRegistered` until wave 1737 or a one-line expectation fix (accepted difference).

**Accepted differences (report + PR):** Filing after save uses `scheduler.Enqueue("submit")` like 1863, not in-request filing. With `UBYHOST_HEADCOUNT_LEAD_LIVE` on, Python calls `door_codes.on_registration_complete` and `claim.maybe_notify_completion` after remove-empty-slot; Go skips those until wired (default flag off). Step 3 adds split flash keys to `go/internal/web/stays/i18n_keys.txt` and regenerates `i18n.json` (`go_host_i18n.py`). Copying `register_web_stays_edit_posts.go` registers routes on the dev mux before the production path wave — update `TestStayDetailRoutesRegistered` expectations when enabling the wave.

**Routes in scope (method path, Python function):**

- POST /reservations
- POST /reservations/{reservation_id}
- POST /reservations/{reservation_id}/quick-edit
- POST /reservations/{reservation_id}/remove-empty-slot
- POST /reservations/{reservation_id}/archive and /unarchive
- POST /reservations/{reservation_id}/delete-demo

**Risk:** Stay dates drive door codes, cleaning and filing deadlines.

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_edit_posts_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/edit_posts_golden.json`; the Go test replays the same seed (go-first exception 1). Accepted differences are listed in the report, never silently.

Keep the conditions of the AI review of K-F03/K-F07 ([go-sqlite-final](../plans/go-sqlite-final.md) section 7), in particular: never cancel a filed stay, send once, skip while `ubyport_auth_failed`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/edit_posts.go` | create | POSTs |
| `go/internal/web/stays/edit_posts_test.go` | create | golden parity and route tests |
| `go/internal/web/stays/testdata/edit_posts_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_stays_edit_posts.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_stays_edit_posts_test.go` | create | route registration test |
| `App/scripts/go_edit_posts_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_edit_posts_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1731-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1731-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1731-files/ANCHORS.txt`):
   - `grep -cF 'async def reservation_quick_edit(reservation_id: int, request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF 'async def reservation_remove_empty_slot(reservation_id: int, request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF 'async def reservation_archive(reservation_id: int, request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF 'async def reservation_unarchive(reservation_id: int, request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF 'async def reservation_delete_demo(reservation_id: int, request: Request):' App/app/routes/admin.py | tail -1`
   - `grep -cF '// CreateHandler is POST /reservations (admin.py reservation_create).' go/internal/web/stays/post.go | tail -1`
   - `grep -cF '// UpdateHandler is POST /reservations/{reservation_id} (admin.py reservation_update).' go/internal/web/staydetail/post.go | tail -1`
   - `ls go/internal/web/stays/edit_posts.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_edit_posts_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_stays_edit_posts.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1731-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_edit_posts_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Rows and audit entries equal Python's; an update of a stay in an active filing state is refused as Python refuses (state machine).
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1731 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1731-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1737.
- **Rollback:** Revert the PR.

## Owner steps

None.
