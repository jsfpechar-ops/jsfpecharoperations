# 0531 report

Status: blocked

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
