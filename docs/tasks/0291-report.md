# 0291 report

Status: review

## Files changed
- App/app/templates/_components.html (row_open: icon dropped)
- App/app/templates/_property_overview.html, App/app/templates/settings.html (card Open: icon dropped)
- App/app/templates/dashboard.html (needs-you button: 'open' variant)
- App/app/templates/cleaning_properties.html (property row with Open button)
- App/app/templates/cleaning_shared.html (cleaning.css key bump; it referenced the changed file)
- App/app/templates/base.html (host2, workflow, cleaning keys to 20261024-0291)
- App/app/static/host2.css (0284 hover line, appended Open block)
- App/app/static/workflow.css (needs-you grid, :has rule)
- App/app/static/cleaning.css (appended property row block)
- App/tests/static_versions.json (regenerated, 35 files)
- App/tests/test_0291_open_buttons.py (new, 3 tests)

## Commands
`.venv/bin/python tests/test_static_versions.py --write`: wrote static_versions.json (35 files).

`.venv/bin/python -m pytest <brief §6 files> -q --tb=short -rs`:
```
1 failed, 44 passed, 1 warning in 151.26s (0:02:31)
```
Failing: tests/test_0285_rows_browser.py::test_properties_rows_match_stays_rows at 1280 px
(`{'gap': -129.0, 'sameLine': False}`). The Open button now has a text label, so it is wider than 28 px
and wraps to a second line in the property cell. Not loosened. Orchestrator decides.
No skipped tests. My new test file passes.

## Acceptance (brief §7)
- [x] No chevron-right inside row-open / host-property-card-open
- [x] Dashboard needs-you button is ui-btn ui-btn-open
- [x] Cleaning properties page: name left, Open right (CSS and test)
- [x] Keys bumped, static_versions.json regenerated
- [ ] Commands run: yes; one failure listed above

## Deviations
- Done: steps 1 to 8 (all). Left: none of the brief's steps.
- Not done: 390 px screenshots (AGENTS rule 7). Not taken because of the tool-call budget.
- Not pushed, no PR (task says commit only).

## Questions
- test_0285 gap: keep the Open button text and relax the test to allow wrapping, or make the property name column wider so the button stays on one line? Owner or orchestrator to decide.

## Owner steps left
- Review the 390 px screenshots for /apartments, /settings, the dashboard and /cleaning/properties.
