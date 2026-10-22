# 0251: Tablet menu opens fully; Back after login does not look like a logout

Status: todo
Depends on: 0250 | Base commit: tip of claude/project-thread-cjz5cc after 0250 | Branch: claude/project-thread-cjz5cc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Between 1024 and 1279 px wide (iPad landscape, iPad Pro portrait) the menu is forced into the narrow icon rail, so its toggle button does nothing visible. There the toggle must open the full menu over the page and close it again. Also: after logging in with an e-mailed link, pressing Back lands on the spent link, which says "link expired" and looks like a logout; a signed-in host must be sent to the app instead.

## 2. Context

`App/app/static/host2.css` lines ~292-303:

```
@media (max-width: 1279px) and (min-width: 1024px) {
  .host-workspace .ui-sidebar { width: var(--nav-w-collapsed); padding: var(--space-3) var(--space-2); }
  .host-workspace .wrap.with-sidebar { margin-left: var(--nav-w-collapsed); }
  .host-workspace .ui-table th, .host-workspace .ui-table td { padding-left: var(--space-3); padding-right: var(--space-3); }
  .host-workspace .ui-sidebar :is(.brand-word, .ui-env, .ui-search-row span, .ui-search-row kbd, .ui-nav a > span:not(.ui-nav-count), .host-account-name) { display: none; }
  .host-workspace .ui-sidebar .ui-nav a, .host-workspace .ui-sidebar .ui-search-row { justify-content: center; padding: 0; }
  .host-workspace .ui-brand { flex-direction: column; height: auto; gap: var(--space-2); }
  .host-workspace .ui-sidebar .host-account-menu { ... }
  @supports (anchor-name: --host-acct) { ... }
}
```

`App/app/static/app.js` `initNavigation()` (~line 785): `setCollapsed(collapsed)` toggles `body.sidebar-collapsed` and stores it in localStorage; the `[data-sidebar-collapse]` button calls `setCollapsed(!...)`, the `[data-sidebar-expand]` button calls `setCollapsed(false)`. In the 1024-1279 range these classes change nothing because the media query above wins.

Design: in that range the rail stays the default and the content keeps its rail margin. The toggle adds `body.sidebar-expanded`, which shows the full-width menu on top of the page (overlay with a shadow). It closes on the toggle, Escape, a tap outside the menu, or when the window leaves the range. It is never stored. While expanded, `sidebar-collapsed` is removed and put back on close, so the generic collapsed rules do not fight the overlay.

`App/app/routes/admin_accounts.py` line ~190:

```
@router.get("/login/link")
def login_link_form(request: Request):
    """Show a "Log in" button. Opening the link spends nothing (mail scanners)."""
    token = request.query_params.get("t", "")
    row = login_link.peek(token)
    if not row or not login_link.account_for(row):
        return _link_page(request, {"expired": True}, status_code=410)
    return _link_page(request, {"token": token, "invite": row["purpose"] == login_link.INVITE})
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | tablet rail only when not expanded; overlay when expanded |
| App/app/static/app.js | edit | tablet toggle logic |
| App/app/templates/base.html (and any template referencing these two files with `?v=`) | edit | new keys |
| App/tests/static_versions.json | regenerate | `--write` |
| App/app/routes/admin_accounts.py | edit | signed-in host on a spent/own link goes to `/` |
| App/tests/test_0251_back_after_login.py | create | route test |
| App/tests/test_0251_tablet_browser.py | create | iPad touch browser test |

No other file may change.

## 4. Steps

### Step 1: CSS (`host2.css`)

Inside that media block, prefix every rule except the `.wrap.with-sidebar` and `.ui-table` lines with `body.host-workspace:not(.sidebar-expanded)` instead of `.host-workspace` (for the `.ui-brand` line too, and for both host-account-menu lines including the one inside `@supports`). Then add at the end of the media block, before its closing `}`:

```
  /* 0251: the toggle opens the full menu over the page on tablets. */
  body.host-workspace.sidebar-expanded .ui-sidebar { width: var(--nav-w); box-shadow: var(--shadow-popover); }
```

Commit `0251 step 1`.

### Step 2: JS (`app.js`, inside `initNavigation`)

After the `setCollapsed` function add:

```
    // 0251: 1024-1279 px always shows the rail (host2.css); there the button
    // opens the full menu over the page instead, never stored.
    var tabletRail = window.matchMedia("(min-width: 1024px) and (max-width: 1279px)");
    var railWasCollapsed = false;
    function syncRailButton() {
      if (!collapse || !tabletRail.matches) return;
      var open = document.body.classList.contains("sidebar-expanded");
      collapse.setAttribute("aria-expanded", open ? "true" : "false");
      collapse.setAttribute("aria-label", open ? collapse.dataset.labelHide : collapse.dataset.labelShow);
    }
    function setExpanded(open) {
      var body = document.body;
      if (open === body.classList.contains("sidebar-expanded")) return;
      if (open) {
        railWasCollapsed = body.classList.contains("sidebar-collapsed");
        body.classList.remove("sidebar-collapsed");
      } else if (railWasCollapsed) {
        body.classList.add("sidebar-collapsed");
      }
      body.classList.toggle("sidebar-expanded", open);
      syncRailButton();
      if (!open && collapse && collapse.dataset.labelShow) {
        // setCollapsed() owns the label outside the tablet range.
        if (!tabletRail.matches) setCollapsed(body.classList.contains("sidebar-collapsed"));
      }
    }
```

Change the two existing listener lines to:

```
    if (collapse) collapse.addEventListener("click", function () {
      if (tabletRail.matches) { setExpanded(!document.body.classList.contains("sidebar-expanded")); return; }
      setCollapsed(!document.body.classList.contains("sidebar-collapsed"));
    });
    if (expand) expand.addEventListener("click", function () {
      if (tabletRail.matches) { setExpanded(true); return; }
      setCollapsed(false);
    });
    document.addEventListener("pointerdown", function (event) {
      if (document.body.classList.contains("sidebar-expanded") && sidebar && !sidebar.contains(event.target)) setExpanded(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && document.body.classList.contains("sidebar-expanded")) setExpanded(false);
    });
    var onRailChange = function () { setExpanded(false); syncRailButton(); if (!tabletRail.matches) setCollapsed(document.body.classList.contains("sidebar-collapsed")); };
    if (tabletRail.addEventListener) tabletRail.addEventListener("change", onRailChange);
    syncRailButton();
```

Bump the `?v=` keys of `app.js` and `host2.css` everywhere they are referenced (`grep -rn "app.js?v=\|host2.css?v=" App/app/templates`) to `20261022-0251`, then `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` from `App/`. Commit `0251 step 2`.

### Step 3: Back after login (`admin_accounts.py`)

Replace the body of `login_link_form` with:

```
    token = request.query_params.get("t", "")
    row = login_link.peek(token)
    account = login_link.account_for(row) if row else None
    current = auth.current_user(request)
    # Back from the first page after logging in returns to this link, which
    # is spent by then. A signed-in host goes to the app, not "link expired".
    # A valid link for another account still shows its button.
    if current and (not account or account["id"] == current["id"]):
        return RedirectResponse("/", status_code=303)
    if not row or not account:
        return _link_page(request, {"expired": True}, status_code=410)
    return _link_page(request, {"token": token, "invite": row["purpose"] == login_link.INVITE})
```

Create `App/tests/test_0251_back_after_login.py`: reuse the `account` fixture and helpers from `tests/test_login_link_environments.py` if importable, otherwise create an account with `auth.create_account(...)` and log in with `tests.conftest.login_as`. Tests: (1) a logged-in client GETting `/login/link?t=bogus` with `follow_redirects=False` gets 303 to `/`; (2) a logged-out client gets 410 for the same URL. Commit `0251 step 3`.

### Step 4: tablet browser test `App/tests/test_0251_tablet_browser.py`

Import `host, base, _context, sync_api, chromium_launch_kwargs` from `tests.test_property_navigation_browser` (`# noqa: F401`). One test, for each viewport `(1180, 820)` and `(1024, 1366)` and `(820, 1180)`, a context with `has_touch=True, is_mobile=True` and the iPad user agent `Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1`:

1. Open `/apartments/{id}?view=overview&lang=en`. For every `.host-property-card`, `document.elementFromPoint` at its centre, at (left+8, top+8) and at its Open pill centre resolves inside an `a` (card link or `.host-property-card-link`) or, for the guest card's Copy button, inside `.host-property-card-actions`. No horizontal scroll (`scrollWidth <= clientWidth`).
2. `tap()` the Guest links card at (left+8, top+8 relative to the card, via `position=`): the settings view with section `guests` becomes visible (reuse `_STATE_JS` from the navigation test). Go back to the overview, `tap()` the Police reporting card: section `reporting` visible.
3. Only for widths 1024-1279: `tap()` `button[data-sidebar-collapse]`; the `#app-sidebar` width is ≥ 200 px and a `.ui-nav a > span` label is visible; tap it again: width < 100 px. Then tap it, tap the page at (900, 600): closed again.
4. If env `UBYHOST_SHOTS_DIR` is set, save a screenshot per viewport (overview, and menu open) there.

Commit `0251 step 4`.

## 5. Do not touch

Everything else; phone (<1024 px) and desktop (≥1280 px) sidebar behaviour must not change. AGENTS.md hard rules 3, 6, 7, 8.

## 6. Commands

From `App/`, with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`:

```
.venv/bin/python -m pytest tests/test_0251_back_after_login.py tests/test_login_link_environments.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_0251_tablet_browser.py tests/test_property_navigation_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_wide_geometry_browser.py tests/test_0199_phone_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```

## 7. Acceptance

- [ ] At 1024-1279 px the menu toggle opens the full menu over the page and closes it (toggle, Esc, tap outside).
- [ ] Phone and ≥1280 px unchanged (geometry tests green).
- [ ] A signed-in host going Back to a spent login link lands on `/`.
- [ ] Keys bumped, manifest regenerated, all §6 green, 0 skipped.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0251-report.md`, as in TEMPLATE.md §9. Do not push; do not open a PR.
