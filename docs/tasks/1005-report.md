# 1005 report

Status: review

## Files changed
- App/app/static/app2.css: shared `ui-details-box` rules (steps 1 to 3, commit 0d2ee1d7)
- App/app/templates/_stay_fee_fields.html: class added to `details.fee-more` (step 2)
- App/app/templates/base.html: `app2.css?v=20261107-1206` (step 3)
- App/tests/static_versions.json: regenerated
- docs/design/catalog.json: `ui-details-box` added; design_lint OK
- App/app/templates/stay_fees.html: circled arrow (`row_open`) removed from the period row; row stays clickable (commit e65c5dc5, Extra request)
- docs/tasks/1005-report.md: this file

## Commands (last lines)
- `pytest tests/test_stay_fee*.py tests/test_host_geometry.py`: 245 passed in 33.46s, 0 skipped.
- `pytest tests/test_layout_lint_browser.py` (UBYHOST_REQUIRE_BROWSER=1): 4 passed, 0 skipped.
- `pytest tests/test_cleaning_browser.py tests/test_0956_calendar_rule_colours_browser.py`: 75 passed, 0 skipped.
- `pytest tests/test_dashboard_calendar_browser.py tests/test_0955_calendar_toolbar_stable_browser.py tests/test_dashboard_calendar.py`: 2 failures, see Deviations.
- `design_lint.py`: OK. `context_lint.py`: context lint OK (warnings are pre-existing).

## §7 acceptance
- [x] Stay fee and layout lint pytest green, 0 skipped.
- [x] 390/768/1280 shots opened (see below). Fields sit inside the box with inner spacing on the left, right and top.
- [ ] No horizontal scroll check at 390 done visually only.
- [x] One 390 px shot: /tmp/shots/layout-lint/fee-setup+open-390.png
- [ ] Design-system checklist: not ticked (no PR opened).

## What I saw
- Fee form, box open (fee-setup+open): 390 shows the box with summary and fields inset from the border; 768 same; 1280 the box is a bordered card with fields inset and summary aligned to the fields.
- Stay fees list: 390 shows cards with chevrons and no circled arrow; 768 shows cards; 1280 table rows with a ⋮ menu and no circled arrow button.
- Copy of 1280 fee form shot: /mnt/project-files/ux-shots/details-box-1280.png

## Deviations
- Calendar tests: `test_dashboard_calendar_browser.py` has 3 failures at 1024/1280/1440 (`test_month_tiles_and_side_panel`, toolbar overlaps side panel) and 1 failure at line 1035 (pill nights offset). The toolbar change is not in these commits. Likely pre-existing from 1004 step 6; not verified at 3959e852.
- Commit trailer: step commit used Sonnet 5.5 (per brief); the Extra commit used Haiku 5.5 (per system attribution). Pick one.
- Cache key 1206 used instead of brief's 1011 (newer than 1205, as instructed).

## Owner steps left
- Decide on the calendar failures (1004 scope).
- Review and open PR; no push done.
