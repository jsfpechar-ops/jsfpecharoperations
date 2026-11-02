# 0504: three mixed start-up functions in app.js bind once
Status: todo
Depends on: 0503 (merged) | Base commit: origin/main | Branch: task/0504-mixed-inits-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Page swap groundwork, step 4. Running `window.UbyHost.initPage()` a second time must not add any listener in `initUnsavedForms`, `initSubmitGuard` and `initDetailsLinks`, and their window listeners must keep working for the page that is on screen. No visible change, no behaviour change on a normal page load.

## 2. Context
- `claimNode(node, key)` near the top of `App/app/static/app.js` returns `true` the first time for a node and key, `false` after. It stores a JS property, never a `data-` attribute. It accepts `window` and `document` too.
- These three functions mix per-element listeners with one `window` listener. Find each with `grep -nF "function NAME()" App/app/static/app.js`.
- The rule:
  - Per-element loop: first line of the callback becomes `if (!claimNode(el, "NAME")) return;`.
  - The `window.addEventListener(...)` call becomes `if (claimNode(window, "NAME")) window.addEventListener(...)`, same handler.
  - A window handler must read the page at event time, never a list or variable captured by the first call (after a page swap the first call's elements are gone).
- `initUnsavedForms`: the `beforeunload` handler today reads the captured `forms` array and the closure variable `submitting`. Change to: the submit listener sets `form._ubySubmitting = true` (JS property, no attribute); the `beforeunload` handler reads `document.querySelectorAll("form[data-unsaved-guard]")` at event time, treats a form as unsaved when `data-dirty` is `"1"` and `_ubySubmitting` is not true, then clears `_ubySubmitting` on every one of those forms (this replaces `submitting = null`). Keep the early `if (!forms.length) return;` before the window claim, so pages without a guarded form still get no `beforeunload` listener.
- `initSubmitGuard`: its `pageshow` handler already queries the page at event time; only claim.
- `initDetailsLinks`: its `hashchange` handler calls `openTarget`, which already looks the target up at event time; only claim. The last line `openTarget(window.location.hash);` stays unguarded: it is a page action and must run for each new page.

## 3. Files
Edit `App/app/static/app.js` (only the three functions), `App/app/templates/base.html` (only the `app.js?v=` key, new value `20261101-0504`), `App/tests/static_versions.json` (only via `--write`), `App/tests/test_0503_page_inits_once_browser.py` (only the `form[data-unsaved-guard]` expectation, see step 3). Create `App/tests/test_0504_mixed_inits_once_browser.py`. Report `docs/tasks/0504-report.md`.

## 4. Steps
1. Apply the rule to `initSubmitGuard` and `initDetailsLinks`. `node --check App/app/static/app.js 2>&1 | tail -3`. Commit `0504 step 1`.
2. Apply the rule and the `beforeunload` change to `initUnsavedForms`. `node --check`. Commit `0504 step 2`.
3. Tests.
   - New file: copy the recorder and login setup from `App/tests/test_0503_page_inits_once_browser.py`, and record listeners on `window` as well as elements. Pages: `/reservations?lang=cs` (has `.action-panel form`), `/apartments/{property_id}?lang=cs` (has `form[data-unsaved-guard]`), and a page where `grep -rl 'data-open-details' App/app/templates` shows `[data-open-details]` (at most one more page). Before the second `initPage()`, assert each covered selector is present. After it, assert zero adds on `.action-panel form`, `[data-open-details]`, and zero `beforeunload`, `pageshow`, `hashchange` adds on `window`. Exception: on `form[data-unsaved-guard]` expect exactly one `invalid` per form (from `initPropertyViews`, which brief 0505 fixes); add the comment "initPropertyViews still re-binds; brief 0505 makes this zero."
   - Behaviour, on `/apartments/{property_id}?lang=cs` after two `initPage()` calls: type into a field of the first `form[data-unsaved-guard]`; then `evaluate` `(() => { const e = new Event("beforeunload", {cancelable: true}); window.dispatchEvent(e); return e.defaultPrevented; })()` must be `true`. Then set `_ubySubmitting = true` on that form via `evaluate` and dispatch again: must be `false`. Dispatch a third time: must be `true` again (the flag was cleared).
   - In `test_0503_page_inits_once_browser.py`, change only the `form[data-unsaved-guard]` expectation from `["change", "input", "invalid", "submit"]` per form to `["invalid"]` per form, and update its comment to name only `initPropertyViews` and brief 0505.
   - Run with `-rs`. Commit `0504 step 3`.
4. Bump `app.js?v=` in `base.html` to `20261101-0504`; from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0504 step 4`.

## 5. Do not touch
Any other init function (including `initPropertyViews`, `initUnsavedDialog`), other static files, templates beyond the version key, routes, Python under `App/app/`, copy, translations. No new dependency.

## 6. Commands (from `App/`, set `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0504_mixed_inits_once_browser.py tests/test_0503_page_inits_once_browser.py tests/test_0502_page_inits_once_browser.py tests/test_0501_bind_once_browser.py tests/test_0284_states_browser.py tests/test_0399_open_buttons_click_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`, plus every file from `grep -rlE 'unsaved|submit-guard|data-open-details|beforeunload' tests/*_browser.py` (list them in the report). Then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files and this brief.

## 8. Stop and ask
Stop if a function's shape does not fit the rule, or if a named test other than the two you edit changes result.

## 9. Report
`docs/tasks/0504-report.md`: Status, test and lint tails, `git diff --stat origin/main`, page-to-selector table, deviations.
