# 0502: nine per-page start-up functions in app.js bind once
Status: todo
Depends on: 0501 (claimNode, initPage) | Base commit: origin/main | Branch: task/0502-page-inits-bind-once-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Page swap groundwork, step 2 (owner chose Turbo, 2026-11-01). Running `window.UbyHost.initPage()` a second time on the same page must not set anything up twice in the nine functions below. No visible change, no behaviour change on a normal page load.

## 2. Context
- 0501 added `claimNode(node, key)` near the top of `App/app/static/app.js`: it returns `true` the first time for a node and key, `false` after. It stores a JS property, never a `data-` attribute (Turbo clones the page; a cloned attribute would block binding on the restored copy).
- Functions (find each with `grep -nF "function NAME()" App/app/static/app.js`): `initBirthDateInputs`, `initTogglePanels`, `initNotifications`, `initAutomationFields`, `initInlineTiming`, `initControllerFields`, `initFeeTemplateCopy`, `initCsvExport`, `initHousebookPdfExport`.
- The rule, the same in every function:
  - Per-element loop (`querySelectorAll(...).forEach(function (el) {`): first line of the callback becomes `if (!claimNode(el, "NAME")) return;`.
  - Single element by id or selector (`var dialog = document.getElementById(...)`, after its existing null check): add `if (!claimNode(dialog, "NAME")) return;` before the first `addEventListener` or other setup. Use the element the function's setup hangs on (the dialog, the form or the button), one claim per function.
  - One-time page actions that are not listeners (for example `initTogglePanels` opening a panel for `?new=1`) sit after the claim, so they also run once per element.
  - `NAME` is the function name. Change nothing else inside the functions.
- `initCsvExport` and `initHousebookPdfExport` also bind triggers outside the dialog: claim each trigger in its own loop, key `NAME`.

## 3. Files
Edit `App/app/static/app.js`, `App/app/templates/base.html` (only the `app.js?v=` key, new value `20261101-0502`), `App/tests/static_versions.json` (only via `--write`). Create `App/tests/test_0502_page_inits_once_browser.py`. Report `docs/tasks/0502-report.md`.

## 4. Steps
1. Apply the rule to the first five functions. `node --check App/app/static/app.js 2>&1 | tail -3`. Commit `0502 step 1`.
2. Apply the rule to the last four. `node --check` again. Commit `0502 step 2`.
3. Test: copy `App/tests/test_0501_bind_once_browser.py` (its recorder and login setup). For each page in a list, open it, install the recorder, call `window.UbyHost.initPage()`, and assert zero listeners added on elements matching these selectors: `[data-birth-date]`, `.action-panel`, `#add-stay-panel`, `form[data-notification-dismiss]`, `[data-automation-mode]`, `form[data-inline-timing]`, `[data-controller-same-toggle]`, `#fee-copy-apply`, `#csv-export-dialog`, `[data-csv-export]`, `#housebook-pdf-dialog`. Pages: `/reservations?lang=cs` plus the pages where `grep -rlE 'data-inline-timing|data-automation-mode|fee-copy-apply|data-controller-same-toggle|housebook-pdf-dialog' App/app/templates` shows these elements live (the property detail page and the stay-fee settings page are likely; at most four pages; use the workspace fixture's first property id). Before the second run, also assert each selector you claim a page covers is present on it, so the test is not empty. Run with `-rs`. Commit `0502 step 3`.
4. Bump `app.js?v=` in `base.html` to `20261101-0502`; from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0502 step 4`.

## 5. Do not touch
Any other init function, other static files, templates beyond the version key, routes, Python under `App/app/`, copy, translations. No new dependency.

## 6. Commands (from `App/`, set `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0502_page_inits_once_browser.py tests/test_0501_bind_once_browser.py tests/test_dashboard_rows_browser.py tests/test_0399_open_buttons_click_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files. Report lists which page covers which selector.

## 8. Stop and ask
Stop if a function's shape does not fit the rule (for example setup that must re-run on every call), or if a named test other than yours changes result.

## 9. Report
`docs/tasks/0502-report.md`: Status, test and lint tails, `git diff --stat origin/main`, page-to-selector table, deviations.
