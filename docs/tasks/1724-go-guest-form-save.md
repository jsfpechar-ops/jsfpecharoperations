# 1724: Go guest 5: guest form save (POST /save)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1723, validation package, 1171 skip rule, encryption `secure` | Base commit: current tip of the working branch | Branch: task/1724-go-guest-form-save
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1724 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1724 step'`.

## 1. Objective

Port `guest_form_save` (about 420 lines): validation, document and signature encryption, photo handling, duplicate detection, `submit_state` transitions and the audit trail. This is the filing-critical write path; split in two briefs if the exact-diff pass exceeds the budget.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `guest.py` 2362-2784; `App/app/validation.py`, `passport_photos.py`, `guest_draft.py`.

**Routes in scope (method path, Python function):**

- POST /l/{token}/{reservation_id}/save (guest_form_save)

**Risk:** Guest pages are public and carry real guest data (passports, signatures). Rule 2 applies line by line; the owner's rule is that guest registration goes last. Filing correctness: UbyPort data is built from these rows.

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_form_save_golden.py` seeds a throwaway database, renders the real FastAPI app, and writes `go/internal/web/guest/testdata/form_save_golden.json`; `form_save_test.go` replays the seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Accepted differences belong in the report, never silently.

Keep the conditions of the AI review of K-F03/K-F07 ([go-sqlite-final](../plans/go-sqlite-final.md) section 7), in particular: never cancel a filed stay, send once, skip while `ubyport_auth_failed`.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1724-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `69ac257c0258f593afa42e6e6017a789d6c0f8a1e0ca2ca65200cce862f89833` | `App/scripts/go_form_save_golden.py` | create |
| `35045473a3b56a342fa060b2b514d0c4ec2e63d942c2fb4a2c51fb3c48403220` | `App/tests/test_go_form_save_golden.py` | create |
| `648bb0e4dc24838f1794fa3d5082aa5160f9cacac3555087868444bd6e00e829` | `go/cmd/ubyhost-web/register_web_guest_form_save.go` | create |
| `20ab5edd56316ba46d40f89f87a5e112f659f3395922ce88a27c7132b12dc382` | `go/cmd/ubyhost-web/register_web_guest_form_save_test.go` | create |
| `65243550b108e01288c4eb201af53d583d7f1e3342f8abeec9ef72374378b16a` | `go/internal/web/guest/form_save.go` | create |
| `484f075a9b3d8b0c351a30d199628399c4d8d8cb2449ce872514601570a1c99b` | `go/internal/web/guest/form_save_test.go` | create |
| `1513bccfa52a7651b77c3a516ccac5e3aaee7930f2ba3e3bdd28a14f75f0a0d0` | `go/internal/web/guest/testdata/form_save_golden.json` | create |

Full manifest: `docs/tasks/1724-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1724-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go test ./internal/web/guest/... -count=1 -run 'FormSave|GuestFormSave'` OK; `pytest tests/test_go_form_save_golden.py` OK when `App/.venv` exists. Full FastAPI golden replay and DB parity need briefs **1720–1723** portal hooks (sidecar stubs compile; executor tightens parity).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/form_save.go` | create | save handler |
| `go/internal/web/guest/form_save_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/form_save_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_form_save.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_form_save_test.go` | create | route registration test |
| `App/scripts/go_form_save_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_form_save_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1724-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1724-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1724-files/ANCHORS.txt`):
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/save")' App/app/routes/guest.py | tail -1`
   - `grep -cF 'async def guest_form_save(token: str, reservation_id: int, request: Request):' App/app/routes/guest.py | tail -1`
   - `grep -cF 'func ValidateGuestForm(g GuestRow, stayFrom, stayTo *time.Time, today time.Time, raw map[string]string) []Issue' go/internal/validation/guest_form.go | tail -1`
   - `grep -cF 'func Expected(override, declared, reduced *int64) *int64' go/internal/headcount/headcount.go | tail -1`
   - `ls go/internal/web/guest/form_save.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_form_save_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_guest_form_save.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1724-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1724-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1724 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_form_save_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- For 15 golden submissions (valid, every validation error, minor, foreigner, repeat save) the guest row, encrypted columns' plaintext after decryption in the test, `audit_log` and reservation `submit_state` equal Python's.
- Passport photo path writes to the `/data` volume (1640/1641) and the retention line already exists.
- A save on a stay already filed is refused exactly as Python refuses.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1724 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1724-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
