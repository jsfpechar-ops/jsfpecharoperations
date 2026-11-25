# 2042b report: guest parity cases, cookies, run

Status: blocked (PIN pass crashed; tool-call cap reached at step 6c)

## Done

- Step 0: Go handle kept and terminated in try/finally (commit 9ac2474). Leftover `ubyhost-web-parity` processes: 0 before and 0 after the short run and after each later run.
- Step 2: `extra_cookies` in `_capture` and `run_case2` (commit c6b9aaa; committed together with step 3 by mistake).
- Step 3: `GUEST_CASES` (20) and `PIN_CASES` (2) appended to `scripts/e2e/parity_cases.py`; counts checked.
- Steps 4 and 5: `run_guest_seed` hook, guest/PIN job loop, cookie tuples, PIN server start with `start_py_process`/`start_go` (commit 20e28f7, one commit for both steps).
- Step 6a smoke (`g-stay-claimed-*`, 390 px): 4 rows, all visible, no error, no SKIPPED. The note does not carry the py/go HTTP status for this case, so the 200 status is not confirmed.
- Step 6b, group H: 120 rows, 72 identical, 48 visible, 0 error, 0 SKIPPED. Log: `$TMPDIR/parity_h_run.log`. Report: `/root/.local/parity/visual/report-H.md`.
- Step 6c, PIN (`PARITY_PIN=1 PARITY_GROUP=P`): crashed, 0 rows. `_run_pre_sql` raised `sqlite3.OperationalError: unrecognized token ":"` (App/scripts/go_page_parity_screenshots.py:232, `db.execute`). The app db helper is on sqlite in this process, so the Postgres URL is not set for the harness process. Not investigated (cap).

## Per guest case, H group (cs and en give the same verdict at 390, 768, 1280)

- identical: g-hub, g-privacy, g-stay-unclaimed, g-stay-provisional, g-claim-landing, g-guide-stay, t-cleaner-share, t-unsubscribe
- identical but both 404 (not a real render): g-stay-locked, g-stay-gone, g-guide-apt, g-leon-apt
- visible: g-hub-claimed, g-stay-claimed, g-stay-claimed-nocookie, g-form-new, g-form-edit-complete, g-form-edit-partial, g-remove
- visible with a stack split: g-leon-stay (Python 404, Go 200)

## Seed

- `run_extra_seed` and `run_guest_seed` both ran with no SKIPPED row. Seed stderr `skipped` lines: see the count in the step 6 report line (0 expected).

## Left

- Step 6c PIN run (fix the Postgres URL for the harness process, then rerun `PARITY_PIN=1 PARITY_GROUP=P`).
- Step 7 acceptance: smoke status not confirmed; g-stay-claimed rendered status not checked.
- Owner: none.
