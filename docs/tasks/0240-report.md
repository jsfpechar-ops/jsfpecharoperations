# 0240 report: Send by data box, backend

Status: review (30-call cap reached after all 9 steps; no commit, as the owner asked)

## Files changed

- App/app/migrations/0013_stay_fee_databox_send.sql (new)
- App/app/config.py (4 env vars + validity seconds)
- App/app/isds_gateway.py (new: configured, GatewayError, create_draft stub, portal_url_ok)
- App/app/routes/stay_fees.py (_send_texts helper, databox_send key, POST route)
- App/app/routes/databox_return.py (_land: signed-in redirect)
- App/app/retention.py (databox_sends step, cutoff line, workspace delete line)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (4 flash keys each)
- App/tests/test_databox_send.py (new, 14 tests)
- App/tests/test_databox_return.py (signed-in no-pending-row test; `auth` import; cleanup helper)
- docs/ENVIRONMENT.md (section "Data box sending (ISDS Odesílací brána)")

Not in git yet: nothing committed or pushed.

## Commands (last lines)

1. `.venv/bin/python -m pytest tests/test_databox_send.py tests/test_databox_return.py tests/test_stay_fee_send_panel.py tests/test_host_i18n.py tests/test_privacy_first.py -q --tb=short -rs -k "not geometry"`
   `45 passed, 1 deselected, 2 warnings in 8.73s`
   The deselected test is `test_send_panel_geometry_and_screenshots` (browser). Without `-k`, it fails at launch: Playwright wants chromium_headless_shell-1243, the container has 1194. Environment, not code. Not run, so no screenshots.
2. `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_retention*.py tests/test_migrations*.py -q --tb=short -k "not geometry"`
   `1 failed, 195 passed, 1 deselected, 1 warning in 12.76s`
   Failure: `tests/test_stay_fee_pay_steps_browser.py::test_pay_steps_fit_every_width_and_language`. It is a browser test; I did not open it, so the cause is unconfirmed (probably the same Chromium version mismatch).
3. `python3 scripts/context_lint.py`
   `context lint: OK` (next free migration now 0014)

## Section 7 acceptance

- [x] No env vars: POST answers "not available" (tested), no row stored.
- [x] No GET starts a send (GET returns 405, tested); browser only goes to ISDS hosts (`portal_url_ok` tested, foreign address refused).
- [x] Signed-in return lands on the Stay fee page with `msg` (tested); signed-out return unchanged (existing tests pass).
- [~] Tests and lint pass, except the two browser tests above.

## Deviations

- No commit and no PR: the owner said do not commit, and executor.md's per-step commit was not done. Brief 0241 is untracked in the tree; I did not touch it.
- Added a `"databox_sends"` line in `_cutoffs` in retention.py (copied from the alert step's pattern).
- Czech period label for the ISDS text comes from `stay_fee.period_label_cs(row["cadence"], month)`. `_ui_period_label` was dropped because it is host-language and used only for the audit line the brief marked optional.
- Test for "another host's filing" became "unknown filing id gives 404" (no second-host fixture in this file).
- The signed-in pending-row return test is in test_databox_send.py (it needs a real filing), not in test_databox_return.py. test_databox_return.py has the no-pending-row case.
- test_databox_send.py copies the fixture helpers instead of importing them, because importing test_stay_fee_send_panel.py pulls in Playwright and would skip the whole file.

## Questions

- None blocking. For the owner: the Playwright Chromium version in App/.venv does not match the installed browser, so the browser tests cannot run here.

## Owner steps left

1. Review the diff, then commit the files above on claude/project-thread-jf2b3v (not main).
2. Fix the browser install (`playwright install chromium` inside App/.venv, or match the 1194 browser to the expected 1243) and rerun `test_send_panel_geometry_and_screenshots` and `test_pay_steps_fit_every_width_and_language`.
3. Rerun the 0240 test set and report back; then the executor can finish with Status: review.

## Orchestrator review (2026-10-22)

Diff read. Ran the scoped set with the Playwright path workaround: 237 passed, 0 skipped (browser tests included). No changes needed.
