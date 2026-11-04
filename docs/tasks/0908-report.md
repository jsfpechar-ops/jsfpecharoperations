# 0908 report: calendar stay bars end halfway into the departure day

Status: blocked

## Changed

- `App/tests/test_dashboard_calendar_browser.py` only:
  - `PILLS_0891` now also returns `rightAbs` (pill right edge) and `depMid` (departure cell middle). `halfEnd` is taken from the departure cell.
  - 0891 right-edge assertion: a pill that ends halfway into its departure day must end at departure cell middle minus g/2 (1 px tolerance). Pills that run into the next week keep the Sunday edge minus 2 px.
  - 0908 test: left edge = arrival cell middle + g/2; right edge = departure cell middle - g/2; touching stays have a gap of g. g is read from `getComputedStyle(.cal-pills).columnGap`.
- No CSS or JS changed in this run.

## Test run

Command (from `App/`, all three files, no `-x`):
`UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_cleaning_browser.py -q --tb=line -rs`

Result: **5 failed, 79 passed, 0 skipped** (3m20s).

Failures (all right-edge checks, all short by about 2 px):
- `test_0891_airbnb_month_tiles_and_pills`, 3 of its width cases: pill right = departure middle - g/2 - 2 (e.g. 141.56 vs 143.56 at 390 px).
- `test_0908_stay_bars_start_and_end_halfway_through_their_days`, 2 width cases: stay A right edge (12-07 to 12-08) at 92.14 vs expected 94.13.

Every left-edge check passes. The gap between back-to-back stays is as expected in the failing cases that reach that check.

## Why it is blocked

The 2 px shortfall equals the `margin-right: 2px` that brief step 4 asks for. Brief section 4b says the right edge is departure middle minus g/2, with no extra 2 px. The two rules conflict by 2 px. The brief says to stop and report when a test fails for a reason other than the 4b rule. I did not change the CSS, and I did not loosen the expectations to hide the margin.

Decision needed from the orchestrator: remove the 2 px right margin (so the 4b rule holds exactly), or keep it and change the 4b expectations to "departure middle - g/2 - 2".

## Screenshots

- Step 3 not done: no new 1-night 390 px screenshot was taken. `docs/tasks/screenshots-0908/one-night-390.png` does not exist.
- `week-390.png` and `week-1280.png` were not viewed in this run.

## Not done

- Commit and push: not done (brief says do not commit or push).
- PR: not opened.
- Owner steps: none until the orchestrator decides the margin question.
