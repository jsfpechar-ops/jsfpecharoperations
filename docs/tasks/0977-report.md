# 0977 report

Status: blocked

Done: steps 1 to 4 (step 4 partly). Left: step 4 failures (below), steps 5 to 10 (feed URL lint, wording revert, stay-fee tests, verification and screenshots, final report, PR review).

## Files changed
- Renames: docs/tasks 0958 to 0964 files to 0978 to 0984 (step 1).
- Text references to 0958 to 0964 renumbered in App/app, App/tests, docs/tasks (script, 375 replacements).
- Merge of origin/main (step 2): six conflicts resolved by hand (app2.css both sides, the rest branch side plus main's 0964 comment in v2_mockup.py).
- Cache keys 20261106-0977: base.html, guest/base.html, _dashboard_calendar.html, _signature_script.html, static_versions.json (step 3).
- App/tests/v2_mockup.py: stay-dates small@320 and b@320 re-pinned to 94px, 0977 comment added (step 4).

## Commands (last lines)
- Step 1 collect: `pytest test_host_property_controls_browser.py test_guest_browser_e2e.py --collect-only` gives 55 tests collected.
- Step 3: `pytest test_static_versions.py test_wp07_cache_heartbeats.py -q` gives 16 passed.
- Step 4: `pytest test_0710_v2_mockup_match_browser.py -k stay -q -rs` gives 3 failed, 39 passed, 141 deselected. Failures: stays at 320 and 390 px, `.mh .big, .head h1` width app=100.203px mockup=77.0625px; stay at 320 px, `.stay-dates .tot` width app=238px mockup=280px. These pins are not in the brief's list; not changed.

## Section 7 checklist
- [x] merge-base with origin/main; no conflict markers
- [x] static_versions test passes
- [ ] stay mockup tests pass (3 failing, see above)
- [ ] layout lint, validation wording, stay-fee tests, screenshots: not run (steps 5 to 8 not started)

## Deviations
1. Step 1: docs/tasks/0977-pr790-merge-main.md skipped (the script would have rewritten this brief's own table).
2. App/.venv was missing; created from requirements.txt and requirements-dev.txt, plus playwright==1.63.0 (gitignored).
3. Step 3: the brief named three keys, but signature.js (_signature_script.html, guest/base.html) and dashboard-calendar.css (_dashboard_calendar.html) also changed in step 1; the static test refused to write until their keys were bumped to 20261106-0977.
4. Step 2: kept main's "# 0964:" comment line in v2_mockup.py (brief section 5 says main's 0964 comments stay).

## Questions
- Are the `.mh .big` (stays 320/390) and `.stay-dates .tot` (320) mismatches present on origin/main too? Not checked (tool budget).

## Owner steps
None yet. PR #790 is not merge-ready: the mockup test must pass before the brief can continue.
