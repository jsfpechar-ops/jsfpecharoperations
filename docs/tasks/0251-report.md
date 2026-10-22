# 0251 report

Status: blocked

## Files changed
- App/app/static/host2.css (step 1): tablet rail rules limited to `:not(.sidebar-expanded)`; overlay rule added.
- App/app/static/app.js (step 2): `tabletRail`, `setExpanded`, `syncRailButton`, Esc / outside-tap / range-change handling.
- App/app/templates/base.html (step 2): `host2.css?v=20261022-0251`, `app.js?v=20261022-0251`.
- App/tests/static_versions.json (step 2): regenerated with `--write` (34 files).
- App/app/routes/admin_accounts.py (step 3): signed-in host on a spent or own link gets 303 to `/`.
- App/tests/test_0251_back_after_login.py (step 3): new, 2 tests.

## Commands
- `.venv/bin/python -m pytest tests/test_0251_back_after_login.py tests/test_login_link_environments.py tests/test_static_versions.py -q --tb=short -x` (From App/, browser env set.)
  Last line: `8 passed, 1 warning in 1.52s`. 0 skipped.
- Not run: §6 commands 2 and 3 (browser tests), step 4 not started.

## Done / Left
Done: steps 1 to 3. Left: step 4 (`App/tests/test_0251_tablet_browser.py`), §6 commands 2 and 3, §7 browser acceptance, screenshots.

## Deviations
Step 4 stopped before writing the file. The brief's card assumptions do not match `App/app/templates/_property_overview.html`:
- Guest links card (line 31) is `div.host-property-card.host-property-card-static`, not a link. Only its inner `a.host-property-card-link` navigates. Its Open pill (line 34) is a span in the div, not in an `a`.
- So the "(left+8, top+8) resolves inside an a" check and the "tap at (left+8, top+8) opens guests" step would fail on the markup as it is.

## Questions
1. For the guest card, should the test target `a.host-property-card-link` (test-only change), or should the template be changed so the whole card is a link?
2. Confirm the stop; then step 4 can continue.

## Owner steps left
None yet.
Untracked `App/tests/test_zz_sweep.py` was already in the tree before this run; not touched or committed.
