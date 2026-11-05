# 0963 report (batch B05)

Status: blocked. Stopped during step 4, row 1 (new 0963 browser tests). The same assertion failed twice.

## Files changed (commits c7f36681, 5c5a2adf, b1fadcfe)
- App/app/templates/_property_editor.html
- App/app/host_i18n.py
- App/app/static/app2.css
- App/app/templates/base.html (app2.css key 20261105-0963a)
- App/tests/static_versions.json (2 entries, by test_static_versions.py --write)
- App/tests/test_0534_property_page_v2.py
- App/tests/test_host_property_controls_browser.py

Steps 1 to 3 applied with `git apply --check` first. All anchors matched.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b05 UBYHOST_DB=/tmp/ubyhost-b05/db-r1.sqlite .venv/bin/python -m pytest tests/test_host_property_controls_browser.py -k 0963 -q -rs --tb=short -x`
   - Run 1: `1 failed, 4 deselected in 13.03s`. Failure at test_host_property_controls_browser.py:627: `assert not page.locator("#archive-help").is_visible()` for ('en', 390). The tip is visible.
   - Run 2 (after one test fix, see Deviations): `1 failed, 4 deselected in 11.36s`. Same assertion, now at line 628, same label.
   - The second 0963 test was not reached (`-x`).
2. Not run (stopped).
3. Not run (stopped).
4. Not run (stopped).
5. Not run (stopped).

## Section 7 acceptance
Not verified. No screenshots were inspected. The archive and copy-chooser checks never ran.

## Deviations
- One test edit in run 2: `page.mouse.move(0, 0)` added before the blur line in test_0963_fee_and_police_headings_and_archive_button. It is in commit b1fadcfe (step 3, amended). It did not change the result.
- Cause not found. In app2.css, `body.v2 .help-tip-body` is display:none (line 1584). The tip is shown only by `.property-settings-form .help-tip:not([data-js]):hover` or `:focus-within` (line 2101) or `.is-open`. app.js line 2049 sets data-js. The cause is not confirmed; I did not investigate further (stop rule).
- Not run: `tests/test_reporting_help_0097.py` (known pre-existing failure on base).
- Local `App/.venv` symlink created (git-ignored). Tracked PNGs rewritten by tests were restored with git checkout.

## Questions
- Should the archive help tip be hidden on plain page load (the test's intent) or is the test wrong? Needs an owner decision on the expected tip behaviour, or a Haiku fix once the cause is found.

## Owner steps left
None.
