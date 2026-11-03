# 0895: a wide window must never keep the sidebar inert

Status: done

## Problem
Josef (Chrome desktop, production, admin preview mode) got a page where every click did nothing until reload. DevTools showed exactly one inert element: `ASIDE#app-sidebar` while the window was wide. No console errors, no view transition.
`setDrawer()` in App/app/static/app.js (inside `initNavigation`, around line 745) sets `sidebar.inert = isCompact() && !open`. `isCompact()` is `window.innerWidth <= NAV_BREAKPOINT` (960). If the width is momentarily small when it runs (window animation, zoom, DevTools dock) and no later `resize` event corrects it, the rail stays inert on a wide window. Clicks on it, including Help and Dashboard, silently do nothing.

## Change (App/app/static/app.js only, inside `initNavigation`)
After the existing `if (claimNode(window, "initNavigation")) window.addEventListener("resize", ...)` line add a self-heal that runs on the events a stale state can survive:

```js
    // Self-heal: a rail left inert while the window is wide would swallow every click.
    function healInert() {
      var rail = document.getElementById("app-sidebar");
      var main = document.getElementById("main-content");
      if (isCompact() || document.body.classList.contains("nav-open")) return;
      if (rail && rail.inert) rail.inert = false;
      if (main && main.inert) main.inert = false;
    }
    if (claimNode(document, "initNavigationHeal")) {
      document.addEventListener("pointerdown", healInert, true);
      document.addEventListener("visibilitychange", healInert);
      window.addEventListener("focus", healInert);
      window.addEventListener("pageshow", healInert);
    }
```
Check `claimNode` accepts a second claim name on `document` (it takes (node, NAME)); if a listener-count test (test_0506 / test_0508 "listeners do not grow") counts document listeners per swap, they are added once because of claimNode, so they pass. Nothing else changes. Do not touch templates, CSS, sw.js or vendor files.

## Test
Add `App/tests/test_0895_sidebar_inert_heal_browser.py`, modelled on `App/tests/test_0508_page_swap_browser.py` (reuse its imports, `seed`, `new_context`, fixtures, sidebar selectors `#app-sidebar a[href="/guide"]` for Help and the Dashboard link). Chromium, 1280 px:
1. Open the dashboard, `page.evaluate("document.getElementById('app-sidebar').inert = true")`, then `page.mouse.click(640, 400)` (any spot in the main area). Assert `#app-sidebar` is no longer inert, then click Help in the sidebar and assert the URL becomes /guide and click Dashboard and assert the URL is back. Without the change the sidebar stays inert and the clicks do nothing.
2. A real compact window keeps its behaviour: viewport 800x900, sidebar is inert while the drawer is closed (`inert` true); a pointerdown in the main area leaves it inert.
0 skipped.

## Run
From App/ (a venv with playwright 1.63.0 already exists in App/.venv): `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0895_sidebar_inert_heal_browser.py tests/test_0508_page_swap_browser.py tests/test_0506_last_inits_once_browser.py -q --tb=short -x 2>&1 | tail -30`. Do not install anything. Revert rewritten PNGs under docs/tasks/ (`git checkout -- docs/tasks`).

## Report
Commit on the current branch, push, report: files changed, test output tail, and whether test 1 fails with the app.js change stashed.
