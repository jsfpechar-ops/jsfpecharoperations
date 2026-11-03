# 0830E report: invoice detail, invoice form + stay picker, submission detail (part E)

Status: blocked (25-call cap reached; part E partly done, not committed)

## Files
- `App/app/templates/invoice_detail.html`: `v2` set; page title block emptied; settings back header (`partials/settings_back_header.html`) at top of body; body wrapped in `<div class="e-page">`; cancel help moved under `help_tip`; `help_tip` import added.
- `App/app/templates/invoice_form.html`, `invoice_stay_picker.html`: `v2` set; back header; body wrapped in `e-page`. No form, field, or POST change.
- `App/app/templates/submission_detail.html`: `v2` set; back header; body wrapped in `e-page`; outcome note `p` changed to `div` (same class, same text); receipt-missing sub-line moved under `help_tip` (the `data-receipt-missing` hook kept, only when the receipt is missing); technical help moved under `help_tip`. No filing logic, form or POST change.
- `App/app/static/app2.css`: only between `/* 0830E invoices+submission (start|end) */`. Ported look for stay command panel, metric value cards, report problems, technical fold, danger zone, invoice item and total grids, help dot, 44 px tap targets, 12 px gaps (scoped `body.v2 .e-page`).

## Test runs
- `tests/test_0830_airbnb_pages_browser.py -k partE`: 6 passed, 12 failed, 0 skipped.
  - Passing: invoice-detail 1024/1280/1440, submission-detail 1024/1280/1440.
  - Failing: invoice-detail 320/390/768, submission-detail 320/390/768, invoice-form all six widths.
  - Last findings seen (before the final two CSS/markup edits, not re-read): invoice-detail and submission-detail: "main content ends under the tab bar" after scrolling to the bottom (lowest about 1000 px, tab top 916 px). Same check fails on overview in part A's run, so it is probably a shell scroll issue. Not fixed, outside my files.
  - invoice-form 390/1280 earlier: buttons 0 to 9 px apart. Margin rule added after; result not re-read.
- Old tests (11 files, `test_0293_invoice_form`, `test_invoice_stay_pages`, `test_invoice_workspace`, `test_invoice_ux`, `test_report_detail_polish`, `test_report_detail_next_step`, `test_wp25_reported_bugs`, `test_design_invoices`, `test_design_reports`, `test_invoice_stay_browser`, `test_host_invoice_items_browser`): 88 passed, 3 failed.
  - `test_design_invoices.py::test_invoice_stay_picker_has_the_v2_form_shell`: asserts `class="ui-ph-back" href="/invoices"`; the page now renders `class="airbnb-back" href="/invoices"`. Assertion needs the new look (not done).
  - `test_host_invoice_items_browser.py::test_invoice_builder_heading_matches_narrow_form_lane`: waits for `.ui-ph`, which the form no longer renders. Assertion needs the new look (not done).
  - `test_host_invoice_items_browser.py::test_invoice_item_geometry_and_localized_screenshots`: page overflows by 46 px at 360 px (en). Not diagnosed. The `body.v2 .e-page .ui-btn{margin:6px}` rule added last is a suspect, unverified.

## Deviations
- The stay picker and invoice form lede (`meta` line) is dropped under the new header (brief §1.4).
- Not taken: screenshots (`UBYHOST_SHOTS_0830` not set); `design_lint.py` not run.

## Leftovers
- Done: steps 1 to 4 of the port (templates, CSS, wrappers, fine print).
- Left: the three old-test assertions above; the 360 px overflow; the tab-bar check on long pages (probably shell-level, check with the orchestrator); invoice-form 12 px neighbour checks re-run; screenshots at 390, 768, 1280.
- Owner steps left: none.

## Run 2 (leftovers)
Status: blocked (tool cap reached; one failure left, see below). Not committed.

- Tab-bar check (leftover 1): fixed on invoice detail and submission detail. Cause: the closed `details` (danger zone form, technical downloads) still laid out its content below the box, so the document ran 120 px past the tab bar. Added `body.v2 .e-page details:not([open]) > :not(summary){display:none}`; removed the extra `.e-page` bottom padding so these pages match the v2 pages (main padding only). partB overview, partB menu and partC properties pass the same check at 390 and 768.
- 360 px overflow (leftover 2): removed `body.v2 .e-page .ui-btn{margin:6px}`. Overflow went from 46 px to 34 px; still failing, not diagnosed further.
- Old assertions (leftover 3): `test_design_invoices` now asserts `class="airbnb-back" href="/invoices"`. `test_host_invoice_items_browser` heading check now measures `.airbnb-header` instead of `.ui-ph`. Behaviour checks kept.
- Invoice form neighbours (leftover 4): stay picker links are a flex row with a 12 px gap, 24 px above, separator dot dropped. invoice_form and invoice_stay_picker pass all six widths.
- Submission detail: header help sub-line moved under `help_tip('report-header-help', ...)`.

## Test runs (run 2)
- `test_0830_airbnb_pages_browser.py -k partE`: 12 passed, 6 failed, 0 skipped.
  - Failing: partE-submission-detail at 320/390/768/1024/1280/1440: "fine print of 81 characters outside a help body: UbyPort accepted this report..." (the outcome note in `submission_detail.html`, `outcome_notes` dict). Not yet moved; the audit flags it, so either move it under help or shorten it.
  - Passing: invoice-detail and invoice-form at all six widths.
- Old tests (11 files, same list as run 1): 90 passed, 1 failed, 0 skipped.
  - `test_host_invoice_items_browser.py::test_invoice_item_geometry_and_localized_screenshots`: 34 px overflow at 360 px (en), down from 46.
- Shell note: `App/app/host_i18n.py:1130` ("This workspace is pointed at the practice server") was flagged as 159 px fine print in run 1 on some pages. It is shell-level, not part E; not changed.

## Git note
I ran `git add -N` by mistake while listing changes; reverted it with `git reset` on the intent-to-add entries. Nothing staged; no commit.

## Owner steps left
- None. Orchestrator: fix the submission outcome-note fine print (or confirm it stays), then the 360 px overflow.
