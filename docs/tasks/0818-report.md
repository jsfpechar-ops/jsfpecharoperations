# 0818 report

Status: review. Nothing committed or pushed (per the owner's instruction for this run).

## Files changed
- App/app/static/app2.css: new block `0818 list filter v2` (collapsed panel, one card, wrapping fields, same-height Apply/Cancel, round 32 px help "?").
- App/app/templates/invoices.html: help summary markup; empty state now only "No invoices yet".
- App/app/templates/stay_fees.html: help summary markup; filter include moved under the head (was in the toolbar block).
- App/app/templates/submissions.html, housebook.html: help summary markup.
- App/app/templates/base.html (app2.css?v=20261102-0818), App/tests/static_versions.json (--write).
- App/app/host_i18n.py, host_vi_i18n.py: removed unused `invoices.empty` (3 lines).
- docs/tasks/0818-records-pages-filter-help-look.md: Status set to review.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 ... -k "invoices or housebook or submissions or stay_fees" ... -rs`: `48 passed, 104 deselected in 63.11s`, 0 skipped.
2. `pytest tests/test_page_help_0277.py ... tests/test_stay_fee_send_panel.py -q`: `32 passed, 1 warning in 6.34s`.

## Acceptance (section 7)
- Filter hidden until Filters clicked, one card, Apply/Cancel same height 40 px with 12 px gap: done in CSS, covered by command 1; not screenshot-checked.
- Help is a round "?" icon, no text, no chevron, on all four pages: done, aria-label kept.
- Commands 1-2: 0 failed, 0 skipped.

## Deviations
- No 1280 or 390 px screenshots taken (the executor screenshot rule); no tests failed, so no test edits were needed.

## Questions
- None.

## Owner steps left
- Look at /invoices and /stay-fees at 1280 and 390 px before merging.
