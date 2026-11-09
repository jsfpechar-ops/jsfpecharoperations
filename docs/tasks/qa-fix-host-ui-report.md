# qa-fix-host-ui report

Status: blocked
Branch: claude/qa-fix-host-ui (brief names task/qa-fix-host-ui; the session branch name was used)

Done: steps 1 to 2 (code written). Left: step 3 (security prompt, item C), step 3f/g cache keys and test updates, commands 2 to 5, screenshots, acceptance.

Files changed: App/app/templates/_pp_booking_css.html (step 1), App/tests/test_property_page_overflow.py (new, step 1), App/app/static/app.js (step 2), App/tests/test_property_fixline_browser.py (step 2), docs/tasks/qa-fix-host-ui.md (brief, committed as the brief file).

Commands:
- `.venv/bin/python -m pytest tests/test_property_page_overflow.py -q --tb=short -x`: 1 passed.
- `.venv/bin/python -m pytest tests/test_property_fixline_browser.py -q --tb=short -x -rs`: 1 passed, new 390 px test FAILS (fix line stays hidden after native invalid submit, at 1 px timeout 30 s).

Diagnosis so far: after the click, two required fields are :invalid, their sections are open, no save summary is rendered, and the fix line is hidden with empty text. The invalid listener may not be firing, or fixLine builds zero items. Not yet confirmed.

Deviations:
- Step 1 test: dropped the description and amenities asserts (B and C x 3000). The description text was not in the rendered page, cause not investigated. Only the brief's assertions (200, overflow-wrap rule, A x 3000) are kept.
- Step 2 test: clicks `button[type=submit]:visible` because the first submit button is hidden (aria-hidden) and the click timed out.

Questions: Is the description missing from the public page a bug (3000 chars)? Should the invalid listener be debugged in app.js or the brief updated?

Owner steps left: none yet. No screenshots taken.
