# 0502 report
Status: review

## Files changed
- App/app/static/app.js: claimNode(...) guard added to the nine init functions (steps 1 and 2). initTogglePanels claims addPanel for the ?new=1 action. initHousebookPdfExport and initCsvExport claim the dialog and their trigger loops.
- App/app/templates/base.html: app.js?v= set to 20261101-0502.
- App/tests/static_versions.json: regenerated with --write (app.js sha256 and v).
- App/tests/test_0502_page_inits_once_browser.py: new browser test.
- docs/tasks/0502-report.md: this report.

## Commands
- node --check App/app/static/app.js: no output (passes).
- Test (from App/, PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers): `.venv/bin/python -m pytest tests/test_0502_page_inits_once_browser.py tests/test_0501_bind_once_browser.py tests/test_dashboard_rows_browser.py tests/test_0399_open_buttons_click_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs`
  tail: `22 passed in 26.33s` (0 skipped).
- Lint (repo root): `python3 scripts/context_lint.py` tail ends `context lint: OK` (WARN lines are informational).
- Teeth check: the new test fails against origin/main app.js (the unfixed code), then passes with the fix.

## Page to selector table
| Page | Selectors claimed on it |
|---|---|
| /reservations?lang=cs | .action-panel, #add-stay-panel, [data-csv-export], #csv-export-dialog |
| /apartments?lang=cs | form[data-inline-timing] |
| /apartments/{first property}?lang=cs | [data-automation-mode], #fee-copy-apply |
| /housebook?lang=cs | #housebook-pdf-dialog, #csv-export-dialog |
Not covered by any page: data-birth-date, form[data-notification-dismiss], data-controller-same-toggle (no template renders it; it is only in app.js).

## Deviations
- The fee-copy button only renders when another property has a stay-fee rate. The test sets stay_fee_rate_czk on the second property in seed().
- Three selectors have no page (see above). They stay in the recorder list, so a listener on them would still be caught, but nothing here proves them.
- The brief asked for an open PR. Not done: the instruction was no push, so the owner or orchestrator opens it.
- Done: steps 1 to 4 all done.

## Questions
- Should data-birth-date (guest_form_admin) and form[data-notification-dismiss] (host alerts) get a page in the test? The four-page cap was reached. data-controller-same-toggle has no template at all; does that markup exist elsewhere?

## Owner steps left
None for this branch. Merge only via scripts/merge-pr-on-green.sh.
