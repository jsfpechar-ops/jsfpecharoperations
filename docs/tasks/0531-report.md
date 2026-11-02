# 0531 report

Status: review

## Files changed
App/app/templates/apartment_form.html, App/app/templates/_property_overview.html, App/app/templates/_property_editor.html, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/static/host.css, App/app/templates/base.html (host.css?v= only), App/tests/static_versions.json, docs/design/catalog.json, App/tests/test_0531_property_page.py (new), docs/tasks/0531-report.md.

## Commands
- Step 3: `App/tests/test_static_versions.py --write` -> `wrote /tmp/wt0531/App/tests/static_versions.json (40 files)`
- Step 4: `.venv/bin/python -m pytest tests/test_0531_property_page.py -q --tb=short -x` -> `4 passed in 1.96s`
- Section 6 full command set: NOT RUN (budget reached).

## Acceptance (section 7)
Not ticked. Only the new test file was run.

## git diff --stat origin/main (before this report file)
 App/.venv                                      |  1 +
 App/app/host_i18n.py                           |  4 +++
 App/app/host_vi_i18n.py                        |  2 ++
 App/app/static/host.css                        |  6 ++++
 App/app/templates/_property_editor.html        |  6 ++--
 App/app/templates/_property_overview.html      |  1 -
 App/app/templates/apartment_form.html          |  1 +
 App/app/templates/base.html                    |  2 +-
 App/tests/static_versions.json                 |  4 +--
 App/tests/test_0531_property_page.py           | 50 ++++++++++++++++++++++++++
 docs/design/catalog.json                       |  4 +++
 docs/tasks/0530-properties-list-setup-chips.md | 46 ++++++++++++++++++++++++
 docs/tasks/0531-property-page-restyle.md       | 43 ++++++++++++++++++++++
 13 files changed, 163 insertions(+), 7 deletions(-)

## Deviations
- Done: steps 1 to 4. Left: step 5 (screenshots at 1280 and 390 px) and the section 6 commands (property hub, host UX, dead links, static versions, browser tests with -rs, design_lint, context_lint).
- `common.cancel` did not exist in any i18n file; added en "Cancel", cs "Zrušit", vi "Hủy" (step 2).
- `common.back` neighbour lines used as insert anchors for the new key; `property_page.guest_link.title` added after `property_nav.tabs_aria` in en, cs and vi.
- Step 3 mobile rule added as `@media (max-width: 640px){.host-workspace .property-savebar > *{flex:1}}`; the brief stated the behaviour but gave no rule.
- Test file imports the `host` and `two_properties` fixtures from tests/test_property_hub.py instead of copying them.
- Sticky save bar vs fields at 390 px: not checked (step 5 not run).

## Questions
None.

## Owner steps left
Fresh session to finish step 5 and section 6, then the orchestrator opens the PR.

## Run 2 (executor, step 5 and section 6)
Status: blocked. Stopped on the section 8 rule: an existing test that is not an assertion on the moved copy button, the "Back to list" label or the save-row order now fails.

### Section 6 test tails
- Core set (`test_0531_property_page`, `test_property_hub`, `test_host_ux_acceptance`, `test_no_dead_internal_links`, `test_static_versions`): `40 passed in 140.76s`
- Browser set, `-x -rs`: stopped at `test_0251_tablet_browser.py::test_overview_cards_and_tablet_menu_on_touch`
  `AssertionError: (1180, {'text': 'Digital door lock EnabledO', 'centre': False, 'corner': True, 'pill': False})`
- Browser set without `-x`: `1 failed, 8 passed` (only the 0251 test fails; 0199 passed earlier in the -x run).
- Baseline check: the same test passes on a clean `origin/main` copy (`1 passed`), so the regression comes from this branch. The branch changes in `_property_overview.html` and `_property_editor.html` are the likely cause; not diagnosed further.
- `python3 scripts/design_lint.py`: `FAIL`. `DESIGN App/app/templates/apartment_form.html: T3 class not in catalog: panel` and `... : mono`. These classes come from the step 1 guest-link markup; the catalog step (step 3 list) does not cover them.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only).

### Screenshots (step 5, `/apartments/<id>?lang=cs`, host fixture data)
- docs/tasks/screenshots-0531/overview-1280.png
- docs/tasks/screenshots-0531/overview-390.png
- docs/tasks/screenshots-0531/settings-1280.png
- docs/tasks/screenshots-0531/settings-390.png
Sticky save bar at 390 px, scrolled to the bottom: no input or select overlaps the bar (last field bottom 434 px, bar top 642 px of an 844 px viewport). The bar is 122 px tall at 390 px because the buttons wrap; the brief did not require this.

### Not done / open
- Failing tablet test (above) needs an owner or orchestrator decision before the PR. Per the brief, the fix is not made here.
- design_lint FAIL needs the two classes added to the catalog or the markup changed.
- Temporary screenshot test was created and deleted; it is not in the commit.
- `App/.venv` shows in `git diff --stat origin/main` as a 1-line change. It is not staged and must not be committed.

## Run 3 (executor, design lint and tablet test fix)
Status: review. Approved by the coordinator: test_0531 assertion changed to `class="property-guest-link"` (Fix 1 removed `panel`).

Changes: `panel` removed from the guest-link section and `mono` from its `<p>` (apartment_form.html); guest-link card gets background and border tokens and the `.ui-sub` rule gets a monospace font (host.css); host.css version key bumped to 20261101-0531a (base.html) and static_versions.json rewritten; `card.scrollIntoView({block: 'center'})` added as the first line of the CARD_JS map callback (test_0251); test_0531 line 13 assertion updated.

design_lint: `design lint: OK`

Tests, first set (`.venv/bin/python -m pytest tests/test_0251_tablet_browser.py tests/test_0531_property_page.py tests/test_static_versions.py -q --tb=short -rs`):
```
........                                                                 [100%]
8 passed in 7.18s
```

Tests, browser set (`ls tests/*browser*.py | xargs grep -l "/apartments/" | head -8 | xargs .venv/bin/python -m pytest -q --tb=short -rs`):
```
............                                                             [100%]
12 passed in 110.98s (0:01:50)
```
0 skipped in both runs. Screenshot PNGs rewritten by the run were restored with `git checkout`.
