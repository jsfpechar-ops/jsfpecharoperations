# 0956 report

Status: blocked

Done: steps A1 to A4, C and Part B applied (orchestrator-approved calc: --cal-lane 56px, chip margin with +8px -47px, app2.css min-height 52px + pl*56px + 60px). Chip geometry test passes at 768, 1024, 1280 (chip 1 is 8 px below the last bar at all three). Test file 0956: 13 passed, 0 skipped. Static versions: 3 passed after `--write`. context_lint: OK (warnings only, pre-existing).
Left: dashboard/0905/0955/0898/cleaning run (started in background, result not yet read), layout-lint-browser (not finished, timed out in shell), screenshots into docs/tasks/screenshots-0956/ and their review, final diff-stat check, push-free commit done below only if listed.

## Files changed
- App/app/static/dashboard-calendar.css: Part B lane 56px; chip margin-top calc; new min-width:1024px override (-24px)
- App/app/static/app2.css: cleaning tile min-height calc(52px + var(--pl,1) * 56px + 60px)
- App/app/templates/base.html, App/app/templates/_dashboard_calendar.html: cache key 20261105-0956b
- App/tests/static_versions.json: regenerated with --write
- App/tests/test_0956_calendar_rule_colours_browser.py: chip hit-test assertion (see Deviations)

## Commands (last lines)
- `pytest tests/test_0956_calendar_rule_colours_browser.py -q -rs -x`: `13 passed in 18.19s`
- `pytest tests/test_static_versions.py`: `3 passed`
- `python3 scripts/context_lint.py`: `context lint: OK`
- `pytest test_dashboard_calendar_browser ... test_cleaning_browser.py -rs`: started in background, output not read yet
- `pytest tests/test_layout_lint_browser.py`: not completed (shell timeout)

## Deviations
- Chip hit-test: `.cal-tile-chips` is `pointer-events:none` by design, so elementFromPoint at a chip centre returns the day button. The test now asserts the hit is inside the 8 Nov day button and not a pill. Geometry checks are unchanged.
- Gap below last bar at >=1024 measured 32 px with the 768 calc; added a min-width:1024px rule of -24px so it is 8 px at 1024 and 1280.
- Cache key bumped to 20261105-0956b because 0956 was already on the key.
- Executor cap reached (about 28 tool calls).

## Owner steps left
- None. No push, no PR.
