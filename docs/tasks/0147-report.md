# 0147 report

Status: review

## Files changed
- App/tests/test_dashboard_phone_browser.py (0147-cont-3 step 1: 1280 branch checks scales in calendar view, gantt hides them)
- docs/tasks/0147-evidence/calendar-phone-390.png
- docs/tasks/0147-evidence/calendar-phone-1280.png

## Commands
- Step 5: `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_host_quiet_dashboard_browser.py -q --tb=line -rs`
  Tail: `14 passed, 1 warning in 82.10s (0:01:22)`, 0 skipped.
- Ruff `--select E9,F63,F7,F82,F401,F841` on the test file: see result in the executor reply.

## Screenshots
- 390: week rows are one line of day numbers with dots, "+1" on 14 to 18 October; toolbar has arrows left and "October 2026" right; property select above; no Gantt, settings, segments or selects; Today present.
- 1280: gantt with bars, all controls present.

## Deviations
- `git clean -fq docs/tasks/0102-evidence` was denied by the permission classifier and was not run. Only explicitly staged paths are committed, so the throwaway shots are not in the commit. Owner may run the clean manually.

## Questions
- None.

## Owner steps left
- Run `git clean -fq docs/tasks/0102-evidence` locally if the throwaway shots should go.
- Review and merge the PR (merge only via scripts/merge-pr-on-green.sh). No push was made by the executor.
