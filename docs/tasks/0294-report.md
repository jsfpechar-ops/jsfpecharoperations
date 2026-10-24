# 0294 report

Status: blocked

## Files changed

- App/app/templates/stay_fees.html: "Open" removed from the 2 name cells; the 2 "Set up" links are `ui-btn-open`; `row_open()` added first in the configured-period row's actions cell.
- App/app/templates/apartments.html: step 2 per coordinator decision; `row_open()` removed from the property-summary name cell, nothing added.
- App/app/templates/entities.html: Open removed from 2 name cells; Edit is `ui-btn-open`; `row_open()` added first in the archived table's actions cell.
- App/app/templates/reservation_detail.html: `cmd_primary` set before `stay-command-actions`; the 2 invoice links use `cta` when `cmd_primary`; "+ Add a guest" (line 182 only) is `ui-btn-open`.
- App/app/static/host2.css: 2 Open-after-name rules deleted; 3 max-width declarations set to `none`; 0294 block appended.
- App/app/templates/base.html: host2 key `?v=20261024-0294`.
- App/tests/static_versions.json: regenerated with `--write`.
- App/tests/test_0285_rows_browser.py: property-summary gap check dropped; entities gap check replaced by "every visible `.row-open`/`.ui-btn-open` is inside `td.row-actions`" plus the contact check.
- App/tests/test_0291_open_buttons.py: 2 tests appended (/entities, /stay-fees).

## Commands and results

Brief §6 command, run from App/:
- `tests/test_0291_open_buttons.py`, `test_0285_rows_browser.py`, `test_design_*.py`, `test_static_versions.py`: 1 failed, 148 passed.
- `tests/test_0252_touch_sweep_browser.py`, `test_host_list_layouts_browser.py`, `test_host_stay*.py`, `test_stay_fee*.py`: `FAILED tests/test_0252_touch_sweep_browser.py::test_every_host_page_on_phone_ipad_and_desktop`, 1 failed, 147 passed.
- Skips: none reported.
- `test_design_lint.py::test_the_repository_passes_the_design_lint` fails on the base commit 6303d14 too (pre-existing, from 0292/0293 classes). This change adds new findings: `ui-btn-open not in catalog` in entities.html, stay_fees.html (x2) and reservation_detail.html. `ui-btn-open` is already used by cleaning_properties.html and is also not in the catalog.

## §7 acceptance

- [x] No `row-open` inside a name cell on /stay-fees, /apartments, /entities (test_0291 covers /entities and /stay-fees).
- [x] Entities Edit is `ui-btn-open`; Add a guest is `ui-btn-open`; invoice link primary only without other CTA (code change; not browser-verified).
- [ ] Tests: 2 failures listed below.

## Deviations

Done: steps 1 to 6 and the static key. Step 7 (static versions) also done.
Stopped: the test run is failing and the executor's attempt cap (about 25 tool calls) is reached. Not investigated: the 0252 touch-sweep failure.

## Questions

1. `ui-btn-open` needs an entry in the design catalog (the design lint T3 rule). This brief does not name that file. Add it, or does the class need a different name?
2. Is test_0252 `test_every_host_page_on_phone_ipad_and_desktop` failing because of the new Open placement (touch target or overlap) or is it pre-existing? Not checked.

## Owner steps left

None.
