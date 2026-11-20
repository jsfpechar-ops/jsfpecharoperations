# 1732: Go stays 3: claim operations and 'filed by hand'

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1731, 1721 | Base commit: current tip of the working branch | Branch: task/1732-go-claim-filed-by-hand
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1732 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1732 step'`.

## 1. Objective

Port `reservation_reopen_guest`, `reservation_resend_claim`, `reservation_release_claim`, `reservation_filed_by_hand` and its undo.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 4305-4418; briefs 1109, 1135, 1155 state guards.

**Routes in scope (method path, Python function):**

- POST /reservations/{reservation_id}/reopen-guest
- POST /reservations/{reservation_id}/resend-claim
- POST /reservations/{reservation_id}/release-claim
- POST /reservations/{reservation_id}/filed-by-hand
- POST /reservations/{reservation_id}/filed-by-hand/undo

**Risk:** Filing state (rule 1).

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_claim_ops_golden.py` seeds a throwaway database, renders the real FastAPI app, and writes `go/internal/web/stays/testdata/claim_ops_golden.json`; `claim_ops_test.go` replays the seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Accepted differences belong in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1732-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `be8122afa62dec7017177f641c2b2f3a7a21c66a7307dad18f41518eb7ed8fd4` | `App/scripts/go_claim_ops_golden.py` | create |
| `71cbf68a4a80817bb6adca4ac65f234976db05989f8931aa9b0c94185bd67756` | `App/tests/test_go_claim_ops_golden.py` | create |
| `cecd31087ff863dddcf8a832fd23793f895093c5d71293cd188bf772db0885dc` | `go/cmd/ubyhost-web/register_web_stays_claim_ops.go` | create |
| `2f000ec717f79102d10ba7c01b8ef1b1c05013baf37696206aa5d77a13082222` | `go/cmd/ubyhost-web/register_web_stays_claim_ops_test.go` | create |
| `43f3ade8a0715d3e4539aac4de7781f121a8ad4dc1a516ad028e703ae60c1f1c` | `go/internal/web/stays/claim_ops.go` | create |
| `7bd970058703724a43a2329a37139665df5d678f27ed01fc439a3e0a61c2120e` | `go/internal/web/stays/claim_ops_test.go` | create |
| `01417c31b6c5ac2f3d6f25a9eb0e4b510b827a0b5fac717b155b1a957dcec6d5` | `go/internal/web/stays/testdata/claim_ops_golden.json` | create |

Full manifest: `docs/tasks/1732-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1732-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/stays/... ./cmd/ubyhost-web/register_web_stays_claim_ops.go` silent; `go test ./internal/web/stays/... -count=1 -run 'ClaimOps|ParseManual'` OK; `go test ./cmd/ubyhost-web/... -run TestClaimOpsRoutesRegistered` OK; `pytest tests/test_go_claim_ops_golden.py` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/claim_ops.go` | create | POSTs |
| `go/internal/web/stays/claim_ops_test.go` | create | golden parity and route tests |
| `go/internal/web/stays/testdata/claim_ops_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_stays_claim_ops.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_stays_claim_ops_test.go` | create | route registration test |
| `App/scripts/go_claim_ops_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_claim_ops_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1732-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1732-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1732-files/ANCHORS.txt`):
   - `grep -cF '@router.post("/reservations/{reservation_id}/reopen-guest")' App/app/routes/admin.py | tail -1`
   - `grep -cF 'def resend_to_verified_email(reservation, apartment)' App/app/claim.py | tail -1`
   - `grep -cF 'def mark_filed_by_hand(' App/app/reporting.py | tail -1`
   - `grep -cF 'func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler)' go/internal/web/stays/handlers.go | tail -1`
   - `ls go/internal/web/stays/claim_ops.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_claim_ops_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_stays_claim_ops.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1732-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1732-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1732 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_claim_ops_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Each transition is allowed or refused exactly as in `statemachine` golden tables; the undo restores the earlier `submit_state`.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1732 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1732-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1737.
- **Rollback:** Revert the PR.

## Owner steps

None.
