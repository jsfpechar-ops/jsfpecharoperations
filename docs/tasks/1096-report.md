# 1096 report

Status: review

Files: App/app/static/app.js (one line), App/app/templates/base.html (key 1096a), App/tests/static_versions.json, App/tests/test_host_police_letter_guard_browser.py (new test), App/tests/test_host_police_letter_browser.py (line 273 now expects ['beforeunload'], orchestrator-approved), docs/tasks/screenshots-1096/.

Red first: new test failed with `Page.wait_for_function: Timeout 30000ms exceeded`.

Commands: section 6.1 8 browser files, 0 skipped; only failure left is guest-new Cancel 43<44 (local-only, CI green on main, also fails without the fix). Letter browser file 12 passed. Layout lint 4 passed. Static versions + heartbeats 16 passed. context_lint OK.

Step 3 (operator_error test) dropped: no existing way to post the refusal; covered by 0833 and unsaved-changes suites.

Screenshots: 390: Save row at the bottom of the viewport, first unticked box visible below it, no sideways scroll, buttons 44 px; 768: same, nothing covered; 1280: Save row floats over the form, no field hidden, no sideways scroll. The lint pages for properties show no Save row on the clean page.

Wanted side effects: Read the letter again asks the discard warning; in-app links ask before leaving.
