# 0203 report

Status: blocked
Done: steps 1 to 16 applied, one commit per step, in order. Left: the browser test fix below (outside brief §3) and the 390 px screenshots.

## Files changed (all in brief §3)
App/app/routes/passkeys.py, App/app/templates/base.html, App/app/templates/login.html, App/app/static/passkeys.js, App/app/routes/admin.py, App/app/routes/onboarding_wizard.py, App/app/templates/setup_wizard/door_lock.html, App/app/templates/setup_wizard/done.html, App/app/templates/setup_wizard/try_it.html, App/app/static/host.js, App/app/static/host2.css, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/tests/test_passkeys.py, App/tests/test_smart_locks_page.py, App/tests/static_versions.json (regenerated, 32 files).

## Commands (last lines)
- 6.1 `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_passkeys.py ... -rs`: `105 passed, 1 warning in 6.15s`. No skips. Both new tests included.
- 6.2 browser files, `-rs`: `12 failed, 75 passed, 1 warning in 530.97s`. 0 skipped. All 12 are `test_wizard_polish_and_overview_cards` (2 languages x 3 widths x 2 variants).
- 6.3 `test_host_i18n.py`: `3 failed, 11 passed`. The same 3 fail on base commit 2f043c8, checked in a temporary worktree (removed). Not caused by this brief.
- 6.3 `test_no_em_dashes.py test_copy_cleanup.py`: `13 passed`.

## Deviations
1. **Brief conflict (stopped).** Step 8b points the done button to `/`, as the brief says. `App/tests/test_onboarding_wizard_browser.py` line 1355 still waits for `**/apartments/*?view=overview**` after that button, so all 12 cases fail. That file is not in brief §3 ("No other file may change"), so I did not edit it. Needed: add that file to §3 and change the wait to the dashboard URL (`/`), then rerun §6.2.
2. **Screenshots not taken.** Hard rule 7 needs one 390 px screenshot per changed page (done, try_it, door_lock, base pop-up). Not done.
3. Pre-existing unstaged PNG changes under `docs/tasks/0102-evidence/` were in the tree before the run. Not committed.
4. Step 16 cache keys regenerated with `--write`.

## Questions
Should the one-line test change above be added to §3 and applied?

## Owner steps left
After the test fix merges, deploy as usual. The new cache keys ship with it.
