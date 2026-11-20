# 1711: Go booking 2: stay-invoice engine (needed by 1712)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1544, 1220 | Base commit: current tip of the working branch | Branch: task/1711-go-stay-invoice-engine
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1711 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1711 step'`.

## 1. Objective

Port `booking_invoice.ensure` plus the storno and partial credit note helpers the guest cancel flow needs (`booking_cancel.py` / `invoices.correct_partial`) as a library with no route. Brief 1712 wires the PDF routes.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `App/app/booking_invoice.py`, `App/app/invoices.py` (`correct_partial`, `cancel`), `docs/plans/stay-only-invoices.md`.

**Risk:** Money and legal documents.

**Parity method (same as briefs 1595 and 1580):** `App/scripts/go_stay_invoice_golden.py` writes `go/internal/booking/testdata/stay_invoice_golden.json` from `booking_invoice._form` (step 2 may extend it to DB-backed cases when `App/.venv` exists). `site_booking_test.go` and `stayinvoice_test.go` replay the form table; integrate tests with PostgreSQL in the report when `UBYHOST_TEST_DATABASE_URL` is set. Accepted differences are listed in the report, never silently.

**All implementation code is pre-written.** Sidecars: `docs/tasks/1711-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `e5099f589b6ab95080b6bac36ffe23dbcf3215f1cf443b9573bfacb47c14c339` | `App/scripts/go_stay_invoice_golden.py` | create |
| `500e119586df513af02bf6bb9257e625268ec0de5b12a42be4ddee4a74f42377` | `App/tests/test_go_stay_invoice_golden.py` | create |
| `88349fc66fbb1c1f589f5e7cc5eb12836397d3272d12fe35e5c27d8540b111c1` | `go/internal/web/invoices/site_booking.go` | create |
| `dfcd8ab982080fe07c367ae45d56d1ecd1d5761580f610a7ba14d3b3e9af71b0` | `go/internal/web/invoices/site_booking_test.go` | create |
| `1ec70d36923e275786d2f3f954f60dd0a91b8e8715c93bad1ed2d2637891b8df` | `go/internal/booking/stayinvoice.go` | create |
| `638eb79ad9cca69c470321bb913072b5bd3378b10873fc184cb44537f444c86a` | `go/internal/booking/stayinvoice_test.go` | create |
| `38a4a9322714d5f6707bbc175014c9cea0f52599e13414a4469b26934e19aea1` | `go/internal/booking/testdata/stay_invoice_golden.json` | create |

Full manifest: `docs/tasks/1711-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1711-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go vet ./internal/web/invoices/... ./internal/booking/...` silent; `go test ./internal/booking/... ./internal/web/invoices/... -count=1 -run 'BookingIssueForm|TestForm'` OK; `python3 scripts/go_stay_invoice_golden.py --check` OK.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/site_booking.go` | create | ensure, storno, partial correction |
| `go/internal/web/invoices/site_booking_test.go` | create | form golden |
| `go/internal/booking/stayinvoice.go` | create | public facade for 1712 |
| `go/internal/booking/stayinvoice_test.go` | create | facade tests |
| `go/internal/booking/testdata/stay_invoice_golden.json` | create | golden written by the Python script |
| `App/scripts/go_stay_invoice_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_stay_invoice_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1711-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1711-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each `grep -cF` / `ls` anchor prints `1` (see `docs/tasks/1711-files/ANCHORS.txt`); `find docs/tasks/1711-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `7`.
   - `grep -cF 'def ensure(booking_id: int) -> Optional[int]:' App/app/booking_invoice.py | tail -1`
   - `grep -cF 'def booking_invoice_pdf(request: Request, slug: str, booking_id: int, token: str):' App/app/routes/property_page.py | tail -1`
   - `grep -cF 'def correct_partial(invoice_id: int, refund_czk: int, reason: str, actor_user_id: Optional[int], *, today: date) -> int:' App/app/invoices.py | tail -1`
   - `grep -cF 'func buildDraft(e entity, form url.Values, today time.Time, st *stay) draft {' go/internal/web/invoices/draft.go | tail -1`
   - `ls go/internal/booking/stayinvoice.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls go/internal/web/invoices/site_booking.go 2>&1 | grep -cF 'No such file' | tail -1`
   - `ls App/scripts/go_stay_invoice_golden.py 2>&1 | grep -cF 'No such file' | tail -1`

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1711-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 7 lines ending `: OK`. Commit `1711 step 1`.
2. Run `App/scripts/go_stay_invoice_golden.py`; if it changes the JSON, commit the golden. Commit `1711 step 2`.
3. `gofmt -l` on the copied Go paths prints nothing. Commit `1711 step 3` when needed.
4. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/booking/... ./internal/web/invoices/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/booking/... ./internal/web/invoices/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_stay_invoice_golden.py -q --tb=short -x 2>&1 | tail -30` passes (or `python3 scripts/go_stay_invoice_golden.py --check` when no venv)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: not applicable (library); rule 10 skipped.

## 7. Acceptance

- `BookingIssueForm` matches Python `booking_invoice._form` for all 8 golden cases (non-payer defaults, cleaning note, cs/en).
- `EnsureSiteBooking` issues through `go/internal/pdf` when run against PostgreSQL (report command output).
- Storno and partial correction helpers refuse the same cases as Python (`not_cancellable`, `bad_amount`).
- `git log --oneline --grep='^1711 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1711-report.md`: commits, command outputs (last 30 lines), accepted differences, what was left undone.

## Rollout wave and rollback

- **Rollout:** No rollout (library).
- **Rollback:** Revert the PR.

## Owner steps

None.