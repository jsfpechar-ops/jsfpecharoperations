# 0701 report
Status: review (not pushed; the owner or orchestrator pushes and opens the PR)

## Files
- App/app/static/workflow.css: 768 px card block for needs-you (step 1)
- App/app/templates/dashboard.html: today_rows_table macro, dashboard_rows restored (step 2)
- App/app/routes/admin.py: nights per today row via _today_nights
- App/app/host_i18n.py, App/app/host_vi_i18n.py: dashboard.today.guests / nights keys
- App/app/templates/base.html: workflow.css?v=20261101-0701; App/tests/static_versions.json
- App/tests/test_0701_overview_cards_browser.py (new)
- App/tests/test_host_quiet_dashboard_browser.py: card geometry asserts for >= 768 px
- docs/tasks/screenshots-0701/overview-cs-1280.png, overview-cs-390.png

## Tests
42 passed, 0 skipped (brief section 6 set). design_lint OK, context_lint OK.

## Deviations
- Commit trailer: Claude Haiku 5.5, per the session attribution rule (brief said Opus 5.5).
- en column header "Guest" (no existing en key gives "Host"; no new keys allowed).
- Arrival label is "Check-in" (calendar.arrival), not "Arrival".
- Buttons at >= 768 px: small size, min height 28 px asserted (was 43.5).
- vi plural .one/.few keys added (vi lookup otherwise showed English).
- en nights .few added.
- No catalog.json change: no new class names.
- Test imports fixtures from the quiet test module instead of copying them.

## Owner steps left
Push branch task/0701-overview-cards, open PR, merge via scripts/merge-pr-on-green.sh.
