# 0124 report: CI fixes (funnel window, create popover reclamp)

Status: review

## Files changed (vs df8b842, App/ only)

- App/tests/test_admin_funnel.py: upper bound `created_at < until` on the in-window query (steps 1).
- App/app/static/dashboard-calendar.js: ResizeObserver on createDialog re-runs placeCreate (step 2).
- App/app/templates/base.html: not changed (see Deviations).

## Commands (last lines)

- Step 1, `pytest tests/test_admin_funnel.py -q --tb=short -x`: `9 passed, 1 warning in 1.35s`
- Step 1, `pytest tests/test_signed_in_chrome.py tests/test_admin_funnel.py`: `25 passed, 1 warning in 1.77s`
- Step 2, `node -e "new Function(...)"`: `syntax-ok`
- Step 4, `UBYHOST_REQUIRE_BROWSER=1 pytest ...::test_create_popover_reclamps_when_switching_to_taller_stay_form -rs`: `2 passed, 1 warning in 4.00s`
- Section 6, `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_dashboard_calendar_browser.py -rs`: `11 passed, 1 warning in 29.37s` (0 skipped)
- Section 6, `pytest tests/test_skeleton_loaders.py`: `10 passed, 1 warning in 0.65s`
- Screenshot run with `UBYHOST_SHOTS_DIR` set: `2 passed`. Output file: `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/calendar-create-popover-reclamp-1280.png` (not viewed).

## Section 7

- [x] Both named tests pass with the browser required.
- [x] `git diff df8b842 --stat -- App/` lists only the two files above.
- [ ] Bounding box line: the test prints none under `-s`. The screenshot is quoted instead (file name has a `calendar-` prefix).

## Deviations

- Step 3 done after coordinator approval: bumped `?v=20261016-0123-refresh1` to `refresh2` in `App/app/templates/_dashboard_calendar.html` line 170 (outside section 3). Commit 02d04e8.
- Step 3 (cache bust): the `dashboard-calendar.js?v=20261016-0123-refresh1` tag is in `App/app/templates/_dashboard_calendar.html`, not `base.html`. That file is outside section 3, so I did not change it. The tests load fresh and do not need the bump.
- Done: steps 1, 2, 4, 5 (commit made for steps 1 and 2 separately; step 5 message applies to the same change set). Left: step 3 (bump) only.

## Questions

- Should the `refresh1` to `refresh2` bump go in `_dashboard_calendar.html`, which section 3 does not list? Owner or reviewer decides.

## Owner steps left

None.
