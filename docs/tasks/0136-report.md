# 0136 report

Status: blocked

## Files changed
- App/app/templates/reservation_detail.html (step 1, commit 4f587de)
- App/app/templates/guest_form_admin.html (step 1, commit 4f587de)
- App/app/host_i18n.py (step 2, commit below)

## Commands
- Step 1 grep: `grep -c 'verify-identity\|host.verify_'` gives 0 and 0. Compile check printed `compiled`.
- Step 2 patch printed `ok`.
- Step 2 tests: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`, last lines:
  ```
  FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects
  !!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
  1 failed, 2 passed, 1 warning in 1.85s
  ```
  Assertion (exception, verbatim): `sqlite3.OperationalError: no such table: apartment`, raised in app/routes/guest.py `_live_apartment` via `_open_link`.

## Deviations
- The same test fails without the step 2 edit. I checked with `git stash` on App/app/host_i18n.py, with the step 1 commit in place. Cause: conftest creates a fresh temp DB per run, and `TestClient(app)` without a context manager never runs migrations. The fix would change test code, which this brief does not allow. Brief section 6 lists this test only as a known failure when run alone; it also fails with its own file here.
- Stopped after the second failure of the same test, per the executor rule.
- Done: steps 1 and 2 (patch only). Left: steps 2 test, 3 to 6 (passport_photos comments, test edits, new test file, browser tests and screenshots, lint and commit).
- reporting.py and routes/admin.py are untouched (no diff).

## Questions
- Should the test_host_i18n language-endpoint failure be fixed in its own brief? Or should steps 3 to 6 continue with it accepted as known?

## Owner steps left
- None. Nothing pushed, no PR opened.
