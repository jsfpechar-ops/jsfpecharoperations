# 0530 report: Properties list with setup chips

Status: review

## Done
- Steps 1-4 (committed earlier): chips data, one table, copy, CSS and catalog.
- Step 5b: `test_host_ux_acceptance.py` no longer looks for `property-summaries`. Two blocks were replaced: the Properties listing check and the guest-link/fee check (now asserts the section is absent). `base.html` and `static_versions.json` committed with it.
- Step 5c: police-ok case added to `test_0530_properties_chips.py` (complete UbyPort fields, police chip `data-state="ok"`).
- Step 5d (section 8 updates only): `test_0285_rows_browser.py` drops the `table.property-summary-table` selector; `test_host_list_page_layout_browser.py` drops the `property-summary` entry; `test_properties_inline_controls_browser.py` deleted (it only covered the removed section).
- Step 6: screenshots of `/apartments?lang=cs`: `docs/tasks/screenshots-0530/apartments-cs-1280.png`, `docs/tasks/screenshots-0530/apartments-cs-390.png` (full page). Not re-viewed after capture.

## Test tails (from App/)
Set 1 (`test_0530_properties_chips`, `test_properties_table_chips`, `test_property_hub`, `test_host_ux_acceptance`, `test_no_dead_internal_links`, `test_static_versions`):
```
54 passed in 121.99s (0:02:01)
```
Set 2 (browser set, `-rs`):
```
40 passed in 156.71s (0:02:36)
```
Design lint (repo root): `design lint: OK`
Context lint (repo root): `context lint: OK` (WARN lines only: names of open briefs, plus "8 commit(s) touched App/ after the last status.md update").

## Diff stat (origin/main, before this report)
```
 App/app/host_i18n.py                               |  46 +-
 App/app/host_vi_i18n.py                            |  21 +-
 App/app/routes/admin.py                            |  45 ++
 App/app/static/host2.css                           |   2 +
 App/app/templates/apartments.html                  |  99 +---
 App/app/templates/base.html                        |   2 +-
 App/tests/static_versions.json                     |   4 +-
 App/tests/test_0285_rows_browser.py                |   2 +-
 App/tests/test_0530_properties_chips.py            | 124 +++++
 App/tests/test_host_list_page_layout_browser.py    |   1 -
 App/tests/test_host_ux_acceptance.py               |  14 +-
 .../test_properties_inline_controls_browser.py     | 532 ---------------------
 App/tests/test_properties_table_chips.py           |   2 +-
 docs/design/catalog.json                           |   6 +-
 docs/tasks/0530-properties-list-setup-chips.md     |  46 ++
 docs/tasks/0531-property-page-restyle.md           |  43 ++
 docs/tasks/screenshots-0530/apartments-cs-1280.png | Bin 0 -> 116650 bytes
 docs/tasks/screenshots-0530/apartments-cs-390.png  | Bin 0 -> 91114 bytes
 18 files changed, 310 insertions(+), 679 deletions(-)
```

## Deviations
- Section 8 edits and one deleted test file, listed above. No other existing test changed.
- Kept keys `apartments.table.entity` and `apartments.table.calendars`: still used, correct.
- Commit `61b2334` message was later reworded; its content is the deletion of `test_properties_inline_controls_browser.py` plus the rows-test selector change.
- Orchestrator follow-up: red chips use ui-badge-action; fee without a rate is grey (optional fee)

## Questions
None.

## Owner steps left
Review and merge through `scripts/merge-pr-on-green.sh`. No deploy step.
