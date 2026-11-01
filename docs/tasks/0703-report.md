# 0703 report

Status: blocked

Done: items 1 to 4 (item 1 is an assertion only, see Deviations), cache key, static versions, 0284 button test (coordinator extra). Left: screenshots, 0284 line-open failure, report PR, owner steps.

## Files changed
- App/app/static/host2.css (0700 block: heading sizes, account card)
- App/app/templating.py (date_long filter)
- App/app/templates/dashboard.html (meta block)
- App/app/templates/_shell_sidebar.html (account block moved under search)
- App/app/templates/base.html (host2.css key 20261101-0703)
- App/tests/static_versions.json
- App/tests/test_0703_look_finish.py, App/tests/test_0703_look_finish_browser.py (new)
- App/tests/test_0284_states_browser.py (coordinator extra: button vs copy left edge)

## Commands
- Brief set (`pytest tests/test_0703_... tests/test_0700... tests/test_0701... tests/test_0702... tests/test_design_guardrails_browser.py tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_design_dashboard.py tests/test_static_versions.py -x -rs`): 39 passed, 0 skipped.
- Sidebar/account browser tests: none exist (glob empty).
- `python3 scripts/design_lint.py`: OK.
- `pytest tests/test_0284_states_browser.py -k needs_you_buttons`: FAILED at line 104 (after the new alignment asserts pass). Error: waiting for navigation to /reservations/7; log says the mock UbyPort is unreachable. Not yet confirmed as pre-existing.
- `python3 scripts/context_lint.py`: not run (cap reached).

## Deviations
- Item 1: the canvas assertion already passes on the base commit (nearest non-transparent ancestor of .needs-you is rgb(246, 246, 244)). No CSS added for item 1.
- Commit trailer: used Claude Haiku 5.5 per the session attribution, not Opus 5.5 as the brief said.
- Not pushed (brief). No PR opened.

## Questions
- Is the 0284 navigation failure pre-existing (mock UbyPort unreachable in this container)?

## Owner steps left
- Screenshots: `cd App && UBYHOST_SHOTS_0701=/tmp/wt0703/docs/tasks/screenshots-0703 .venv/bin/python -m pytest tests/test_0701_overview_cards_browser.py` (not run).
- Decide on the 0284 failure, then open the PR.
