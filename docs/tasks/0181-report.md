# 0181 report

Status: blocked

## Files changed
- App/app/static/host2.css (0181 block, min-width 1024 px)
- App/app/templates/base.html (host2.css key 20261020-0181)
- App/tests/static_versions.json (regenerated)
- App/tests/test_design_guardrails_browser.py (test_table_rows_have_their_own_border_on_desktop)
- docs/tasks/0181-screenshots/ (20 PNGs), docs/tasks/0181-report.md

## Commands
- `python3 scripts/design_lint.py` -> `design lint: OK`
- `App/.venv/bin/python tests/test_static_versions.py --write` and `pytest tests/test_static_versions.py -q` -> `3 passed`
- `pytest tests/test_design_guardrails_browser.py -k table_rows_have_their_own` (browser required) -> `1 passed`
- Screenshots: `App/.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD/App ...` -> 20 shots, 5 with problems (all /properties, 404)

## Step status
Done: steps 1 to 5 (5 partly: screenshots taken and reservations 390 and 1280 viewed, bordered rows aligned, no clipping seen).
Left: step 6 (browser test run with 0 skipped, plus the 0102 cleanup), step 7 (final commit and PR, not pushed).

## Deviations
- Step 5: the brief's `--new-app $PWD` fails because the tool needs the App dir (has .venv). Used `$PWD/App`.
- Step 5: `/properties` returns 404 in the app; the page was not screenshotted. Owner or orchestrator to pick the right route (likely /apartments).
- Commit messages follow `0181 step k`, with the trailer names from the owner's message.

## Questions
- Which route replaces /properties for the screenshot list?

## Owner steps left
- None yet. After step 6 passes, review and merge with scripts/merge-pr-on-green.sh.
