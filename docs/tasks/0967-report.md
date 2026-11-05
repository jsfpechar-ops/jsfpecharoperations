# 0967 report (B09: C02, C03)

Status: blocked
Reason: command 1 stopped at an existing test that the brief does not name. `test_calendar_geometry_locales_and_screenshots` (App/tests/test_dashboard_calendar_browser.py line 335) asserts `max(heights) <= 184` for `.cal-week` at 1024+ in calendar mode. With the new +N lane the week tile is 226 px (94 + 3 × 44). The brief's own risk list says the tile grows to `94 + 3 * 44`, so the 184 bound is stale. Changing it is outside §3 and §8 says to stop.

Done: steps 1 to 3 (commands 1 to 7 not run after the failure).
Left: command 1 (after the owner or orchestrator decides the 184 bound), commands 2 to 7, UX gate, report §7 ticks.

## Commits (branch codex/0967-b09-calendar-orient, not pushed)
- 3a92d95c 0967 step 1 (dashboard.html line 49)
- 7bd9c59d 0967 step 2 (CSS block, JS pillRow, two ?v= keys, static_versions.json)
- 5cd4763c 0967 step 3 (range(3) to range(4) in check_tiles_0891; four new tests)

## Files changed (excluding the brief)
dashboard.html 1 line; dashboard-calendar.css +16; dashboard-calendar.js +5/-1; _dashboard_calendar.html 2 lines; static_versions.json 4/4 (matches patch; `--write` wrote 49 entries); test_dashboard_calendar_browser.py +175/-2.

## Commands
1. `tests/test_dashboard_calendar_browser.py -rs -q -x`: FAIL (1 failed, 5 passed, 0 skipped)
```
E   AssertionError: [182, 226, 226, 94, 94, 94, ...]
E   assert 226 <= 184
1 failed, 5 passed in 59.97s
```
2 to 7: not run.

## §7 acceptance
None ticked. The 0967 tests did not run, so no screenshots were taken and the UX gate was not done. Design-system checklist not ticked.

## Deviations
- HEAD at start was 61508ab4 (brief commit on top of de537cb3, adds only the brief file). Worked on top of it.
- Created App/.venv symlink to the 0958 venv (git-ignored).

## Questions
Approve raising the line 335 bound from 184 to 226 (94 + 3 × 44), in the same file? Or another fix?

## Owner steps left
None until the orchestrator decides. No push, PR or merge was done.
