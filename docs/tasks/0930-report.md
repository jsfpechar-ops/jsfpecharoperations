# 0930 report: calendar stay bars end halfway into the departure day

Status: review

## Changed

- `App/app/static/dashboard-calendar.css`: removed `margin-right: 2px` from `.cal-pill` (desktop rule line 764, phone rule line 798). Now `margin:0`. `.continues-start { margin-left:0 }` kept.
- `App/tests/test_dashboard_calendar_browser.py`: 0891 right-edge check and 0930 test use the 4b rule (left = arrival cell middle + g/2, right = departure cell middle - g/2, 1 px tolerance, g from `getComputedStyle(.cal-pills).columnGap`). `PILLS_0891` returns `rightAbs` and `depMid`.
- Expectation changes (the 2 px margin no longer exists, orchestrator decision):
  - line ~1037: `abs(pill["right"] - 2)` -> `abs(pill["right"])`
  - line ~1084: `c["2026-12-06"]["r"] - 2` -> `c["2026-12-06"]["r"]`

## Test run (from App/)

`UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_cleaning_browser.py -q --tb=line -rs`

Result: **84 passed, 0 skipped** (3m28s).

A temporary test file used only to take `one-night-390.png` was removed afterwards.

## Screenshots (docs/tasks/screenshots-0930/)

- `week-390.png`: the stay 5 to 8 Dec runs in from the Monday edge (continues from the week before) and ends in the middle of the 8th. The 8 to 11 stay starts in the middle of the 8th, so the two touch with a small gap and do not overlap. "+N" is not shown in this week.
- `week-1280.png`: stay A starts at the Monday edge and ends at the middle of the 8th. Stay B starts in the middle of the 8th and ends in the middle of the 11th. The gap between them is about 12 px, the desktop column gap. The name is ellipsized, and the same two bars appear in a second row, which is how the screenshot locator captures the week.
- `one-night-390.png`: a 1-night stay 5 to 6 Dec. The bar starts in the middle of the 5th and ends in the middle of the 6th, and the name is ellipsized ("090...").

## Not done

- No commit, no push, no PR.

Update (CI fix, section 4c): bumped the calendar CSS/JS keys in App/app/templates/_dashboard_calendar.html to v=20261104-0930a and regenerated App/tests/static_versions.json. Run: 87 passed, 0 skipped (static versions + the three browser files).

Update (CI shard 4, section 4d): added min-width:44px to the 768 px pill rule and justify-self:end to .cal-pill.continues-end; bumped both keys to 20261104-0930b. Run of the four files: 85 passed, 3 failed, 0 skipped (test_0891_airbnb_month_tiles_and_pills[768] and [1280]: pill left edge off by 178 px and 123 px; test_0930_stay_bars_start_and_end_halfway_through_their_days[1280]: a1 left edge off by 45 px). Cause: justify-self:end makes the continues-end item size to its content instead of filling its grid span. Status: blocked, stopped per brief section 4d.

Update (4d, final): rule is now `.cal-pill.continues-end { justify-self:end; width:100%; }` (min-width:44px on the base pill rule); both keys 20261104-0930c; static manifest rewritten. Four files in full: 88 passed, 0 skipped, 0 failed (includes the earlier 3 failures and the Sunday-arrival test). Status: review. No commit, no push.

Update (4e, final): pill min-width is now 48px at 768 px+ (44px tap target still holds); both keys 20261104-0930d; static manifest rewritten. Four files in full: 88 passed, 0 failed, 0 skipped, exit 0. Status: review. No commit, no push.
