# 0968 report (B10 executor)

Status: blocked. Stopped after command 4 under the brief's rule (same cause twice). Commands 3 and 5 not run. No screenshot reviewed, so the UX gate is not met.

## Commits (branch codex/0968-b10-stay-list, not pushed)
- a67b517b 0968 step 2: app patch (i18n en/cs/vi, reservations.html, app2.css, base.html) and static_versions refresh
- 4b0f8bc5 0968 step 3: test patch
- a18c21f8 0968 step 4 test fix: fixture teardown and range assertions (see deviations)
- plus this report commit

## Commands (UBYHOST_DB unique per run; screenshots dir /tmp/ubyhost-b10)
1. test_host_filter_panels_browser.py + test_0285_rows_browser.py: first run 5 passed, 1 failed, 1 teardown error. After one fix: 8 passed, 0 skipped.
2. test_static_versions.py + test_wp07_cache_heartbeats.py: 16 passed, 0 skipped.
3. Not run (stopped).
4. i18n/copy set: 43 passed, 3 failed, 0 skipped. Failed twice with the same cause: test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects, ::test_a_signed_in_dashboard_keeps_vietnamese, ::test_language_endpoint_accepts_vietnamese, all "sqlite3.OperationalError: no such table". Same 3 fail on base 7b0355c4 (git archive copy, 11 passed), so pre-existing, not caused by B10. This file has no DB setup and relies on order.
5. Not run (stopped).
6. context_lint.py: "context lint: OK" (warnings only: 4 commits touched App/ after status.md update).

## Deviations
- Command 1 failure 1: fixture teardown FK error on DELETE FROM user_account. Fixed by deleting alert and audit rows for the owner first.
- Command 1 failure 2: Apply with from = today resolves to range=upcoming (route logic in App/app/routes/admin.py about line 3339, existing behaviour). Assertions changed from range=custom to range= (range kept). Scope and apartment still asserted.
- App/.venv is a symlink to /tmp/ubyhost-0958-worktree/App/.venv. A .venv/.venv link already existed inside that venv (not created here).

## Screenshots
Command 1 wrote screenshots to /tmp/ubyhost-b10 (stays-default-{en,cs}-{390,768,1280}.png, filter-open/applied/empty-en-1280.png, heights.txt). Not opened or reviewed in this run. Section 7 not ticked.

## Owner or orchestrator steps
- Decide on test_host_i18n.py: add DB init or fix ordering (pre-existing on base).
- Re-run commands 3 to 5 and review the 390, 768 and 1280 screenshots before review.

## Diff stat (7b0355c4..HEAD, App only)
 App/app/host_i18n.py                         |  10 +-
 App/app/host_vi_i18n.py                      |   5 +-
 App/app/static/app2.css                      |   7 +
 App/app/templates/base.html                  |   2 +-
 App/app/templates/reservations.html          |   9 +-
 App/tests/static_versions.json               |   4 +-
 App/tests/test_0285_rows_browser.py          |   2 +-
 App/tests/test_host_filter_panels_browser.py | 222 ++++++++++++++++++++++++++-
 8 files changed, 251 insertions(+), 10 deletions(-)
