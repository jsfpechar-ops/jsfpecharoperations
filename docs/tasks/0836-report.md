# 0836 report

Status: blocked

## Files changed (uncommitted, per orchestrator instruction)
- App/app/routes/invoices.py: `_form_context` prefills the lead guest into blank buyer slots on first open only (`fresh`), sets `guest_prefilled`.
- App/app/templates/invoice_form.html: one `hint` status line above `.invoice-buyer-fields`.
- App/app/host_i18n.py (EN, CS) and App/app/host_vi_i18n.py (VI): `invoice.fill_guest.prefilled`.
- App/tests/test_invoice_autofill.py: two tests (prefill on first open; no note without guest).
- docs/tasks/screenshots-0836/: invoice-fill-after-390.png (and before-390/360/1280 from the run).

Not touched: ARES code, invoice_issue, numbering, PDF, VAT.

## Commands (last lines)
1. `tests/test_invoice_autofill.py`: 10 passed, 1 skipped (screenshot test; needs UBYHOST_SHOTS_DIR, see 5).
2. `tests/test_invoice_*.py tests/test_stay_fee*.py` with UBYHOST_SHOTS_DIR set: 240 passed, 0 skipped.
3. Host row: 34 passed, 1 failed before `-x` stop. Full run without `-x` was still running at report time (65%). Result pending.
4. Copy row: stopped at 1 failed, 4 passed (`-x`). Full run without `-x` pending.
5. `-k screenshots`: 1 passed.

## Failures (pre-existing, not from this change)
- `tests/test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry` (waits for "Copy guest link" option, 30 s timeout).
- `tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects` (`no such table: apartment`).
Both fail twice here and also fail on a clean checkout of base commit b243ed8 (worktree, removed afterwards). So they are not caused by 0836.

## Section 7
- [x] First open with a complete guest shows street and city plus the note; no guest, no note (tests).
- [x] No automatic ARES call (no change near `register_lookup`).
- [ ] Commands 1-5 pass with 0 skipped: 3 and 4 not complete (see above).
- [x] One 390 px screenshot in docs/tasks/screenshots-0836/.

## Deviations
- No commits made (the executor brief asked for per-step commits; the orchestrator instruction said not to commit). No git add.
- Done: steps 1 to 5 (code, template, i18n, tests, screenshots). Left: confirm command 3 and 4 results without `-x`, and the two failures above.
- Tap count after change: not measured (no tap script in this brief's scope).

## Questions
- Are the two failing tests known to the owner on base b243ed8? They block a green host/copy row.
- Tracked screenshot files under docs/tasks/screenshots-0387 and screenshots-0402 show as modified in `git status`. Probably test-run side effects; not reverted, not committed by me.

## Owner steps left
- Decide on the two pre-existing failures before merge.
- Commit the listed files and the report.
