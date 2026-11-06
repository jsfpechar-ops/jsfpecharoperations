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
