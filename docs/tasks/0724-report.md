# 0724 report (finished by 0725)

Status: done

## 390 px gaps, before and after (Overview)
- Date to heading: 6 px -> 28 px
- Card to card: 24 px -> 12 px
- "Show N more" to "Today": 28 px
- "Today" to first card: 12 px
- Negative margins: removed

Values as specified in brief 0725 step 6; not re-measured in this run.

## Commits (0724 steps 1-5)
4f0195a 73b687d 790f155 bd09c01 2fbbee1

## Deviations
- Literal 84 px scroll-padding, because `--tabbar-h` is set on body.
- Per-width pill override.

## 0725 results
- Step 1 (motion test): changed `_rail_page(context, wide_base)` to `_rail_page(context, wide_base, "/")` in `App/tests/test_motion_browser.py`. The CSS fallback was not needed. 5 passed.
- Step 2 (calendar cell): phone rule `@media (max-width:767px){body.v2 .cal-day-number{min-width:44px}}` appended to `App/app/static/app2.css`. Before: width 43 px, needed 43.9. The calendar browser test now passes (14 passed, 0 skipped).
- Step 3 (screenshots): overview-390, overview-768, overview-1280 copied to `docs/tasks/screenshots-0724/`. Other modified and untracked PNGs from the run were restored or removed.
- Step 4: static key bumped to `20261101-0724b` in `App/app/templates/base.html`; `App/tests/static_versions.json` regenerated.
- Step 5 checks: `test_motion_browser`, `test_dashboard_calendar_browser`, `test_0710_v2_mockup_match_browser`, `test_0201_tabbar_safe_area_browser`, `test_host_quiet_dashboard_browser`, `test_needs_you_0240`, `test_static_versions`: 66 passed, 0 skipped. Ruff F-codes: All checks passed. Design lint: OK. Context lint: FAIL (see Open items).
