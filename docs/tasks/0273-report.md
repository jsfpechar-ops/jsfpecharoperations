# 0273 report: friendlier setup wizard

Status: review

## Files changed
- App/app/templates/setup_wizard/_layout.html (meter, question header, nav_icon import)
- App/app/static/wizard.css (appended 0273 block)
- App/app/templates/base.html (wizard.css key 20261022-0273)
- App/app/host_i18n.py (EN and CS keys)
- App/app/host_vi_i18n.py (VI keys)
- docs/design/catalog.json (6 legacy classes for _layout.html)
- App/tests/static_versions.json (regenerated)
- App/tests/test_wizard_friendly_0273.py (new, 4 tests)

## Commands (last lines)
- `pytest tests/test_wizard_friendly_0273.py tests/test_static_versions.py tests/test_onboarding_wizard_survival.py -rs`: 31 passed, 0 skipped.
- `pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -rs`: 3 failed, 15 passed. Failures: test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects, test_a_signed_in_dashboard_keeps_vietnamese, test_language_endpoint_accepts_vietnamese. Error: `sqlite3.OperationalError: no such table: apartment` (db.py:1356). test_no_em_dashes.py alone: 4 passed. test_host_i18n.py alone: same 3 failures.
- `python3 scripts/design_lint.py`: design lint: OK

## Section 7
- [x] Question h2 and icon tile on each step (EN, CS, VI tested on calendar).
- [x] "n of 8 done" words; tick only when n > 0 (tested).
- [x] Design lint OK; static versions test passes.
- [x] New tests pass.
- Not done: 390 px screenshots (not taken; no browser run in this brief's commands).

## Deviations
- Done: steps 1 to 9. Left: none. Steps 5 and 6 share one commit (`0273 step 5`).
- Done-count test: `_full_apartment` is a complete apartment, so "0 of 8 done" cannot be shown without a bare apartment. The zero case uses monkeypatch on property_setup.done_count.
- Test 2 checks the page after the skip is posted to police (not a regex on the exact count).
- Acceptance blocked: test_host_i18n.py fails with missing tables, before any string lookup. Not verified as pre-existing (no baseline run). The brief said STOP on a repeated failure, so no fix was attempted.

## Questions
- Is test_host_i18n.py expected to pass when run alone? It needs DB setup that this brief did not cover.

## Owner steps left
- Decide on test_host_i18n.py before review.
- Orchestrator: test_host_i18n.py has the same 3 failures on main when run alone (isolation, not this brief).
