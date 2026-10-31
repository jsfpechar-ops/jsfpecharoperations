# 0458 report: deadline counts weekends only (status: review)

## Decisions applied (owner, via coordinator)
- Step 3 skipped: docs/UBYPORT_CORE.md has no deadline sentence (134 lines, no match for "working day", "days", "deadline", "three", "within").
- Helpers deleted: `easter_sunday`, `public_holidays`, `_HOLIDAY_CACHE`, `holiday_set` in `App/app/deadlines.py`. `typing` import reduced to `Optional`.
- Tests deleted: `test_easter_sunday_known_years`, `test_czech_public_holidays`, and `test_good_friday_only_from_2016` (it also called `public_holidays`). They were removed with the helpers.
- Test renamed: `test_working_day_arithmetic_skips_public_holiday` to `test_working_day_arithmetic_counts_public_holidays`. Expectation 2026-11-18.
- Copy changed, one key in three languages: `guide.reporting.deadline`:
  - `App/app/guide_i18n.py` (en): "Weekends do not count."
  - `App/app/guide_i18n.py` (cs): "Víkendy se nepočítají."
  - `App/app/host_vi_i18n.py` (vi): "Cuối tuần không được tính."
- `reporting.py` not touched (line 565 comment still says "weekend or holiday").
- Also fixed: `deadlines.py` line 1 docstring, and the `add_working_days` docstring sentence "a weekend or a public holiday" (now "a weekend"), since it became false.

## Files changed
- `App/app/deadlines.py`
- `App/tests/test_deadlines.py`
- `App/app/guide_i18n.py`
- `App/app/host_vi_i18n.py`
- `docs/tasks/0458-deadline-weekends-only.md` (brief copied from commit 2a8063b, Status: review)
- `docs/tasks/0458-report.md`

## Commands
- `App/.venv/bin/python -m pytest tests/test_deadlines.py -q --tb=short -rs`: `22 passed in 1.91s`, 0 skipped.
- `App/.venv/bin/python -m pytest tests/test_guide*.py tests/test_guest_guide*.py -q --tb=short -rs`: `148 passed, 4 skipped`. The 4 skips are browser tests (`test_guide_browser.py:19`, `test_guest_browser_e2e.py:39` x2, `test_guest_guide_table_browser.py:13`): `playwright` is not installed in the venv. Under the 0 skipped rule this is NOT a pass for the browser part. CI or an environment with playwright needs to run them.

## Deviations
- The 4 browser-test skips above (no playwright in this environment). Not fixed here.
- The test-map has no row for `deadlines.py`. Ran `test_deadlines.py` directly, per the brief.
