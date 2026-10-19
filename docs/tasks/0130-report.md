# 0130 report

Status: blocked

## Files changed
- App/app/host_i18n.py (step 1: nav.cleaning, nav.more, nav.admin, nav.smart_locks in EN and CS). Commit bf6a829 "0130 step 1".

## Commands
- `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x`
  Last lines: `sqlite3.OperationalError: no such table: apartment`, then
  `FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `1 failed, 2 passed`.
- Failed twice (same result on rerun). Also fails at base commit 5423051 with the i18n file reverted, so it is not caused by step 1.

## Section 7
- [ ] Not reached.

## Deviations
- Done: steps 1 to 1. Left: steps 2 to 10 (not started).
- The failing test is not in the brief's known-failure list. It is a DB schema issue in the test setup (table `apartment` missing when this file runs alone), not a string issue.

## Questions
- Should the test run be fixed first (for example migrations in the fixture), or is this test expected to fail when run in isolation? Please confirm before I continue with steps 2 to 10.

## Owner steps left
- None yet.
