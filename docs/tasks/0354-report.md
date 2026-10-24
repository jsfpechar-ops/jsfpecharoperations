# 0354 report

Status: review

## Files changed
- App/app/guest_guide.py (steps 1 to 4, incl. apply_catalog.py)
- App/app/host_i18n.py (step 1, apply_catalog.py)
- App/app/templates/_ui.html (steps 5, 6)
- App/app/templates/guest_guide_card.html (step 7)
- App/app/templates/guest_guide.html (step 8)
- App/app/static/host2.css (step 9)
- App/app/templates/base.html (step 10)
- App/tests/static_versions.json (step 11)
- App/tests/test_guest_guide.py, App/tests/test_guest_guide_pages.py (steps 12, 13)
- docs/tasks/0354-report.md

## Commands (last 5 lines each)
- `apply_catalog.py`: `catalog: 11 topics, 24 cards, 17 default`
- `test_static_versions.py --write`: `wrote .../App/tests/static_versions.json (36 files)`
- `pytest tests/test_guest_guide*.py tests/test_guide*.py tests/test_leon.py` (browser env, -rs): `174 passed, 1 warning in 29.95s`, 0 skipped
- `pytest tests/test_static_versions.py`: `3 passed, 1 warning in 0.12s`
- `pytest tests/test_*_i18n.py ... tests/test_design_*.py` (browser env, -rs): `3 failed, 180 passed, 2 warnings in 124.53s`. The 3 failures are the known test_host_i18n.py ones (Vietnamese x2, language endpoint). 0 skipped.
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `design_lint.py`: `design lint: OK`
- `context_lint.py`: `context lint: OK`

## Section 7 acceptance
- [x] Only the section 3 files change (plus the report).
- [x] New tests pass (catalog complete en/cs, existing property gets cards, skipped counts as answered, ghost text test in pages file).
- [x] Both lints OK.

## Deviations
- Step 10: the anchor `/static/host2.css?v=20261022-0289` was not in base.html; it held `?v=20261024-0302e`. Per coordinator instruction the key is now `?v=20261024-0354` (not the brief's `-0304`). No other template links host2.css.
- Step 13 applied after the append in step 12 (test file ends with the appended tests).
- Guide suite without browser env showed 3 skipped; with the browser env it shows 0 skipped.

## Questions
- None open.

## Owner steps left
- Orchestrator adds the 390 px screenshots (card list, Wi-Fi card) per rule 7.
- Review and merge once CI is green.
