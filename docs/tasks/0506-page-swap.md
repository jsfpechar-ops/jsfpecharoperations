# 0506-0508: fast page swap (one PR)
Status: in-progress | Base: origin/main | Branch: task/0506-page-swap (worktree /tmp/wt0506) | Executor: Haiku 5.5, one part per session (30 tool calls each)

## 1. Objective
Host pages switch without a full reload (Hotwire Turbo Drive, owner decision #614 in docs/context/decisions.md). The look stays the same; only speed changes. Three parts, run in order, each committed on this branch. Read only this file, docs/context/executor.md and the files named here.

## 2. Context
Shared rules (from 0501-0505):
- `claimNode(node, key)` (top of `App/app/static/app.js`) is true the first time per node and key; it accepts `document` and `window`.
- Per element: `if (!claimNode(el, "NAME")) return;`. Document/window listeners: inside one `if (claimNode(document|window, "NAME")) { ... }`.
- A document/window handler finds its elements at event time (`document.querySelector...`, `event.target.closest(...)`), never through a variable captured when the page started: after a swap those elements are gone.
- State that both kinds of handler share lives outside the function (see `helpTipState` above `initHelpTips`).
- Tests copy the recorder and login setup from `App/tests/test_0505_row_menus_help_tips_once_browser.py`.
- Never commit the PNGs that browser tests rewrite under docs/tasks/: `git checkout -- docs/tasks/'*.png'` before each commit.
- Test runs: from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest <files> -q --tb=short -x -rs 2>&1 | tail -30`. Chromium only locally; CI runs WebKit (Safari).

## 4. Steps
### Part A (0506): last app.js start-up functions bind once
Functions: `initFilterPanels`, `initDateRanges`, `initMonthPickers`, `initNavigation`, `initPowerTools` (find with `grep -nF "function NAME(" App/app/static/app.js`).
1. `initFilterPanels`: claim each form. `initDateRanges`/`initMonthPickers`: claim each range/picker; replace their per-range `document` pointerdown/keydown listeners with one claimed pair per function that, at event time, closes every open popover/panel the event is outside of (same `close(true)` behaviour; keep the close function reachable, for example by storing it on the element as `el._ubyClose`).
2. `initNavigation`: claim each button/element; the `document`/`window`/`matchMedia` listeners go inside one claim and look up `#app-sidebar`, `#main-content` and buttons at event time. Keep `railWasCollapsed`, `animateTimer` and similar state outside the function.
3. `initPowerTools`: same rule; the command dialog (`#command-dialog`) and its list are looked up at event time inside document handlers.
4. Test `App/tests/test_0506_last_inits_once_browser.py`: on `/reservations?lang=cs` (filter panel + date range) and `/?lang=cs`, two `initPage()` calls add zero listeners on any element and on document/window; then behaviour: open the date range popover, press Escape, it is hidden; open the sidebar drawer at 390 px (`[data-nav-toggle]`), Escape closes it; Ctrl+K (or the open button) opens `#command-dialog`, Escape closes it.
5. Run part A test plus `test_0501`..`test_0505`, `test_design_shell_browser.py`, `test_0705_v2_shell_browser.py`. Commit `0506 part A`.
Stop and ask if a function shares other closure state with its document handlers than you can hoist simply.

### Part B (0507): other host scripts run per page
1. In `app.js` add next to `initPage`: `var pageHooks = [];` and `window.UbyHost.onPage = function (fn) { pageHooks.push(fn); if (pageStarted) fn(); };` where `initPage` sets `pageStarted = true` and then calls every hook. Scripts load before or after app.js, so `onPage` must also work when called after the first `initPage`.
2. `host.js`, `pwa.js`, `havel.js`, `passkeys.js`: the parts that bind page elements (examples: host.js `[data-host-signature]` blocks and `[data-host-alerts]`; pwa.js `[data-push-row]`, `[data-pwa-install-row]`; havel.js `[data-havel-panel]`/`[data-havel-page]`; passkeys.js its DOMContentLoaded body) move into a function registered with `window.UbyHost.onPage(fn)`, each element claimed. Their delegated `document`/`window` listeners stay where they are (they run once) but must find elements at event time. If a script can load on a page without app.js (check `grep -rn 'SCRIPT.js' App/app/templates`), call the function directly when `window.UbyHost.onPage` is missing.
3. `cleaning.js` and `dashboard-calendar.js` sit in the page body and Turbo runs body scripts again on each visit. Their element binding may run again; guard each `document`/`window` listener with `claimNode`-style `window._uby...` flags (they cannot see app.js's `claimNode`; use `if (!window._ubyCleaningBound) { window._ubyCleaningBound = true; ... }`) and look elements up at event time.
4. `shell.js`, `skeleton.js`, `csrf.js` only use delegated listeners: check each handler finds elements at event time; change nothing else.
5. Test `App/tests/test_0507_page_hooks_browser.py`: on `/?lang=cs` and the cleaning page, two `initPage()` calls add zero listeners; the calendar and cleaning list still render; on the settings page the push row is still bound (one click handler path works as today).
6. Run part B test, part A test, and every `*_browser.py` that `grep -rlE 'havel|push|signature|cleaning|dashboard-calendar|passkey' App/tests/*_browser.py` lists. Commit `0507 part B`.

### Part C (0508): turn on the page swap
1. Copy `/tmp/turbo-8.0.13.js` (Turbo 8.0.13 UMD, MIT, header kept) to `App/app/static/vendor/turbo-8.0.13.js`.
2. `App/app/templates/base.html` (host pages only; guest, auth and public templates stay as they are):
   - In `<head>`: `<script src="/static/vendor/turbo-8.0.13.js" defer data-turbo-track="reload"></script>`, then move the shared scripts now at the end of the body (csrf, skeleton, app, host, pwa, passkeys, shell, havel, with their `{% if %}`) into `<head>`, each `defer data-turbo-track="reload"`, same order. Add `<meta name="turbo-cache-control" content="no-cache">` (no stale private pages on Back) and `<meta name="turbo-prefetch" content="true">`.
   - Remove the `<script type="speculationrules">` block (Turbo prefetches on hover instead); copy its exclusions as `data-turbo="false"` (step 3). Update the prefetch tests to check Turbo instead.
   - In `app.js` replace `document.addEventListener("DOMContentLoaded", initPage);` with `document.addEventListener("turbo:load", initPage);` plus a fallback `if (!window.Turbo) document.addEventListener("DOMContentLoaded", initPage);`.
   - Forms stay full page loads: in app.js top level `if (window.Turbo) Turbo.config.forms.mode = "off";` (run it on `turbo:load` once if Turbo loads after app.js).
   - Hide Turbo's own progress bar so the look does not change: in `App/app/static/host2.css` `.turbo-progress-bar { display: none; }`. skeleton.js keeps showing the page skeleton on click; make it hide on `turbo:load` as it does on `pageshow`.
3. `data-turbo="false"` on links that must stay full loads: logout, `/lang`, `/api/`, `/admin/`, exports, PDF, ZIP, `[download]`, `target=_blank`. Find them with `grep -rnE 'href="[^"]*(logout|/lang|export|\.pdf|/pdf|\.zip)' App/app/templates | head -40`.
4. Version keys: bump every changed static file's `?v=` and run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
5. Test `App/tests/test_0508_page_swap_browser.py` (Chromium locally, CI adds WebKit):
   - Log in, open `/?lang=cs`, set `window.__swapMarker = 1`, click the sidebar link to stays (`/reservations`), wait for URL; `window.__swapMarker` is still 1 (no full reload), `#main-content` shows the stays heading, the active sidebar item changed.
   - After the swap: row menu opens/closes, help tip opens, command dialog opens with Ctrl+K; Back returns to dashboard without full reload and the calendar renders.
   - A form submit (any filter form) still does a full load (marker gone).
   - Logout link is a full load and afterwards Back does not show the dashboard content.
   - Listener count after 5 swaps between dashboard and stays: `document` and `window` listener adds after the first page are zero.
6. Run: part C test, part A and B tests, `test_0501`..`test_0505`, `test_design_shell_browser.py`, `test_0705_v2_shell_browser.py`, `test_download_skeleton_browser.py`, `test_havel_launcher_skeleton_browser.py`, the prefetch tests, `test_static_versions.py`, then from repo root `python3 scripts/context_lint.py 2>&1 | tail -10`. Commit `0508 part C`.

## 3. Files
App/app/static/{app,host,pwa,havel,passkeys,cleaning,dashboard-calendar,skeleton}.js, host2.css, vendor/turbo-8.0.13.js, templates/base.html and host templates (version keys, data-turbo), tests named in the steps.

## 6. Commands
See each part, step "Run".

## 7. Acceptance
All named tests pass, 0 skipped; CI green including WebKit.

## 8. Stop and ask
Stop when a script does not fit the shared rules, or a named test other than yours changes result.

## 5. Do not touch
Guest pages, auth/public templates, routes, Python under App/app/, copy, translations, Stripe/payment scripts. No dependency beyond the vendored Turbo file (decision #614).

## 9. Report
Append to `docs/tasks/0506-report.md` per part: Status, test tails, `git diff --stat origin/main | tail -40`, deviations, anything you stopped on.
