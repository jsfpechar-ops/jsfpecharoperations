# 0142 report

Status: blocked

## Files changed
- App/app/templates/stay_fees.html, App/app/templates/stay_fee_detail.html
- docs/design/catalog.json (both templates enforced; legacy lists 14 and 30)
- App/tests/test_stay_fee_detail.py, test_host_fee_navigation.py, test_host_wide_geometry_browser.py, test_host_button_contrast_browser.py, test_host_list_cards_browser.py, test_fee_setup_compatibility.py
- App/tests/test_design_fees.py (new)

## Commands
- Step 2 compile: compiled. Step 3 `scripts/design_lint.py`: design lint: OK.
- Step 4 (`test_design_fees.py`, `test_stay_fee*.py`, `test_design_lint.py`, with UBYHOST_BROWSER_EXECUTABLE set): 125 passed.
- Step 5 browser set: 43 passed, 1 failed. Failure: `test_host_wide_lanes_align` on invoices/en/1024 (`.panel.tight.scroll-x, .panel.empty` missing). Invoices is not in scope.

## Section 7
- [x] Fees list and detail shells, design lint, step 4 tests. Browser set not green, so not ticked.

## Deviations
Done: steps 1 to 5 (step 5 run, failing). Left: step 6 commit, and the invoices failure.
No SKIPPED lines. Log at /tmp/claude-0/0142-step5.log.

## Questions
Is `test_host_wide_lanes_align` on invoices failing on base (c340b7f) or caused by 0138 to 0141?

## Owner steps
None.
