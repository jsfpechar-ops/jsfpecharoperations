# 0830D report: Stays list and stay detail (part D)

Status: blocked (leftover: design lint catalog for 3 new classes; not committed)

## Files
- `App/app/templates/reservations.html`: filter chips replaced by `partials/settings_pills.html` (upcoming, current, past, failed, archive). The `Filters` toggle button is kept, still a `.chip`, hidden by default.
- `App/app/templates/reservation_detail.html`: round back link replaced by `partials/settings_back_header.html` (back to `return_to`, title = guest or stay name). The head `h1.big` became `div.big` so the page has one h1.
- `App/app/static/app2.css`: only inside the `0830D` markers. Added: `.stays-desk` padding 16px; `.host-stay-detail .card` 1px border, radius 12, padding 16px 20px; `.stays-phone .card.stay` 1px border; hide the `How` chevron (`.stays-how .ui-how-chevron`); hide `[data-filter-summary]` fine print; `.stays-links` as a bordered list of 64 px index rows.
- `App/tests/test_0830_airbnb_pages_browser.py`: new function `test_0830D_stays_regressions` appended at the end (passes; 0 skipped). Uses `empty_host` from `tests/test_signed_in_chrome.py` via `__wrapped__` and `next()`. It checks one h1, no `chip`/`chips` classes on the empty list.
- Old tests updated for the new look: `tests/test_design_stays.py` (asserts `settings-pills`, not `chips stays-chips`); `tests/test_0285_rows_browser.py` (`aria-current="page"` on Upcoming & current).

## Test runs
- `-k partD` (`test_0830_airbnb_pages_browser.py`): before this part 12 failed; now 10 failed, 2 passed (the `partD-reservations` and `partD-stay-detail` cases at 1024 to 1440 partly pass now); last full run: 10 failed, 2 passed, 0 skipped.
- `test_0830D_stays_regressions`: 1 passed.
- Old tests (`test_design_stays`, `test_0285_rows_browser`, `test_0523_stays_list`, `test_0525_stay_detail`, `test_0766_phone_stays_browser`, `test_design_stay_detail`, `test_door_code_window`, `test_host_stay_detail_layout_browser`): 118 passed, 0 skipped.
- Not run: `design_lint.py`, screenshots (`UBYHOST_SHOTS_0830` not set), `test_host_filter_panels_browser.py` and other broad host tests that touch `[data-filter-toggle]`.

## Still red (partD)
- Reservations list: 12 px rule between the `Send all ready stays`, `Download house book`, `Add stay` and `Filters` controls and between `Police reports`, `Guest register`, `Export stays (CSV)` (0 to 8 px apart). A wrapped `.stays-head-actions` and a 12 px gap on `.stays-links` would fix most.
- Reservations list at 390: the card `T TOMAS NOVAK ...` text sits within 16 px of its edge.
- Stay detail: 12 px rule on `Send to UbyPort` vs `Copy guest form link` (0 px), `Edit count` vs `+ Add a guest` (8 px).
- Stay detail: fine print `Reporting deadline arrives in 1 day · Th...` (96 chars) outside a help body, at every width. Source is `small.police-deadline` in `reservation_detail.html` (around line 289) and `deadline_badge` in `_components.html`. Needs moving under a help `?` or dropping; not done.
- Stay detail: `.airbnb-back` now present; the stay detail card-border check passes at 390 after the CSS edit.

## Coordinator's extra must-fix list (Stays list, desktop)
1. Two chevrons on `How does this work?`: the CSS hides the second one (`.ui-how-chevron`). The help is still a big pill; moving it to a small `?` after the h1 is NOT done.
2. Tabs as settings pills: done (partial, 44 px, aria-current). Filters button is still a dashed `.chip` (not restyled).
3. Fine print under tabs (`All properties · Active`): hidden via `[data-filter-summary]`.
4. Empty list links: now bordered index rows (`.stays-links`). The empty-state block above them was not re-checked; no screenshot taken.

## Deviations
- Stay detail `h1.big` changed to `div.big`; the title is now the back header h1.

## Owner steps left
- None. Orchestrator commits.

## Leftovers
- Items above under "Still red" and the How-pill `?` move.


## Run 2 (leftovers 1 to 6, not committed)
Done:
1. `How does this work?` is now a small `?` (`help_tip`) after the h1 in `.stays-title-row`. The second chevron hack is removed. The pop-up body is styled for this page in the 0830D block.
2. Filters is a `btn ghost` head button after Add stay (`data-filter-toggle`, `hidden`, `aria-controls` kept). The dashed chip is gone.
3. `.stays-head-actions` gap 12 px and wraps. `.stays-links` rows are separate bordered 64 px rows, 12 px apart.
4. Phone stay cards: padding 16 px; long name/range text wraps (no clipping), so text stays 16 px from the edge at 320.
5. Stay detail: `.stay-head-cta` and `.stay-guests-actions` gap 12 px.
6. Deadline: `small.police-deadline` keeps the badge only; the long note sits in a `help_tip` in `span.police-deadline-row` next to it (template only, no Python change).
Other edits: `App/tests/test_0284_states_browser.py` selector is now `a.settings-pill:not([aria-current])`; `App/tests/test_host_geometry.py` line 106 now asserts the 12 px gap for `.stays-head-actions`; hover shade for `.stays-pills .settings-pill` added.

Test runs (App/, 0 skipped):
- `tests/test_0830_airbnb_pages_browser.py -k "partD or 0830D"`: 13 passed, 0 skipped (also 12 passed with `UBYHOST_SHOTS_0830=1`).
- Old: `test_design_stays`, `test_0285_rows_browser`, `test_0523_stays_list`, `test_0525_stay_detail`, `test_0766_phone_stays_browser`, `test_design_stay_detail`, `test_door_code_window`, `test_host_stay_detail_layout_browser`, `test_0284_states_browser`: 120 passed, 0 skipped.
- `test_host_geometry.py` and `test_0281_card_borders_browser.py`: 2 passed; `test_host_geometry.py::test_dashboard_actions_share_height_and_gap` fails (`assert 40 == 37`). It is the dashboard (part B), not this part; not touched here.
- Screenshots (390, 768, 1280): `docs/tasks/screenshots-0830/partD-reservations-390.png`, `docs/tasks/screenshots-0830/partD-stay-detail-390.png` (and the 768 and 1280 ones).
- `python3 scripts/design_lint.py`: FAIL overall (other parts too). From this part: `T3 class not in catalog` for `stays-title-row` (reservations.html), `stays-pills` (reservations.html), `police-deadline-row` (reservation_detail.html).

Deviations: none in the code, beyond the test assertion update above.

Left:
- Add the three new classes to the design lint catalog, or rename them to existing catalog classes (orchestrator or owner decision).
- The dashboard geometry test (part B) is red.
