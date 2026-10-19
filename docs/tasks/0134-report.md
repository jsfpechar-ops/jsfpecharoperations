# 0134 report

Status: blocked

Files changed: App/app/templates/reservations.html, App/app/static/host2.css, docs/design/catalog.json, App/tests/test_stays_empty_workspace.py, App/tests/test_host_filter_panels_browser.py, App/tests/test_design_stays.py (new).
Commits: b01a9cf (step 1), 5963102 (step 2), ebd7ff4 (step 3), e1a23b1 (step 4), 1dbd37b (step 5), 10c33f9 (step 5 fix: selector quoting).

Done: steps 1 to 5. Left: step 6 (browser tests fail), screenshots, report acceptance.

Commands:
- design_lint: OK. ruff E9,F63,F7,F82,F401,F841: All checks passed.
- test_design_stays + stays tests (step 5): 36 passed.
- Browser (step 6): 3 failed, 12 passed, 0 skipped. Failures:
  - test_host_filter_panels_browser.py:424 test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech: assert 40 >= 42 (triggerHeight).
  - test_host_list_page_layout_browser.py:155 test_list_pages_share_order_edges_and_rhythm: 'DOM order is not notices, title, tabs, toolbar, panel' for stays at 760, 1024, 1440; plus a height [40, 42] mismatch at 1024.
  - test_host_geometry.py:119 test_dashboard_actions_share_height_and_gap: assert 2 == 1 (heights {0, 40}). Not verified as pre-existing.
- Non-browser (grep /reservations, -x): 483 passed, 1 failed:
E   AssertionError: [

Screenshots: none. No test writes UBYHOST_SHOTS_DIR, and I had no calls left for a Playwright script.

Deviations: step 2 put ui_toolbar in the body block, but host_page renders the toolbar block before body. Likely cause of the DOM-order failure. Not fixed.

Questions: (1) Should the toolbar call move into a {% block toolbar %} in reservations.html? (2) Is the 42 px trigger minimum for the Filters button still wanted under v2 (40 px now)? (3) Is test_dashboard_actions_share_height_and_gap failing on the base commit too?

Owner steps left: none.

## 0134-cont-1 (executor, Haiku 5.5)

Done: steps 1 to 3. Left: steps 4 to 7 (step 4 blocked, see below).

- 6990e3a `0134-cont-1 step 1`: toolbar call moved into `{% block toolbar %}` in `reservations.html`. Also moved the `stay_property`, `stay_chip_items` and `stay_list_actions` sets to top level, because `stay_list_actions` reads `stay_property.label`. Jinja parse OK. Not yet checked in a browser.
- 51a434e `0134-cont-1 step 2`: `test_host_filter_panels_browser.py` line 424, `>= 42` changed to `>= 40`. No 42 px expectation was left in `test_host_list_page_layout_browser.py`.
- 2821bff `0134-cont-1 step 3`: `test_host_geometry.py` buttons filtered by `offsetParent !== null`.

Step 4 failed (`App/tests/test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state`, run twice-free, stopped):

```
assert not [('property-guests', 'cs', 360, False, 375, [], ...), ('property-guests', 'cs', 390, False, 405, [], ...)]
1 failed, 8 passed, 1 warning in 100.26s
```

Cause: `app/static/app.js` line 357 adds a `span.copy-label-confirmed` ("Zkopírováno") to copy buttons. `app/static/host.css` line 369 hides it with `visibility: hidden` only, so it still takes width. It ends at right 405 px on a 390 px page, and the page scrolls sideways. The fix needs `host.css` or `app.js`, which are not in the brief's file table. Stopped per brief section 8. Needs a CSS brief (for example taking the hidden label out of layout) before steps 5 to 7.

Steps 5 to 7 not run. No screenshots taken.

Owner steps left: none yet.
Questions: may the next brief change `host.css` (`.btn-icon .copy-label-confirmed`) and `app.js` for the copy label?

## 0134-cont-2 (executor report)

Status: blocked

- Step 1 (commit 832d37b, `0134-cont-2 step 1`): appended the icon-button label rule to `App/app/static/host2.css`. `design_lint` prints OK. `test_every_page_family_fits_every_width_language_and_rail_state` passes alone (1 passed, 97 s).
- Step 1 other test: `test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back` fails with `Locator.click: Timeout 30000ms exceeded ... waiting for locator("a.btn[href^=\"/apartments/1\"]").first`. It also fails with the CSS change reverted, so it predates this brief. Not in the brief's named list; not fixed.
- Step 5 run (7 files): 16 passed, 1 failed. `test_host_list_page_layout_browser.py:155`: `actions differ in height [40, 42]` (properties, en/cs, 1024 to 1440, expanded). It also fails at 0134-cont-1 HEAD without the new rule, so it predates this brief. Not in the brief's named list; not fixed. Step 5 is therefore not passing with 0 skipped.
- Step 1b (orchestrator addition, `tests/test_overhaul.py::test_reservations_paginate_and_preserve_filters`): fails on `assert "Page 2 of 2" in second.text`. Cause: `_ui.html` `ui_pagination` renders `{{ page }} / {{ pages }}` (line 117) and has no visible label slot. The old `reservations.html` used `t('stays.pagination.label')` ("Page %(page)s of %(pages)s") between Previous and Next. Restoring it needs the macro to take a visible label. That means editing `App/app/templates/_ui.html`, which the brief lists as do-not-touch, and it changes the shared macro used by host pages. Not committed. Owner or orchestrator decision needed: approve the `_ui.html` macro change, or choose another option.
- Steps 6 (screenshots) and 7 not run.

Owner steps left: none until the decisions above are made.

## 0134-cont-3 executor report

Status: blocked
Step 1 commit: 1775a85 (files: App/app/templates/_ui.html, App/app/templates/reservations.html). Tests: 32 passed, 1 warning in 2.68s.
Step 2 (screenshots): not done. The login helper returned 303 to /login?notice=form_expired, so no session cookie; the existing test_host_stay_actions_browser.py passes. Scratch script at the scratchpad, shoot_0134.py. Owner or orchestrator to decide.
Step 3 lint output:
```
design lint: OK
All checks passed!
```
Deviations: login workaround attempts in a scratchpad script only; nothing outside the brief was changed.
Owner steps left: none until step 2 is solved.
