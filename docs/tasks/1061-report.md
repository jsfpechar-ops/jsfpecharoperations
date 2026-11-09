# 1061 report

Status: blocked

Done: steps 1 to 9 (templates, app.js SVG helper, test_icons_marks_1061.py, cleaning toast assertion now expects svg, app.js cache key 20261109-1061a, static_versions.json rewritten).

Tests (from App/, UBYHOST_REQUIRE_BROWSER=1, known failures deselected):
- host row: 247 passed, 2 deselected. Earlier run had one ViewTransition flake in test_host_filter_panels_browser; it passes alone and in the rerun.
- onboarding/property/first: 369 passed.
- invoice/stay fee: 994 passed, 2 skipped (test_invoice_autofill.py:383, :452, need UBYHOST_SHOTS_DIR). Rerun pending.
- calendar: 138 passed. cleaning: 100 passed.
- door codes: 256 passed (rerun with UBYHOST_SHOTS_DIR, webkit deselected).
- login/auth: 85 passed. public/landing: 115 passed.
- design guardrails + icons + static: 58 passed, 1 deselected.
- layout lint: 4 passed.
- Door codes row first run: test_disclosure_design_and_geometry_on_every_changed_page[en-webkit] failed because the WebKit browser is not installed here (environment, not code). Deselected webkit in the rerun.

Not done: screenshots at 390/768/1280 EN and CS saved to docs/tasks/screenshots-1061/ and reviewed; CSS centring check for .readiness-mark and .auth-float em; PR is not opened (per owner).

Partial rerun log: /tmp/claude-0/-home-user-jsfpecharoperations/4c50b3c9-3d1a-524a-adfa-f3c1a6b89ecd/scratchpad/summary2.txt
