# 0503: eight more per-page start-up functions in app.js bind once
Status: todo
Depends on: 0502 (merged) | Base commit: origin/main | Branch: task/0503-page-inits-bind-once-b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Page swap groundwork, step 3 (owner chose Turbo, 2026-11-01). Running `window.UbyHost.initPage()` a second time on the same page must not set anything up twice in the eight functions below. No visible change, no behaviour change on a normal page load.

## 2. Context
- 0501 added `claimNode(node, key)` near the top of `App/app/static/app.js`: it returns `true` the first time for a node and key, `false` after. It stores a JS property, never a `data-` attribute (Turbo clones the page; a cloned attribute would block binding on the restored copy).
- Functions (find each with `grep -nF "function NAME()" App/app/static/app.js`): `initUnsavedDialog`, `initAutoFilters`, `initGeneratedPasswords`, `initResetPasswordDialog`, `initConfirmDialog`, `initSavedViews`, `initInlineEdit`, `initToasts`.
- The rule, the same in every function:
  - Per-element loop (`querySelectorAll(...).forEach(function (el) {`): first line of the callback becomes `if (!claimNode(el, "NAME")) return;`.
  - Single element by id or selector (`var dialog = document.getElementById(...)`, after its existing null check): add `if (!claimNode(dialog, "NAME")) return;` before the first `addEventListener` or other setup. Use the element the function's setup hangs on (the dialog, the form or the button), one claim per function.
  - One-time page actions that are not listeners sit after the claim, so they also run once per element.
  - `NAME` is the function name. Change nothing else inside the functions.
- `initConfirmDialog` already uses `bindHostNodes` for `form[data-confirm]` and `button[data-confirm]`: leave those calls as they are, claim only its direct bindings. `initToasts` already guards two bindings with `_copyRecoveryBound` and `_feedbackVisibilityBound`: leave those, claim each toast or rail it sets up. `initUnsavedDialog` binds per form and on `#unsaved-dialog`: claim each.

## 3. Files
Edit `App/app/static/app.js`, `App/app/templates/base.html` (only the `app.js?v=` key, new value `20261101-0503`), `App/tests/static_versions.json` (only via `--write`). Create `App/tests/test_0503_page_inits_once_browser.py`. Report `docs/tasks/0503-report.md`.

## 4. Steps
1. Apply the rule to the first four functions. `node --check App/app/static/app.js 2>&1 | tail -3`. Commit `0503 step 1`.
2. Apply the rule to the last four. `node --check` again. Commit `0503 step 2`.
3. Test: copy `App/tests/test_0501_bind_once_browser.py` (its recorder and login setup). For each page in a list, open it, install the recorder, call `window.UbyHost.initPage()`, and assert zero listeners added on elements matching these selectors: `#unsaved-dialog`, `form[data-unsaved]` (check the real form selector in `initUnsavedDialog`), `form[data-auto-submit]`, `[data-generate-password]`, `#reset-password-dialog`, `#confirm-dialog`, `[data-saved-views]`, `[data-save-view]`, `form[data-inline-edit]`, `[data-feedback-rail]`, `[data-toast]`. Pages: `/reservations?lang=cs` plus the pages where `grep -rlE 'data-inline-edit|data-saved-views|reset-password-dialog|data-generate-password|unsaved-dialog' App/app/templates` shows these elements live (at most four pages; use the workspace fixture's first property id). Before the second run, also assert each selector you claim a page covers is present on it, so the test is not empty. Run with `-rs`. Commit `0503 step 3`.
4. Bump `app.js?v=` in `base.html` to `20261101-0503`; from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0503 step 4`.

## 5. Do not touch
Any other init function, other static files, templates beyond the version key, routes, Python under `App/app/`, copy, translations. No new dependency.

## 6. Commands (from `App/`, set `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0503_page_inits_once_browser.py tests/test_0502_page_inits_once_browser.py tests/test_0501_bind_once_browser.py tests/test_dashboard_rows_browser.py tests/test_0282_signature_dialog_browser.py tests/test_0284_states_browser.py tests/test_0399_open_buttons_click_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files. Report lists which page covers which selector.

## 8. Stop and ask
Stop if a function's shape does not fit the rule (for example setup that must re-run on every call), or if a named test other than yours changes result.

## 9. Report
`docs/tasks/0503-report.md`: Status, test and lint tails, `git diff --stat origin/main`, page-to-selector table, deviations.
