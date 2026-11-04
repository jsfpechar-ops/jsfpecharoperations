# 0952 report

Status: blocked (budget cap reached; resume at "Next step")

## Commits (branch par-0952, not pushed, no PR)
- 2b64ecc8 steps 2-3: unsaved guard (document-level listener for form-attribute controls), #door-code/#smart-locks open #sec-lock and scroll, drop sec-lock-account CSS order
- bc805d4f step 1: one `#sec-lock` outside the property form; door-code controls carry form="property-settings-form"
- e55ffb48 step 4: tests/test_0952_lock_section.py (one section, no duplicate ids, with and without lock panel); old DOM and CSS order assertions in test_0534 updated
- 3c604bb9, 71262dbb: door-code switch status and discard follow form-attribute controls; app.js key 20261104-0952k (orchestrator asked for 0952j; 0952j was refused by the static versions tool once app.js changed again)
- 322afa88: earlier blocked report (superseded by this file)

## Tests
- test_host_unsaved_changes_browser.py: 15 passed, 0 skipped (after 71262dbb)
- test_0534, test_0952_lock_section, test_0530, test_property_hub, test_host_properties_navigation: pass (non-browser)
- Earlier browser run (before 3c604bb9/71262dbb): layout lint, 0251, 0541, 0199, host geometry, static versions all passed with 0 skipped; not rerun after the last two commits.
- Lint: F841 at tests/test_0541_property_page_phone_browser.py:168 (`spec`), a line this change does not touch; not yet checked against the base commit.

## Not done
- Browser test for editing a door-code control outside the form and asserting the dirty/unsaved state: not written (needs a lock-account fixture).
- Browser anchor test for #door-code / #smart-locks (step 2 asserts): not written.
- Screenshots at 390/768/1280 with the lock section open, and per-width notes: not taken.
- Design-system checklist, status line, decision line: not done (decision for orchestrator: `[ui] 0952 lock section is one accordion outside the property form; door-code controls use form="property-settings-form"`).

## Deviations
- Sub-block small headings not added; existing headings kept.
- app.js cache key is 20261104-0952k, not 0952j.

## Next step
1. Rerun `tests/test_layout_lint_browser.py tests/test_0251_tablet_browser.py tests/test_0541_property_page_phone_browser.py tests/test_0199_phone_geometry_browser.py tests/test_host_geometry.py` from App/ with 0 skipped.
2. Add the guard browser test and the anchor browser test, then take the three screenshots and write per-width notes.
3. Check F841 against the base commit.
