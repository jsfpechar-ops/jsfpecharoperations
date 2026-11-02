# 0718 report (executor, session 2)

Status: blocked. Stopped at the 25-call limit. Two checks still fail (below). Screenshots were taken but not yet read.

## Commits (branch task/0718-v2-phone-shell, not pushed)
- 8d38f89: tab labels 12 px (orchestrator decision), app2.css key 20261101-0718b.
- eab367c: step 4, phone checks in v2_mockup.py and the 0710 test (phone screens, box metrics, tab-bar geometry, menu entry).
- Commit of this report: menu markup and CSS, key 20261101-0718e, screenshots.

## Test tails
- Full brief set, before the last menu CSS fixes: `2 failed, 60 passed in 187.61s`, 0 skipped. Failures: overview-768 and menu-320.
- Menu and static tests after the last fix: `1 failed, 7 passed`. Failure: menu-320 (see below). test_static_versions.py passes.
- design_lint.py: OK. context_lint.py: OK.

## Open failures
1. overview-768 (style): 21 differences on Dnes-page selectors (.head h1, .todo .card, .head .btn). The phone block applies below 1024 px, so 768 gets the phone classes while the test compares it with the desktop mockup. Left for brief 0719, as the brief allows. Not skipped.
2. menu-320 (style): `.card.me` height 117 px vs 108 px in the mockup. The fixture name wraps to more lines than the mockup's demo name. Not fixed.

## Deviations
- Tab labels 12 px instead of 11 px (orchestrator decision). Overrides for `.tab`, `.tab:not(.on)`, `.tab.on` font-size.
- Menu page: page title is `h1.big` (no host header), icon rows with chevrons (from _icons.html), `.card.me` with the mockup's avatar layout.
- Menu rows have no subtitle (`.row .t small` in missing_ok). The mockup subtitles are demo copy. Owner decision needed.
- Phone pages: desktop style checks are skipped at phone widths when the page has a phone_view. Phone checks compare phone_selectors only.
- Box width compared in px (±2 px), not as a fraction of the viewport.
- main has no horizontal padding below 1024 px (cards 20 px from the edge, as in the mockup).
- Menu desktop rows get min-height 48 px (tap target at 1024+).

## Screenshots
docs/tasks/screenshots-0718/: menu-390.png, overview-390.png, overview-768.png (full page). Not yet read.

## Owner steps left
None. Decisions needed: menu subtitles (copy); overview-768 wait for 0719 or accept the phone design at 768.
