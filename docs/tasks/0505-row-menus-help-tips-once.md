# 0505: row menus and help tips in app.js bind once
Status: todo
Depends on: 0504 (merged) | Base commit: origin/main | Branch: task/0505-mixed-inits-b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Page swap groundwork, step 5. Running `window.UbyHost.initPage()` a second time must not add any listener in `initRowMenus` and `initHelpTips`, and their `document`/`window` listeners must keep working with menus and tips bound by any later call. No visible change, no behaviour change on a normal page load.

## 2. Context
- `claimNode(node, key)` near the top of `App/app/static/app.js` returns `true` the first time for a node and key, `false` after; it accepts `document` and `window`. `bindHostNodes(selector, fn)` already binds each element once.
- Find each function with `grep -nF "function NAME()" App/app/static/app.js`.
- The rule:
  - Per-element loop: first line of the callback becomes `if (!claimNode(el, "NAME")) return;` (`initRowMenus` already uses `bindHostNodes` for triggers: leave it).
  - Each block of `document.addEventListener(...)` / `window.addEventListener(...)` calls at the end of the function goes inside one `if (claimNode(document, "NAME")) { ... }`, same handlers.
  - State shared between per-element handlers and the document/window handlers must be shared by every call. Today it is a `var` inside the function, so a second call would make a second copy that the first call's document handlers never see.
- `initRowMenus`: `var lastOpenAt = 0;` moves out of the function to the enclosing scope, renamed `rowMenuLastOpenAt`, declared right above `function initRowMenus()`. Replace its two uses.
- `initHelpTips`: `var current = null;` and `var timer = null;` move out of the function to one object declared right above `function initHelpTips()`: `var helpTipState = { current: null, timer: null };`. Replace every use of `current` and `timer` inside the function with `helpTipState.current` / `helpTipState.timer`. Keep the early `if (!tips.length) return;` before the claim.

## 3. Files
Edit `App/app/static/app.js` (only these two functions and the two new declarations), `App/app/templates/base.html` (only the `app.js?v=` key, new value `20261101-0505`), `App/tests/static_versions.json` (only via `--write`). Create `App/tests/test_0505_row_menus_help_tips_once_browser.py`. Report `docs/tasks/0505-report.md`.

## 4. Steps
1. `initRowMenus`. `node --check App/app/static/app.js 2>&1 | tail -3`. Commit `0505 step 1`.
2. `initHelpTips`. `node --check`. Commit `0505 step 2`.
3. Test: copy the recorder and login setup from `App/tests/test_0504_mixed_inits_once_browser.py` (it records `window` too; add `document`). Pages: `/reservations?lang=cs` (has `.row-menu-trigger`; confirm with `grep -rl 'row-menu-trigger' App/app/templates`) and a page where `grep -rl 'data-help-tip' App/app/templates` shows a tip (use the workspace fixture's ids). Before the second `initPage()`, assert the selectors are present. After it, assert zero adds on `.row-menu-trigger`, `.row-menu-panel`, `[data-help-tip]`, `.help-tip-btn`, and zero adds on `document` and `window`.
   Behaviour after two `initPage()` calls: click the first `.row-menu-trigger`, its panel has class `is-open`; press Escape, no `.row-menu-panel.is-open` remains. Click the first `.help-tip-btn`; its tip shows open (use the same check the existing help tip browser test uses: `grep -rl 'help-tip' tests/*_browser.py`); press Escape; it is closed.
   Run with `-rs`. Commit `0505 step 3`.
4. Bump `app.js?v=` in `base.html` to `20261101-0505`; from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0505 step 4`.

## 5. Do not touch
Any other init function, other static files, templates beyond the version key, routes, Python under `App/app/`, copy, translations. No new dependency.

## 6. Commands (from `App/`, set `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0505_row_menus_help_tips_once_browser.py tests/test_0504_mixed_inits_once_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0502_page_inits_once_browser.py tests/test_0501_bind_once_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`, plus every file from `grep -rlE 'row-menu|help-tip' tests/*_browser.py` (list them in the report). Then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files and this brief.

## 8. Stop and ask
Stop if a function's shape does not fit the rule (other closure state shared with the document/window handlers than named above), or if a named test other than yours changes result.

## 9. Report
`docs/tasks/0505-report.md`: Status, test and lint tails, `git diff --stat origin/main`, page-to-selector table, deviations.
