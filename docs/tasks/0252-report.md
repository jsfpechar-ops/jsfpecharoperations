# 0252 report

Status: blocked

## Files changed
- App/app/templates/_components.html (row_open macro)
- App/app/templates/{reservations,reservation_detail,apartments,submission_detail,entities,submissions,settings_archived,housebook,invoices,stay_fees,settings}.html
- App/app/static/host.css, host2.css, templates/base.html (keys 20261022-0252), App/tests/static_versions.json
- App/tests/test_property_navigation_browser.py (stale fixes, step 4)
- App/tests/test_0252_touch_sweep_browser.py (new, step 5)

## Commands
1. `tests/test_static_versions.py tests/test_0250_property_cards.py`: 6 passed, 0 skipped.
2. `tests/test_0252_touch_sweep_browser.py -rs`: 1 failed, 0 skipped. Problems (pytest truncated the list after 5 entries; the rest is not captured):
   - phone390 /, /apartments
   - ipad820 /, /apartments
   - ipad1024 /, /apartments
   - Kinds: noCue only. "/" = dashboard reservation rows (dashboard.html is out of scope, brief §5). "/apartments" = Karlin Loft and Vinohrady Studio, the `data-summary-row` clickable rows at apartments.html line 81 (no cue; not in the brief's step 2 table).
3. Not run (executor budget reached).
4. Not run (executor budget reached).

## Deviations
- Steps 1 and 2 are one commit, "0252 step 2" (first commit message amended before push).
- stay_fees.html: the cue also went into the second branch row-actions cell (line 134) of the same row.
- Line drift: the ui-chips rule was at host2.css line 385, not 383. Matched by text.
- Apartments summary row (line 81) and dashboard rows (`/`) not cued: see Commands 2.
- Done: steps 1 to 5 committed (step 5 test file included). Left: sweep problems (decision needed on apartments summary row cue), commands 3 and 4.

## Questions
- Should the apartments summary row (`data-summary-row`) get a cue? Dashboard rows are out of scope per brief §5; the test flags them, so the probe may need an exclusion.

## Owner steps left
- None until the sweep test passes.
