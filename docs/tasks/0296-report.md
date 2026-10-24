# 0296 report: lint catalog and row cues

Status: blocked

## Files changed
- docs/design/catalog.json: step 1 (22 T3 classes appended; class_notes entry for ui-btn-open)
- scripts/design_lint.py: step 2 (T4 per button group; docstring line updated)
- App/tests/test_0252_touch_sweep_browser.py: step 3 (cue selector adds .ui-btn-open)
- App/app/templates/apartments.html: step 4 (sr-only actions header; row_open() cell per property-summary row)

## Commands
- `cd App && .venv/bin/python ../scripts/design_lint.py` -> `DESIGN App/app/templates/invoice_form.html: T4 more than one ui-btn-primary in one group` / `design lint: FAIL`
- `.venv/bin/python -m pytest tests/test_design_lint.py tests/test_0252_touch_sweep_browser.py tests/test_0285_rows_browser.py tests/test_host_list_layouts_browser.py tests/test_design_*.py -q --tb=short -rs` -> `2 failed, 142 passed in 113.97s`, 0 skipped
  - FAILED tests/test_design_lint.py::test_the_repository_passes_the_design_lint: invoice_form.html T4 (see Questions 1)
  - FAILED tests/test_design_lint.py::test_template_rules_catch_each_kind_of_drift: `assert any("T4" in f for f in _t('<a class="ui-btn ui-btn-primary"></a><a class="ui-btn ui-btn-primary"></a>'))` is False (see Questions 2)
- `python3 scripts/context_lint.py` -> `context lint: OK`

## Acceptance
- [ ] design lint OK: NO (invoice_form.html T4)
- [ ] listed tests pass: NO (2 failures above); test_0252 passes

## Deviations
- Done: steps 1 to 4. Left: none. Blocked on the two decisions below; no test was changed.

## Questions
1. invoice_form.html: the whole invoice is one `<form>` (lines 24-297). It holds the ARES "fill" primary (line 66, inside the buyer card) and the "Issue" primary (line 294). They are not exclusive `{% if %}` branches, so the brief's `multi_primary_ok` exemption does not apply. Options: (a) owner allows invoice_form.html via a `multi_primary_ok` catalog key; (b) line 66 becomes `ui-btn-secondary` (template change outside the brief); (c) T4 treats a `<form>` as not a group.
2. test_design_lint.py `test_template_rules_catch_each_kind_of_drift` expects two bare sibling primaries with no wrapper tag to be flagged. The brief's regex only sees primaries inside div/form/p/td/li, so it does not. Options: (a) add a fallback that counts a template's top-level primaries as one group; (b) change that fixture.

## Owner steps left
- None (decision needed on Questions 1 and 2).
