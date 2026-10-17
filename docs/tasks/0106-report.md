# 0106 report: Cleaning page polish

Status: review. Branch `task/0106-cleaning-page-polish` cut from `feature/host-design0123-20261016` at `34b7933`. Committed locally, not pushed.

## Result in one line

CSS and cache-bust changes are in. The cleaning browser file has 19 passed and 2 failed, 0 skipped. Two failures come from a conflict between the brief's pill design and an existing visible-label guard, so I did not weaken the guard. Screenshots and the full suite were not run (budget).

## Files changed (`git diff --stat origin/feature/host-design0123-20261016`)

```
App/app/static/cleaning.css                | 97 ++++++++++++++----------------
App/app/static/dashboard-calendar.css      | 93 ++++++----------------------
App/app/templates/_dashboard_calendar.html |  2 +-
App/app/templates/cleaning.html            |  2 +-
App/app/templates/cleaning_edit.html       |  2 +-
App/app/templates/cleaning_properties.html |  2 +-
App/app/templates/cleaning_settings.html   |  2 +-
App/app/templates/cleaning_shared.html     |  2 +-
App/app/templates/cleaning_shares.html     |  2 +-
App/tests/test_cleaning_browser.py         |  9 +--
10 files changed, 75 insertions(+), 138 deletions(-)
```

No JS, Python, i18n or markup changes. `?v=` suffix `-0106` added to the seven stylesheet links (six cleaning templates plus `_dashboard_calendar.html`).

## Commands run

1. `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -q -rfs --tb=short` (from `App/`). Last line:
   `2 failed, 19 passed, 1 warning in 34.73s`
   Both failures: `test_fractional_checkout_and_same_day_cleaning_geometry[1280-en]` and `[1280-cs]`, at `test_cleaning_browser.py:198`.
2. `... pytest tests -q -rfs --tb=no -k "cleaning or dashboard_calendar or host_geometry or wide_geometry"` (from `App/`). Last line:
   `3 failed, 108 passed, 3567 deselected, 1 warning in 239.43s`
   The 2 failures above, plus `test_dashboard_calendar_browser.py::test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place`.
3. Same dashboard test with the base (HEAD) CSS temporarily restored: `1 failed, 1 warning in 34.13s`. It fails without my change too (it waits for a dashboard row). Pre-existing, not a CSS regression. My CSS was regenerated afterwards and the cleaning run was repeated (state as in command 1).
4. Full suite (`UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 ... pytest tests -q`): NOT RUN.
5. `python3 scripts/context_lint.py`: `context lint: OK` before this report existed. Rerun after writing this file, output in the final message.

Environment: created `App/.venv` (git-ignored, not committed). Installed `requirements.txt`, `requirements-dev.txt` and `playwright==1.63.0` (the version CI installs, not a new project dependency). `/opt/pw-browsers/chromium` is a directory, so the binary `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` was used via `UBYHOST_BROWSER_EXECUTABLE`.

## Brief section 7 (honest tick state)

- [ ] Month pills 22px, amber tint, 3px left edge. CSS in place (`--event-height`). Not verified visually: no screenshots.
- [ ] "+N" chips small and quiet, `aria-label`/`title` kept. CSS in place. Not verified visually.
- [ ] List cards one row at 1280px, about 60px. CSS in place. Not measured.
- [ ] Header, period form slim, one coral button, skip link works by keyboard. CSS in place. Skip link is visually hidden until focus, not keyboard-tested.
- [ ] No horizontal overflow at 360/390/1024/1280, 44px touch at ≤760. Tests asserting 44px touch targets pass at 360 and 390. No separate overflow measurement.
- [ ] Dashboard calendar and Gantt render correctly. Dashboard subset: all pass except the pre-existing failure above. No screenshots.
- [ ] Browser and geometry tests 0 skipped. Met for the cleaning file and the subset (no skips). Two failures remain (below).
- [x] `context_lint.py` (see command 5; rerun output appended in the final message).

Screenshots (`docs/tasks/0106-screenshots/`): NOT CAPTURED.

## Deviations from the brief

1. **Visible-label guard conflict (2 failing tests).** Brief Step 2 sets `.dashboard-calendar .cal-cleaning-label { display:none }` on desktop. `_assert_cleaning_day_marker` (test lines 186-198, desktop branch) asserts the label is displayed, fits, and contains "Cleaning". I did not weaken it. Owner or orchestrator decision needed (see questions).
2. **`host-design0123.css` line 99 overrides the list heading.** `body.host-workspace .cleaning-page .cleaning-date-group > h3 { font-size:clamp(24px,3vw,28px) }` wins over the brief's rule. Per the brief I did not edit that file. I kept a compact `body.host-workspace ...` h3 rule at the end of `cleaning.css`. It has equal specificity and loads later (`base.html` loads host-design0123.css first), so it wins. The brief said this line "may stay if harmless"; it was not, so I replaced it.
3. **Font sizes raised to keep existing legibility guards.** `.cleaning-instructions` 13px to 14px (test requires ≥14). `.cleaning-pin` 15px to 20px (test requires ≥20; the removed compact block used 20px for the same reason).
4. **Gantt 20px rule wrapped in `@media (min-width:761px)`.** Otherwise the 4-class selector beats the mobile 44px gantt height.
5. **Overflow chip rule replaces the desktop orange `.cal-day-summary.has-cleaning-overflow` block.** It is not wrapped; mobile sizes (44px) still come from the existing later mobile rule. Mobile chips lose the old orange.
6. **Pill colours apply at all widths.** Sizes and touch padding at ≤760px come from the existing mobile rules, unchanged. Only the colours and border changed on mobile.
7. **Card warnings only are amber.** `.cleaning-card .cleaning-warning` is amber. Form alerts that also use `.cleaning-warning` (role="alert" in `cleaning_edit`, `cleaning_settings`, `cleaning_shares`) keep the old red base style, so error severity is not lost. The day-dialog warnings in `dashboard-calendar.js` also keep the base style.
8. Removed superseded `.cleaning-page .cal-event.is-cleaning-marker { border-radius:5px }` and `.cleaning-page .cal-event[data-event-kind=cleaning]`.
9. Not touched, as the brief did not list them: `.cal-cleaning-legend-swatch` (orange) in `dashboard-calendar.css`.

## Test assertion changes (`App/tests/test_cleaning_browser.py`)

- `_assert_cleaning_day_marker`: pill background `rgb(245,185,66)` to `rgb(255,244,214)` (`--amber-bg`); colour `rgb(32,32,30)` to `rgb(107,58,0)` (`--status-action-ink`). The contrast assertion (≥7) is unchanged; by hand the new pair is about 8.6:1.
- Date heading size `16 <= x <= 18` to `12 <= x <= 14` (brief: 13px).
- Overflow chip background `rgb(245,185,66)` to transparent (`rgba(0, 0, 0, 0)` or `transparent`).

No touch-target, overflow or accessibility assertion was weakened, except the visible-label guard, which is left failing on purpose (deviation 1).

## Questions for the orchestrator

1. Pill label: keep "Cleaning" visible on the desktop pill (then the brief's `display:none` changes, and the pill is icon + "Cleaning" + property), or keep icon + property and change the test to check `aria-label` instead?
2. Should `host-design0123.css` line 99 be removed in a follow-up (owner or another task)?
3. Is the mobile colour change (deviation 6) and the plain mobile overflow chip (deviation 5) acceptable?
