# 0835 report

Status: blocked
Done: steps 1 to 5. Left: steps 6 to 7.

## Files changed
- App/app/doc_ocr.py (step 1): policy gate removed from `available`, docstring fixed.
- App/app/routes/admin.py (step 2): `ocr_scan` payload no longer checks policy.
- App/app/host_i18n.py (step 3): EN and CS label and hint replaced.
- App/app/templates/guest/_ocr_scan.html (step 4, new).
- App/app/templates/guest/form.html (steps 4 and 5): include in first step card; old markup and old scan JS removed.

## Commands
- Step 1 to 2 tests (`test_doc_ocr.py test_property_form_save.py test_billing_order.py`), last lines:
  - `FAILED tests/test_doc_ocr.py::test_the_form_hides_the_button_until_max_and_installed`
  - `!!! stopping after 1 failures !!!`
  - `1 failed, 2 passed in 1.32s`
  - Cause: the test asserts the old `ocr-scan-toggle` markup. Step 7 rewrites it.
- Context lint, browser tests: not run (steps 6 and 7 not reached).

## Section 7 ticks
- Steps 1 to 5 committed as `0835 step k`: done.
- Steps 6 and 7: not done.
- Test acceptance: not met.

## Deviations
- Steps 1 and 2 were edited together, then committed as two commits.
- Step 5 first left a stray `{% endif %}` (TemplateSyntaxError). Fixed and amended into the `0835 step 5` commit before the test run.
- The include sits directly after the opening `<div class="g-card">` tag, before the `<h2>`, as the brief literally says "top of the first step card". Visual placement not checked.
- No screenshots taken (no browser run).

## Questions
- Step 7 changes the test that now fails. Confirm that is the intended update.

## Owner steps left
- Review the branch, then push and update PR #727 yourself. Nothing was pushed.
