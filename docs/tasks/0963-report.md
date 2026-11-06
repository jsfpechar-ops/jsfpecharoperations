# 0963 report (blocked at step 4 stop check)

Status: blocked. Executor stopped per brief §8: a test pins the old `?v=` keys, and the fix needs a file outside §3.

## 1. Files changed (done, committed)

- App/app/main.py: `_access_kind` helper, `kind=` suffix in `_log_access` (step 1, commit a2190e9)
- App/app/static/cleaning.js: timer/focus refresh dispatches `CustomEvent` with `detail.background = true` (step 2, a891031)
- App/app/static/dashboard-calendar.js: `load(background)`, `X-Uby-Background: 1` header only when `=== true`, listener passes `event.detail.background` (step 3, a40d1fc)
- App/app/templates/_cleaning_screen.html, _dashboard_calendar.html: `?v=20261106-0963` (step 4, 42e9dc6)

## 2. Commands

- `.venv/bin/python -m pytest tests/test_access_log.py tests/test_perf_logging.py -q --tb=short -x` (step 1): `14 passed in 1.55s`
- `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x` (after step 4): `FAILED tests/test_static_versions.py::test_the_manifest_is_current`, `1 failed, 2 passed`. The manifest `App/tests/static_versions.json` still records `cleaning.js` v `20261102-0507` and `dashboard-calendar.js` v `20261105-0956b` with the old sha256 values. The test asks for `tests/test_static_versions.py --write`.

## 3. Section 7 ticks

- [x] Plain line unchanged (test_perf_logging passes)
- [ ] `kind=prefetch` / `kind=poll` tests: not written (step 5 not reached)
- [x] `grep -n background dashboard-calendar.js` shows 3 lines
- [x] Both script tags carry `?v=20261106-0963`
- [ ] OPERATIONS.md `kind=` and LogQL queries: not done (step 6 not reached)
- [ ] Branch pushed, no PR, lint clean: push done by this report commit; lint and step 7 not run

## 4. Deviations

- Step 4 check expected no pins. `App/tests/static_versions.json` pins both script keys. Stopped per §8.
- Step 5 (tests), step 6 (OPERATIONS.md) and step 7 (checks) not run.
- Commit trailer: the owner's instruction named Claude Opus 5.5; used as given.

## 5. Questions

- Update `App/tests/static_versions.json` (both entries, via `tests/test_static_versions.py --write`) inside this branch? This file is outside brief §3.

## 6. Owner steps left

- Decide on the manifest update above, then resume at step 5.
- After deploy, follow the owner steps in the brief (Grafana queries).

## Resume

Steps 1-4 were already committed. Done in this resume:

- Step 4b (approved amendment): `App/tests/static_versions.json` regenerated. Only the `cleaning.js` and `dashboard-calendar.js` entries changed (v `20261106-0963`). `tests/test_static_versions.py` passes. Commit `be66008`.
- Step 5: four `kind=` tests appended to `App/tests/test_access_log.py`. Commit `5d32efc`.
- Step 6: OPERATIONS.md Logs section gained the `kind=` paragraph and the three Grafana query bullets (13 insertions). Commit `ac61361`.
- Step 7 and the §6 rows: see the test runs below.

Test runs (last lines, verbatim):

- `tests/test_static_versions.py`: `3 passed in 0.10s`
- `tests/test_access_log.py tests/test_perf_logging.py`: `18 passed in 1.23s`
- `tests/test_access_log.py tests/test_perf_logging.py tests/test_metrics_0427.py`: `22 passed in 1.30s`
- `tests/test_cleaning*.py tests/test_calendar_*.py tests/test_dashboard_calendar*.py -rs`: `99 passed, 2 skipped in 7.58s`. The 2 skips are `test_cleaning_browser.py:18` and `test_dashboard_calendar_browser.py:17`: `could not import 'playwright.sync_api'`. Not run. Playwright is not in `App/.venv`, and system python3 has neither playwright nor pytest. Nothing was installed.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, all about other open briefs and the status update).

Brief §7 status: plain-line and kind tests pass; prefetch-wins test passes; both script tags carry the new key; OPERATIONS.md documents `kind=` and the queries; lint OK. Not re-verified in this resume: the `grep -n background` count (3 lines) from step 3. The browser tests above are not run, so the 0-skipped rule is not met.

Deviations:

- The two browser tests skip because Playwright is missing. Owner or CI must run them before merge.
- Commit trailer: the owner's instruction named Claude Opus 5.5, so that name is used.

Owner steps left: unchanged from the brief (Grafana queries after deploy).

## Orchestrator review (2026-11-06)

Code reviewed (main.py `_access_kind`, calendar `load(background)`): OK. Browser tests skipped locally (no Playwright in .venv); CI runs them before merge.

Production findings from the same session, for a later brief:
- `settings`: ~13k updates on 40 rows in 6 days (a write every ~40 s from a loop).
- `guest`, `cleaning_event`, `alert`: 100k+ full-table scans each. Harmless at 9 properties; add indexes or stop the loops before scaling.
- Signup: 33 GET /signup (all 200), 0 POST in 7 days. Real-visitor count to be checked in PostHog.
