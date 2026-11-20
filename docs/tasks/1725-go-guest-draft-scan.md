# 1725: Go guest 6: draft autosave and document scan

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1724 | Base commit: current tip of the working branch | Branch: task/1725-go-guest-draft-scan
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1725 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1725 step'`.

## 1. Objective

Port `guest_form_draft` and `guest_document_scan` (document scanning upload, size and type limits).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `guest.py` 2784-3062; `guest_draft.py`.

**Routes in scope (method path, Python function):**

- POST /l/{token}/{reservation_id}/draft
- POST /l/{token}/{reservation_id}/scan

**Risk:** Guest pages are public and carry real guest data (passports, signatures). Rule 2 applies line by line; the owner's rule is that guest registration goes last.

**Parity method (same as briefs 1595 and 1580):** a golden script `App/scripts/go_draft_scan_golden.py` seeds a throwaway database with made-up rows, renders the real FastAPI app, and writes `testdata/*_golden.json`; the Go test replays the same seed and must match byte for byte (go-first exception 1). Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1725-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `34b32ff1c5ec3456b08815da7d6ccaa351b50a28cadf28b843fa1fc83c192150` | `App/scripts/go_draft_scan_golden.py` | create |
| `c5c9a467029c0e0db2fa87eaa946007221c4a4668b0b270e86c5c18763ec2a2d` | `App/tests/test_go_draft_scan_golden.py` | create |
| `3108594b5019775ef45edd0b5f039455187719a0a33d94ae674861733b127e72` | `go/cmd/ubyhost-web/register_web_guest_draft_scan.go` | create |
| `c5489aa16d8afdd1cc341a835c7bd6c208c97c8e30e2d5809bc7044260fa0f9a` | `go/cmd/ubyhost-web/register_web_guest_draft_scan_test.go` | create |
| `27531dfa5c15935e0fce0a2e78d46eee1d0ab88292af8214f41605be1a2dff71` | `go/internal/web/guest/draft_scan.go` | create |
| `293241d706fffd45df085b5676477c198f2edd606ab63afbc4430bf3337e238e` | `go/internal/web/guest/draft_scan_test.go` | create |
| `7c6cdc260b8a0337eeda018654f618d384520b125ae1d867e02b17942c69a88f` | `go/internal/web/guest/testdata/draft_scan_golden.json` | create |

Full manifest: `docs/tasks/1725-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1725-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/guest ./cmd/...` silent; `go test ./internal/web/guest -count=1` OK; `go test ./cmd/ubyhost-web/... -run TestGuestDraftScanRoutesRegistered` OK; executor step 2 must add FastAPI golden replay and wire `claim_generation` / mail gates from brief 1721 (sidecar pins `claim_generation` 0 until then).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/draft_scan.go` | create | draft and scan |
| `go/internal/web/guest/draft_scan_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/draft_scan_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_draft_scan.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_draft_scan_test.go` | create | route registration test |
| `App/scripts/go_draft_scan_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_draft_scan_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1725-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1725-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1725-files/ANCHORS.txt`):
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/draft")' App/app/routes/guest.py | tail -1`
   - `grep -cF 'async def guest_form_draft(token: str, reservation_id: int, request: Request):' App/app/routes/guest.py | tail -1`
   - `grep -cF '@router.post("/l/{token}/{reservation_id}/scan")' App/app/routes/guest.py | tail -1`
   - `grep -cF 'async def guest_document_scan(token: str, reservation_id: int, request: Request):' App/app/routes/guest.py | tail -1`
   - `ls go/internal/web/guest/draft_scan.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_draft_scan_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_guest_draft_scan.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1725-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1725-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1725 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_draft_scan_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Draft rows equal Python's; the scan endpoint refuses oversize and wrong types with Python's messages; nothing is stored when refused.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1725 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1725-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
