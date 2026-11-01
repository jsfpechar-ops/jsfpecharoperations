# 0501: app.js shared binder binds each element once, start-up callable twice
Status: todo
Depends on: 0500 (merged) | Base commit: origin/main | Branch: task/0501-host-bind-once
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Groundwork for the page swap the owner chose (Turbo, decisions.md 2026-11-01). After a swap, app.js start-up must be able to run again without binding any handler twice. This first step fixes the shared binder `bindHostNodes` and names the start-up as `window.UbyHost.initPage`. No visible change, no behaviour change on a normal page load.

## 2. Context
- `App/app/static/app.js:10` `bindHostNodes(selector, attach)` creates a new `WeakSet` on every call and adds a new `document` listener for `ubyhost:content-updated` on every call. Calling it twice double-binds every matched element. Callers: `initCopy`, `initRowMenus`, `initClickableRows`, `initDismissBanners`, `initConfirmDialog` (two calls). `dashboard-calendar.js:807` dispatches the event; do not touch that file.
- Start-up is the `DOMContentLoaded` handler at the end of app.js (anchor `document.addEventListener("DOMContentLoaded", function () {`) calling 29 `init*` functions.
- Marker must be a JS-side record (WeakMap or a property on the node), never a `data-` attribute: Turbo clones the page for its cache, and a cloned attribute would block binding on the restored copy.
- Other inits still double-bind after this task. That is expected; 0502-0505 fix them. The test in step 3 therefore only checks the binder's elements and the content-updated listener.

## 3. Files
Edit `App/app/static/app.js`, `App/app/templates/base.html` (only the `app.js?v=` key, new value `20261101-0501`), `App/tests/static_versions.json` (only via the `--write` command in step 4). Create `App/tests/test_0501_bind_once_browser.py`. Report: `docs/tasks/0501-report.md`.

## 4. Steps
1. In `app.js`, replace the body of `bindHostNodes` with a module-level registry:
   ```js
  var hostBindings = {};
  function claimNode(node, key) {
    var keys = node._ubyBound || (node._ubyBound = {});
    if (keys[key]) return false;
    keys[key] = true;
    return true;
  }
  function visitBinding(root, selector) {
    if (!root || !root.querySelectorAll) return;
    var attach = hostBindings[selector];
    if (root.matches && root.matches(selector) && claimNode(root, selector)) attach(root);
    root.querySelectorAll(selector).forEach(function (node) {
      if (claimNode(node, selector)) attach(node);
    });
  }
  function bindHostNodes(selector, attach) {
    hostBindings[selector] = attach;
    visitBinding(document, selector);
  }
  document.addEventListener("ubyhost:content-updated", function (event) {
    var root = event.detail && event.detail.root;
    if (!root || !root.isConnected) return;
    Object.keys(hostBindings).forEach(function (selector) { visitBinding(root, selector); });
  });
   ```
   The latest `attach` for a selector wins (it may close over the current page's dialog). Commit `0501 step 1`.
2. Replace the `DOMContentLoaded` handler: move its 29 calls, unchanged and in the same order, into `function initPage() { ... }`; then add `window.UbyHost = window.UbyHost || {}; window.UbyHost.initPage = initPage;` and `document.addEventListener("DOMContentLoaded", initPage);`. Commit `0501 step 2`.
3. Test `test_0501_bind_once_browser.py`. Copy the module header, imports and fixtures (`calendar_origin`, `calendar_workspace`, `launch`, `make_stay`) from `App/tests/test_dashboard_rows_browser.py` lines 1-30 and its first test's setup (read only the lines you need). Open `/reservations?lang=cs` as the signed-in host with at least two stays so rows exist. Then in the page:
   - Install a counter before the second start-up: wrap `EventTarget.prototype.addEventListener` so it records `(target is document or window ? that name : element.matches(sel) for sel in ["[data-copy]", "tr[data-href]", ".clickable-row[data-href]", ".row-menu-trigger", "[data-dismiss-banner]", "form[data-confirm]", "button[data-confirm]"]), type`.
   - Call `window.UbyHost.initPage()`.
   - Assert: zero recorded calls on any element matching those selectors, and zero `ubyhost:content-updated` listeners added on `document`.
   - Assert clicking a stay row still navigates to its `data-href` (one navigation).
   Run with `-rs`, 0 skipped. Commit `0501 step 3`.
4. In `base.html` change `app.js?v=20261025-0377` to `app.js?v=20261101-0501`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0501 step 4`.

## 5. Do not touch
Any other init function, other static files, other templates, routes, Python under `App/app/`, copy, translations. No new dependency.

## 6. Commands (from `App/`)
`.venv/bin/python -m pytest tests/test_0501_bind_once_browser.py tests/test_dashboard_rows_browser.py tests/test_0285_rows_browser.py tests/test_0399_open_buttons_click_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`
Browser tests need `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` if Chromium is not found. Then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All named tests pass, 0 skipped. `git diff --stat origin/main` lists only the files in section 3. No screenshots (no visual change).

## 8. Stop and ask
Stop if `bindHostNodes` is defined differently from section 2, if any caller passes the same selector twice with different intent, or if a named test other than yours changes result.

## 9. Report
`docs/tasks/0501-report.md`: Status, test and lint tails, `git diff --stat origin/main`, deviations.
