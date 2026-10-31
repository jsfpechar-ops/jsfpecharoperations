# 0458 report: deadline counts weekends only (status: blocked)

## Files changed
- `App/app/deadlines.py`: `is_working_day()` now returns `day.weekday() < 5`. Helpers kept (see Deviations).
- `App/tests/test_deadlines.py`: the one holiday case (`test_working_day_arithmetic_skips_public_holiday`) now expects 2026-11-18 (was 11-19), comment updated.
- `docs/tasks/0458-deadline-weekends-only.md`: brief copied in from commit 2a8063b (not present on this branch); Status set to blocked.
- `docs/tasks/0458-report.md`: this report.

## Commands
- `App/.venv/bin/python -m pytest tests/test_deadlines.py -q --tb=short -rs`: `25 passed in 2.05s`, 0 skipped. Run without -x for diagnosis; no failures.

## Not done
- Step 3 (deadline sentence in `docs/UBYPORT_CORE.md`): no such sentence. grep for "working day", "days", "deadline", "three", "within" returns nothing in the 134-line file.

## Copy hits (holiday wording)
- `App/app/guide_i18n.py:134` (`guide.reporting.deadline`): "Weekends and Czech public holidays do not count." Now false. Not a template, so not changed.
- `App/app/reporting.py:565`: comment "a weekend or holiday". Brief says do not touch reporting.py; not changed.
- `App/app/deadlines.py` line 1 docstring still says "Czech public holidays".

## Deviations
- Helpers `public_holidays`, `holiday_set`, `easter_sunday` NOT deleted. `App/tests/test_deadlines.py` imports them (`test_easter_sunday_known_years`, `test_czech_public_holidays`, lines 25-26). Brief step 1 says delete only if nothing else imports them. Acceptance "no remaining reference to holidays in App/app" is therefore not met.
- Test name `test_working_day_arithmetic_skips_public_holiday` kept, although it is now misleading.

## Questions for owner
1. Delete the helpers and the two helper tests, or keep them as dead code?
2. Change the guest guide sentence in `guide_i18n.py:134` to "Weekends do not count."? It is false now.
3. Where is the deadline described in docs? UBYPORT_CORE has no such sentence.
