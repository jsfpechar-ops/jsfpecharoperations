# 0395: Havel panel always sits above the page; a stale start screen is never restored

Status: done
Depends on: main (0391 topics-first merged) | Branch: claude/0395-havel-panel-layer (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner (Josef, 2026-10-25, desktop screenshot of the production dashboard): the reservations calendar's day-header row (Fri 23 to Thu 29) draws on top of the open Havel panel and hides the "Calendars (Airbnb, Booking)" chip. "This looks like a bug, resolve it and find the issue."

Two bugs, both found by the orchestrator:

1. **Layering.** Havel is a non-modal `<dialog>` opened with `panel.show()`, so it is not in the browser's top layer and needs its own `z-index`. On phones (`max-width: 767px`) it gets `z-index: var(--z-drawer)`, but the computer rule (`min-width: 768px`, host2.css ~951) has none. The calendar header is `position: sticky; z-index: 10` (dashboard-calendar.css:70, the name column 11), so it paints over the panel. Any page dropdown (`--z-popover`, 60) would too.
   Fix: one `z-index: var(--z-popover)` for the panel at every width. Toasts (`--z-toast`, 80) stay above it; page sticky rows (10, 11, `--z-sticky` 20), the sidebar and the tab bar (`--z-drawer` 40 / `--z-sticky`) stay below it.
2. **Stale start screen.** The same screenshot shows the old topic list without "Other topic", although 0391 was live (production deploy 20:46 UTC, screenshot ~21:03 UTC). `restore()` in havel.js puts the thread HTML saved in sessionStorage back on every page load (up to 12 hours). When the saved thread is only the start screen (greeting + topic chips, no host bubble), it replaces the fresh server copy: an old deploy's topics come back, and the topics of the page where it was saved show on every other page.
   Fix: restore the saved thread HTML only when it holds a conversation, i.e. contains `havel-msg-host` (every topic, question, Other or AI exchange adds one). Otherwise keep the server's fresh start screen; the open/unread state and the hidden fields are still restored.

No copy change, no look change.

## 2. Context

- `App/app/static/host2.css` ~949 to ~1057: `.havel-dialog` rules. Line ~949 is the base rule (`--havel-w`, `--havel-h`), ~951 the `min-width: 768px` rule, ~984 and ~1056 the two `max-width: 767px` rules that each set `z-index: var(--z-drawer)`.
- `App/app/static/tokens.css` ~96: `--z-sticky: 20; --z-drawer: 40; --z-popover: 60; --z-toast: 80; --z-dialog: 100`.
- `App/app/static/havel.js` ~80: `restore()`; inside it `apply` does `t.innerHTML = s.html;`.
- `App/app/templates/base.html`: `host2.css?v=20261025-0386c` (~26) and `havel.js?v=20261025-0391` (~250).
- Browser tests reuse `tests/test_havel_browser.py` (`origin`, `_context`) and the `host` fixture, see `tests/test_0391_havel_topics_first_browser.py`. The dashboard (`/`) shows the reservations calendar (`.cal-gantt-header`) for the seeded host.

## 3. Files

| Path | Action |
|---|---|
| App/app/static/host2.css | z-index on the base `.havel-dialog` rule, drop the two phone ones |
| App/app/static/havel.js | restore thread HTML only with a host bubble |
| App/app/templates/base.html | bump host2.css and havel.js keys to `?v=20261025-0395` |
| App/tests/static_versions.json | `tests/test_static_versions.py --write` |
| App/tests/test_0395_havel_panel_layer_browser.py | new test |

## 4. Steps

1. **CSS** (`host2.css`).
   - Base rule: `.host-workspace .havel-dialog { --havel-w: 400px; --havel-h: 680px; }` becomes
     `.host-workspace .havel-dialog { --havel-w: 400px; --havel-h: 680px; z-index: var(--z-popover); }`
     Put the comment line `/* 0395: show() keeps the panel out of the top layer, so it needs its own layer above sticky page rows and dropdowns. */` directly above it.
   - In the two `@media (max-width: 767px)` `.host-workspace .havel-dialog { ... }` rules (~984, ~1056) remove only the ` z-index: var(--z-drawer);` declaration. Change nothing else on those lines.

2. **JS** (`havel.js`, `restore()`): replace
   `      t.innerHTML = s.html;`
   with
   ```
      // 0395: a saved start screen is never newer than the server's (topics change per page and per deploy).
      if (s.html.indexOf("havel-msg-host") !== -1) t.innerHTML = s.html;
   ```

3. **Version keys** (`base.html`): `host2.css?v=20261025-0386c` → `host2.css?v=20261025-0395`, `havel.js?v=20261025-0391` → `havel.js?v=20261025-0395`. Then `.venv/bin/python tests/test_static_versions.py --write` (check the file's docstring for the exact command).

4. **New test** `tests/test_0395_havel_panel_layer_browser.py`: copy the imports, `importorskip` line, `origin`/`_context`/`host` lines and `_open` from `test_0391_havel_topics_first_browser.py`. `SHOTS = ... "screenshots-0395"`.
   - `test_panel_above_calendar(origin)` at 1280 (use a viewport 1280x800; if `_context` takes only a width, that is fine):
     - `page.goto(origin[0] + "/")`, `header = page.locator(".cal-gantt-header").first`, `header.wait_for()`.
     - `dialog = _open(page)`.
     - `assert page.evaluate("getComputedStyle(document.getElementById('havel-sheet')).zIndex") == "60"`.
     - Scroll so the calendar header row is behind the panel: `page.evaluate("""() => { const h = document.querySelector('.cal-gantt-header'); const d = document.getElementById('havel-sheet').getBoundingClientRect(); window.scrollBy(0, h.getBoundingClientRect().top - (d.top + d.height / 2)); }""")`.
     - Then for the point at the header's vertical centre and the panel's horizontal centre:
       `hit = page.evaluate("""() => { const h = document.querySelector('.cal-gantt-header').getBoundingClientRect(); const d = document.getElementById('havel-sheet').getBoundingClientRect(); const el = document.elementFromPoint(d.left + d.width / 2, h.top + h.height / 2); return !!(el && el.closest('#havel-sheet')); }""")` → `assert hit`. If the header is not inside the panel's box after the scroll (`h.top < d.top or h.bottom > d.bottom`), STOP and ask (§8).
     - Screenshot `panel-calendar-1280.png` (viewport, not full_page).
   - `test_stale_start_screen_not_restored(origin)` at 1280:
     - Open `/`, open the panel, close it, then
       `page.evaluate("""() => { const k = 'ubyhost.havel.chat'; const s = JSON.parse(sessionStorage.getItem(k)); s.html = '<div class="havel-topics" data-havel-topics><p>STALE</p></div>'; s.open = true; sessionStorage.setItem(k, JSON.stringify(s)); }""")`.
       (If `sessionStorage.getItem(k)` is null after closing, set `{owner: <the panel's data-havel-owner>, saved: Date.now(), html: ..., open: true}` instead.)
     - `page.reload()`; `dialog = page.locator("#havel-sheet[open]")`; `dialog.wait_for()`.
     - `sync_api.expect(dialog.locator("[data-havel-other]")).to_be_visible()` and `assert "STALE" not in dialog.inner_text()`.
     - Same again but `s.html` holds a conversation: `'<div class="havel-msg havel-msg-host"><div class="havel-bubble"><p>KEEP ME</p></div></div>'`: after reload `assert "KEEP ME" in dialog.inner_text()`.
   - `test_phone_panel_above_tabbar(origin)` at 390: open `/`, open the panel, `assert` computed zIndex is `"60"`, screenshot `panel-390.png`.

## 5. Do not touch

havel.py, routes, templates other than base.html's two version keys, copy (`havel.intro` stays), dashboard-calendar.css, every other z-index.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
node --check app/static/havel.js
.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0395_havel_panel_layer_browser.py tests/test_0391_havel_topics_first_browser.py tests/test_0386_havel_phone_look_browser.py tests/test_havel_browser.py tests/test_static_versions.py tests/test_design_*.py -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep screenshots- | grep -v screenshots-0395) 2>/dev/null; true
```
If ruff is not in `.venv/bin`, run `.venv/bin/pip install -q ruff` once. If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] `panel-calendar-1280.png`: the calendar day row stops at the panel's left edge; the panel's chips are whole. `panel-390.png`: panel as before. You looked at each once.

## 8. Stop and ask

As in TEMPLATE §8. Also: the header is not behind the panel after the scroll in step 4.

## 9. Report

No report file. ONE commit `0395: Havel panel above sticky page rows; no stale start screen restore`, including this brief and the screenshots, ending with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01VRuzvVQhNfP97gJ4nEGYXQ`. Do not push.
