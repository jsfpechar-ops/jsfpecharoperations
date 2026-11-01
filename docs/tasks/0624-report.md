# 0624 report (executor: Haiku 5.5)

Status: blocked

## Files changed

- `App/app/payments_consent.py` (new, step 1), commit `78957afb`
- `App/app/retention.py` (step 2: `payments_terms_accepted` added to the never-expire list), commit `87ae04e4`
- `App/app/host_i18n.py` (steps 3 and 4: EN and CS `payments.consent.*` keys, one commit for both steps), commit `ca4014e6` (message says "step 3")
- `docs/tasks/0624-payments-consent.md` (Status line only: todo, then in-progress, then blocked)
- `docs/tasks/0624-report.md` (this file)

Steps 5 to 13 not started.

## Commands

- Step 1 `cd App && .venv/bin/python -c "import app.main"`: no output (pass).
- Step 2 `cd App && .venv/bin/python -c "import app.main"`: no output (pass).
- Step 4 `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x` (run twice, same failure):
  ```
  ubyhost:main.py:246 unhandled error on /l/{token}
  sqlite3.OperationalError: no such table: apartment
  FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects
  1 failed, 2 passed
  ```
  The same test also fails with the step 3 and 4 edits stashed (checked once), so the failure is not caused by the i18n keys. The test hits `/l/{token}`, which queries the `apartment` table, and the database has no such table. Likely a test-database setup problem in this container; not investigated further, per the executor rules.

## §7 acceptance

- [ ] Not reached.
- [ ] Not reached.
- [ ] Not reached.
- [ ] Not reached.

## Deviations

- Steps 3 and 4 share one commit (`ca4014e6`, labelled "0624 step 3").

## Questions

- `tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects` fails with "no such table: apartment" in this container, before any consent code is reached. Does this test pass on `main` in CI or locally? If yes, the container DB needs initialising (for example `db.init_db()` or the test DB env var). Please advise before the executor retries.

## Owner steps left

- None yet. The orchestrator decides whether to fix the test environment and re-run the brief from step 5, or to close it.
