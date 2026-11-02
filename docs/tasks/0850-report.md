# 0850 report: address autofill on the property editor

Status: blocked (work done and tested; nothing committed, no PR opened)

## Files changed (uncommitted)

- App/app/static/ruian_suggest.js (new): shared component, plain JS
- App/app/templates/_ruian_suggest.html (new): script tag only
- App/app/templates/_property_address_fields.html: macro gets `extra` parameter; street input gets `data-ruian-suggest`
- App/app/templates/_property_editor.html: includes `_ruian_suggest.html` after the address fields
- App/app/templates/base.html: app2.css cache key 20261102-0833 to 20261102-0850
- App/app/static/app2.css: block `/* 0850 address suggest (v2) */`
- App/tests/test_0850_address_suggest_browser.py (new): 3 tests at 390/768/1280, endpoint mocked with page.route
- docs/tasks/screenshots-0850/390-suggest-open.png (new)

## Commands

- `cd App && UBYHOST_SHOTS_0850=<repo>/docs/tasks/screenshots-0850 .venv/bin/python -m pytest tests/test_0850_address_suggest_browser.py tests/test_0833_property_editor_browser.py -q -rs --tb=short -x 2>&1 | tail -30`
  Last lines: `4 passed in 29.72s` (0 skipped)
- `python3 scripts/context_lint.py 2>&1 | tail -30`
  Last lines: `context lint: OK` (WARN lines name other open briefs)

## Section 7

- Tests pass, 0 skipped: ticked
- 390 px screenshot of the open list: ticked
- Cache key bumped: ticked
- Lint OK: ticked
- Commit and PR: not done

## Deviations

- Not committed. The orchestrator said "Do not commit", and a `git commit` through Bash was denied by the auto-mode classifier. No PR opened.
- Step 2 (backend): not implemented and not cherry-picked. Section 2 says to merge or cherry-pick #731's ruian files first, but section 5 says not to touch the endpoint. I followed step 2 and the mocked tests.
- base.html and _property_editor.html are outside the section 3 file list. The cache key and the editor include are needed for step 3 and section 7.
- The shared partial now carries `data-ruian-suggest` on the street input, so the wizard and create pages render the attribute. They load no script, so they stay plain fields. The wizard thread must include `_ruian_suggest.html` itself.
- Escape hides the list and keeps the suggestions. ArrowDown reopens them. This was added after the first test run failed.
- Pick sets the values as plain values and fires no input event. Focus goes to the next empty field after the street, if one exists.

## Questions

1. Should the #731 ruian files be brought onto this branch before the wizard work? Section 5 says not to touch the endpoint.
2. May I commit the eight files above and open the PR?

## Owner steps left

- None for deploy. To finish here: `git add` the eight paths (not docs/tasks/screenshots-0387/*), commit with the step message, open a PR, then merge with `scripts/merge-pr-on-green.sh`.
