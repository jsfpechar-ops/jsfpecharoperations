# 0797 report (run 2)

Status: blocked

## Files changed
- `App/tests/test_design_shell_browser.py`: two collapse tests load `/payments?lang=en` (run 1). Done.
- `App/app/static/app2.css` (16 lines added, none removed):
  - after `body.v2 .month-control` (run 2 step a): port of host.css 502-505 and 555-564 as `body.v2` rules, plus `body.v2 .month-trigger{width:100%}` (needed for the trigger width test; not in the brief's list).
  - 0793 block: `#housebook-pdf-dialog .ui-form-actions` flex, equal `flex:1 1 0` buttons with `min-height:44px`, and `.ui-pair` 2-column grid.
- Root cause of the PDF dialog width mismatch: v2 pages load only app2.css (base.html:21), so host2.css:49 and :512 never apply. `.ui-form-actions` computed `display:block`, buttons `inline-block`.
- Not committed.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_design_shell_browser.py tests/test_host_filter_panels_browser.py tests/test_host_controls_browser.py -q -rfs --tb=line`
   Last 5 lines: `E   AssertionError: assert 'rgb(239, 239, 239)' == 'rgb(250, 235, 232)'` / `FAILED ...test_host_filter_panels_browser.py::test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech` / `1 failed, 19 passed in 78.67s`
   Controls test and both shell tests pass.
2. `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions" -q -rs --tb=short`
   Last 5 lines: `....` / `36 passed, 94 deselected in 59.24s`. 0 failed, 0 skipped.

## Deviations
- Added `.month-trigger{width:100%}` and `.ui-pair` grid, `min-height:44px` (outside the brief's list, needed by the named tests).
- Temporary probe test file created and deleted (no residue).

## Questions
1. Line 508 expects the selected month cell in `/invoices` month grid to be `rgb(250,235,232)` (host.css `#faebe8`). v2 has no `.month-choice.selected` rule, so it renders grey `rgb(239,239,239)`. The v2 token `--brand-soft` is `#f9e9e7`, not `#faebe8`. Options: (a) add `body.v2 .month-choice.selected{background:#faebe8;...}` (a hard-coded colour, which the brief forbids); (b) change the test to expect `--brand-soft` (`rgb(249, 233, 231)`); (c) drop that assertion for v2. Owner/orchestrator decides.

## Owner steps left
None.
