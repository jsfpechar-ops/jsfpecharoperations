# 1712: Go booking 3: guest cancel and invoice PDFs (replaces 1553)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1711, 1544 | Base commit: current tip of the working branch | Branch: task/1712-go-booking-cancel-pdfs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1712 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1712 step'`.

## 1. Objective

Register `booking_manage_cancel`, `booking_invoice_pdf`, `booking_correction_pdf` and `booking_manage_calendar`. 1553 is already marked replaced by 1712 (no edit here).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/routes/property_page.py` (the four functions listed below).

**Routes in scope (method path, Python function):**

- POST /p/{slug}/b/{booking_id}/{token}/cancel
- GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf
- GET /p/{slug}/b/{booking_id}/{token}/correction.pdf
- GET /p/{slug}/b/{booking_id}/{token}/calendar.ics

**Risk:** Refunds.

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_cancel_pdfs_golden.py` seeds HTTP cases and writes `go/internal/web/booking/testdata/cancel_pdfs_golden.json`; `cancel_pdfs_test.go` replays on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1). Full FastAPI byte replay grows with executor step 2 when `App/.venv` is available. Accepted differences belong in the report, never silently.

**Calendar route:** `GET .../calendar.ics` stays registered in `go/cmd/ubyhost-web/register_web_booking.go` (brief 1351) so `newMux` does not panic on a duplicate pattern. Logic lives in `StayCalendarHandler` in `handlers.go`; this brief does not edit those files.

**Invoice issue:** first-time `invoice.pdf` issue needs brief **1711** `stayinvoice` before parity matches Python `booking_invoice.ensure`.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1712-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `c1315255eb80064df72dfce63f8b8cf93cfaf53d39bee9bebe22bb42f7ba0b23` | `App/scripts/go_cancel_pdfs_golden.py` | create |
| `d8dbc0d40d006bc04cf43c1abee2108f4fd2158959736e4cbb873dc063f5e62a` | `App/tests/test_go_cancel_pdfs_golden.py` | create |
| `58bae6cc8e9ffc256ed51a850ccd67fb3135fb9d719b154c85389235cbe4c401` | `go/cmd/ubyhost-web/register_web_booking_cancel_pdfs.go` | create |
| `c4a593b832c2a7b973b3f91edad95b772106befb9fbbcd8562109d04f15e15b0` | `go/cmd/ubyhost-web/register_web_booking_cancel_pdfs_test.go` | create |
| `432c855cd2bbff036b6ac4135492eedce86c25468da5d9404bba4c7e3cd6d167` | `go/internal/web/booking/cancel_pdfs.go` | create |
| `e0f707463d216d9681d1ffc4ad8d31afd1069aa2528658e3d253aad725261889` | `go/internal/web/booking/cancel_pdfs_test.go` | create |
| `cf73b38d8f67871189a9970fbccf9893914e6a442181cfc600e3360afd357ab3` | `go/internal/web/booking/testdata/cancel_pdfs_golden.json` | create |

Full manifest: `docs/tasks/1712-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1712-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go test ./internal/web/booking/... -run 'CancelPDFs|GuestCancel'` OK; `go test ./cmd/ubyhost-web/... -run TestBookingCancelPDFsRoutesRegistered` OK; `pytest tests/test_go_cancel_pdfs_golden.py` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/cancel_pdfs.go` | create | routes |
| `go/internal/web/booking/cancel_pdfs_test.go` | create | golden parity and route tests |
| `go/internal/web/booking/testdata/cancel_pdfs_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_booking_cancel_pdfs.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_booking_cancel_pdfs_test.go` | create | route registration test |
| `App/scripts/go_cancel_pdfs_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_cancel_pdfs_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1712-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1712-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1712-files/ANCHORS.txt`):
   - `grep -cF 'def booking_manage_cancel(request: Request, slug: str, booking_id: int, token: str):' App/app/routes/property_page.py | tail -1`
   - `grep -cF 'def booking_invoice_pdf(request: Request, slug: str, booking_id: int, token: str):' App/app/routes/property_page.py | tail -1`
   - `grep -cF 'def cancel(booking_id: int, *, by_host: bool, now: Optional[datetime] = None)' App/app/booking_cancel.py | tail -1`
   - `grep -cF 'def ensure(booking_id: int) -> Optional[int]:' App/app/booking_invoice.py | tail -1`
   - `grep -cF 'func StayCalendarHandler(' go/internal/web/booking/handlers.go | tail -1`
   - `ls go/internal/web/booking/cancel_pdfs.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_cancel_pdfs_golden.py 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/cmd/ubyhost-web/register_web_booking_cancel_pdfs.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `find docs/tasks/1712-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1712-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1712 step 1`.
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
- `cd App && .venv/bin/python -m pytest tests/test_go_cancel_pdfs_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- A bad token returns the same 404 as Python; a cancel is idempotent and writes one refund request only.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1712 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1712-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1714.
- **Rollback:** Revert the PR.

## Owner steps

None.
