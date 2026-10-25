# 0373: Havel (AI) as a floating corner assistant that does not block the app

Status: todo
Depends on: 0324, 0332 (merged) | Base commit: a49cdaf (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0373-havel-corner
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner request (Josef, 2026-10-25): "I want the support AI assistant to be in the right corner, not in the sidebar. When you open him, you should still be able to use the app, not grey out the background. It leads you and supports you." Also: when Havel opens it shows a fixed introduction from the backend (no AI call, not counted, not sent to the model).

After this brief:

1. Every host page (except `/havel` itself) shows one round Havel button fixed in the bottom-right corner. The sidebar item and the phone top-bar icon are gone. The guide page button and the phone More row stay.
2. The Havel panel opens with `dialog.show()` (not `showModal()`): no backdrop, no grey, the page behind stays scrollable and clickable. The panel stays open when the host clicks the page; it closes only with its X button or Escape while focus is inside it.
3. Phone (< 768 px): the panel is a smaller bottom sheet that sits above the tab bar, full width, at most 70dvh tall, no backdrop. Computer: unchanged size and place (400 x 680, bottom-right).
4. While the panel is open the corner button is hidden; on close it comes back and gets focus (or the element that opened the panel, if that is still visible).
5. The home screen of the panel and of `/havel` starts with a Havel bubble with a fixed greeting (`havel.greeting`, en, cs, vi), above "What do you need help with?".
6. The text box empties as soon as a message is sent; on error the text comes back (already done by `showError`).

Out of scope: keeping the chat across pages (brief 0374, same branch, runs after this one). Do NOT edit `App/app/routes/havel.py` or `App/app/templates/_havel_form.html`: another branch is changing them.

## 2. Context

Rules: AGENTS.md 6 (works without JavaScript: the button is a link to `/havel`), 7 (browser tests 0 skipped, screenshots at 390 px), 9 (one copy key, three languages). MASTER 7.15 (Havel panel). Team pitfalls:

- Anything in `base.html` on every host page must not render `ui-btn-primary` (design tests count exactly one primary per page). The corner button is NOT a `ui-btn`; it has its own class `havel-fab`.
- Every new CSS class must be added to `docs/design/catalog.json` `"classes"` (next to `"havel-launcher"`), or `scripts/design_lint.py` fails.
- CSS uses tokens only (no raw hex, no raw px except 1px hairlines); copy has no em dashes.
- Playwright `wait_for_function("string")` is blocked by the CSP; use `expect(locator)` or a Python function.
- Every `*_browser.py` imports Playwright with `sync_api = pytest.importorskip("playwright.sync_api")`.

Current code (`grep -n` each before editing; STOP and report if one is missing):

- `App/app/templates/_shell_sidebar.html` line ~27: `<a class="host-help havel-launcher" href="/havel" ... data-sheet-open="havel-sheet" data-havel-launcher ...>`.
- `App/app/templates/_shell_topbar.html` line ~7: `<a class="ui-btn ui-btn-quiet ui-btn-icon havel-launcher" href="/havel" data-sheet-open="havel-sheet" data-havel-launcher aria-label="{{ t('havel.launcher') }}">`.
- `App/app/templates/_havel_panel.html`: `{% if nav | default('') != 'havel' %}<dialog id="havel-sheet" class="ui-dialog havel-dialog" ...>` ... `</dialog>{% endif %}`.
- `App/app/templates/_havel_topics.html`: the last `{% else %}` branch renders `<h2 class="havel-answer-title">{{ t('havel.topics_title') }}</h2>` (the home screen).
- `App/app/static/shell.js`: `if (sheet && typeof sheet.showModal === "function") { event.preventDefault(); if (!sheet.open) sheet.showModal(); }`.
- `App/app/static/havel.js`: `panel.showModal()` twice (the `[data-havel-more]` handler and `window.UbyHavel.open`), the `panel.addEventListener("close", ...)` focus return, `function send(extra)` with `var echoed = extra ? null : echo(text);`.
- `App/app/static/host2.css` ~line 934-958: block `/* 0324: Havel panel and launcher ...`, with `@media (min-width: 768px) { .host-workspace .havel-dialog { position: fixed; inset: auto var(--space-6) var(--space-6) auto; ...` and `@media (max-width: 767px) { .host-workspace .havel-dialog .ui-sheet { max-height: 92dvh; height: 92dvh; } }`. The phone tab bar is `.ui-tabbar` with height `calc(var(--tabbar-h) + var(--tabbar-safe))`; phone sticky action bars are `.ui-sticky-actions`.
- `App/app/templates/base.html`: `host2.css?v=20261025-0332`, `shell.js?v=20261019-v2a`, `havel.js?v=20261025-0332c`.
- i18n: `App/app/host_i18n.py` en `"havel.topics_title": "What do you need help with?",` (~1590) and cs `"havel.topics_title": "S čím potřebujete pomoct?",` (~3225); `App/app/host_vi_i18n.py` `"havel.topics_title": "Bạn cần giúp về việc gì?",` (~3363).
- Tests that pin the old launchers: `App/tests/test_havel_panel.py` (lines 15-23: count of `data-sheet-open="havel-sheet"` == 2, sidebar regexes), `App/tests/test_havel_browser.py` (`#app-sidebar [data-havel-launcher]` ~70, `.ui-topbar [data-havel-launcher]` ~107 and ~138, Escape closes ~96). `App/tests/test_havel_palette.py` checks the guide page button; it must still pass unchanged.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_shell_sidebar.html | edit | remove the Havel item |
| App/app/templates/_shell_topbar.html | edit | remove the Havel icon button |
| App/app/templates/_havel_panel.html | edit | corner button, `data-havel-modeless` on the dialog |
| App/app/templates/_havel_topics.html | edit | greeting bubble on the home screen |
| App/app/static/shell.js | edit | `show()` for modeless sheets, Escape |
| App/app/static/havel.js | edit | `show()`, button hide/show, focus, clear on send |
| App/app/static/host2.css | edit | `.havel-fab`, phone sheet |
| App/app/templates/base.html | edit | cache keys `20261025-0373` |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | `havel.greeting` |
| docs/design/catalog.json | edit | add `havel-fab`, `havel-greeting` |
| docs/design/MASTER.md | edit | 7.15 launcher sentence |
| App/tests/test_havel_panel.py, App/tests/test_havel_browser.py | edit | new launcher, modeless, greeting |
| docs/tasks/screenshots-0373/*.png | new | screenshots |

## 4. Steps

1. **Remove old launchers.** Delete the whole Havel `<a ...havel-launcher...>` line in `_shell_sidebar.html` and in `_shell_topbar.html`. Leave the guide page button (`guide.html`) and the More row (`_shell_tabbar.html`, `data-havel-more`) as they are.

2. **Corner button** in `_havel_panel.html`, inside the same `{% if nav | default('') != 'havel' %}`, right before `<dialog`:
   ```
   <a class="havel-fab" href="/havel" data-sheet-open="havel-sheet" data-havel-launcher data-havel-fab aria-label="{{ t('havel.launcher') }}" title="{{ t('havel.launcher') }}">{{ icon('message-circle-question', 24) }}</a>
   ```
   Add `data-havel-modeless` to the `<dialog ...>` tag. Without JavaScript the button is a plain link to `/havel`.

3. **shell.js**: in the opener branch, if `sheet.hasAttribute("data-havel-modeless")` and `typeof sheet.show === "function"`, call `event.preventDefault(); if (!sheet.open) sheet.show();` and `return`; otherwise keep the `showModal()` code. The click-on-backdrop close (`event.target === open`) must not close a modeless dialog: add `&& !open.hasAttribute("data-havel-modeless")`. Add a `keydown` listener: on `Escape`, if `document.activeElement` is inside `dialog[data-havel-modeless][open]`, close that dialog and `preventDefault()`.

4. **havel.js**:
   - Replace both `panel.showModal()` calls with `panel.show()` (keep the `typeof panel.show !== "function"` guard in the More handler).
   - Add `function fab() { return document.querySelector("[data-havel-fab]"); }`. Remember the opener: in the document click listener, when a `[data-sheet-open="havel-sheet"]` or `[data-havel-more]` is clicked, store it in `var opener`. After the panel opens (in `ensureForm` callback and on the launcher click), set `fab().hidden = true` and, on computer (`!PHONE.matches`), focus the textarea; on phone focus `#havel-title` with `tabindex="-1"` set on it in the template (add `tabindex="-1"` to `<h2 id="havel-title">`). Do not steal focus anywhere else.
   - Replace the `close` listener: set `fab().hidden = false`; focus `opener` if it is still in the page and `offsetParent !== null`, else focus `fab()`.
   - In `send(extra)`: right after `var echoed = extra ? null : echo(text);` add `if (!extra && ta) { ta.value = ""; ta.dispatchEvent(new Event("input")); }`. `showError(text)` already puts the text back; keep that.

5. **CSS** (`host2.css`, at the end of the 0324 block). Tokens only:
   - `.host-workspace .havel-fab`: `position: fixed; right: var(--space-6); bottom: var(--space-6); z-index: var(--z-drawer);` 56 px circle as `width/height: calc(var(--control-h) + var(--space-3))` (or the nearest token that gives 52 to 56 px; must be at least 44 px), `display: inline-flex; align-items: center; justify-content: center; border-radius: var(--radius-pill); background: var(--accent); color: var(--accent-on, var(--surface)); box-shadow: var(--shadow-2)` (use the shadow token the dialogs use; `grep -n "shadow" App/app/static/tokens.css`). `:hover` a darker accent token if one exists, `:focus-visible { box-shadow: var(--focus-ring-2); outline: 0; }`, `[hidden] { display: none; }`.
   - Phone `@media (max-width: 767px)`: `.havel-fab { right: var(--space-4); bottom: calc(var(--tabbar-h) + var(--tabbar-safe) + var(--space-4)); }` and on pages with a sticky action bar `body:has(.ui-sticky-actions) .havel-fab` add the bar height: use `calc(var(--tabbar-h) + var(--tabbar-safe) + var(--control-h) + var(--space-8))`.
   - Phone panel: replace the 92dvh rule with `.host-workspace .havel-dialog { inset: auto 0 calc(var(--tabbar-h) + var(--tabbar-safe)) 0; z-index: var(--z-drawer); }` and `.host-workspace .havel-dialog .ui-sheet { height: min(70dvh, 560px); max-height: 70dvh; }` (560px is fine as a size cap if the lint allows px for sizes in this file; check how `--havel-h` is set and reuse that pattern with a `--havel-h-phone: 560px` custom property). Add a top hairline/shadow so it reads as a layer without a backdrop.
   - `.host-workspace .havel-dialog::backdrop { display: none; }` is not needed with `show()`; do not add it.
   - Greeting: `.host-workspace .havel-greeting { margin-bottom: var(--space-2); }`.
   Add `havel-fab` and `havel-greeting` to `docs/design/catalog.json` `"classes"` right after `"havel-launcher"`.

6. **Greeting** in `_havel_topics.html` (placement at the end of this step):
   ```
   <div class="havel-msg havel-msg-havel havel-greeting" data-havel-greeting>
     <div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div>
     <div class="havel-bubble"><p>{{ t('havel.greeting') }}</p></div>
   </div>
   ```
   It is template text only: no AI call, no limit count, never in `history`. Add the key after each `havel.topics_title` line (draft wording; the owner may replace it later, keep it one key):
   - en: `"havel.greeting": "Hi, I'm Havel, the UbyHost support assistant (AI). I can show you where everything is in the app and walk you through it step by step. Pick a topic below or just write your question in your own words.",`
   - cs: `"havel.greeting": "Dobrý den, jsem Havel, asistent podpory UbyHost (AI). Ukážu vám, kde co v aplikaci najdete, a provedu vás krok za krokem. Vyberte si téma níže, nebo mi napište otázku vlastními slovy.",`
   - vi: `"havel.greeting": "Xin chào, tôi là Havel, trợ lý hỗ trợ của UbyHost (AI). Tôi có thể chỉ cho bạn mọi thứ nằm ở đâu trong ứng dụng và hướng dẫn bạn từng bước. Hãy chọn một chủ đề bên dưới hoặc viết câu hỏi bằng lời của bạn.",`
   Placement: `havel.js` `echo(text)` removes `[data-havel-topics]` when the host types, and the greeting must stay as the first message. So put the greeting block BEFORE `<div class="havel-topics" data-havel-topics>`, wrapped in `{% if not havel_answer and not havel_topic_data %}...{% endif %}` so it shows only on the home screen. Not inside the `{% else %}` branch.

7. **MASTER 7.15**: replace "Launchers: sidebar item above Help & guide; phone top-bar icon button and More row. No floating bubble, no toasts in the panel." with "Launcher: one round accent button fixed bottom-right (`.havel-fab`, above the tab bar on phone), hidden while the panel is open; plus the phone More row and the guide page button. The panel opens with `show()`: no backdrop, the page stays usable; it closes with its X or Escape. Phone: bottom sheet above the tab bar, at most 70dvh. The home screen starts with the fixed greeting `havel.greeting` (template, no AI). No toasts in the panel."

8. **base.html**: bump `host2.css?v=`, `shell.js?v=` and `havel.js?v=` to `20261025-0373`.

9. **Tests.**
   - `test_havel_panel.py`: the dashboard has `data-havel-fab` once, `page.count('data-sheet-open="havel-sheet"') == 1`, no `havel-launcher` in the sidebar/topbar markup, `data-havel-modeless` on the dialog, `data-havel-greeting` in the panel with the en greeting text; `/havel` has no `data-havel-fab` but has the greeting. Add one test that `?lang=cs` (or however the other tests switch language; grep) renders the cs greeting.
   - `test_havel_browser.py`: computer 1280: click `[data-havel-fab]`, dialog open, `page.evaluate("document.querySelector('#havel-sheet').matches(':modal')")` is False, the fab is hidden, a link in the sidebar is still clickable while open (click `#app-sidebar a[href="/properties"]` or any nav link in a NEW page check is not needed: just assert `page.locator("#app-sidebar a").first.is_enabled()` and that `document.elementFromPoint` at the sidebar centre is inside `#app-sidebar`), Escape with focus in the panel closes it, fab visible again and focused. Phone 390: fab visible above the tab bar (its bottom < tab bar top), tap opens the sheet, sheet bottom <= tab bar top + 1, sheet height <= 0.7 * viewport + 1, the tab bar is still clickable (elementFromPoint inside `.ui-tabbar`). Send a message and assert the textarea is empty before the reply arrives (check right after `press("Enter")`). Replace the old sidebar/topbar locators everywhere with `[data-havel-fab]`.
   - Screenshots to `docs/tasks/screenshots-0373/`: `fab-dashboard-390.png`, `panel-open-390.png` (with greeting), `panel-open-1280.png`, `panel-open-cs-390.png`.

## 5. Checks

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
.venv/bin/python -m pytest tests/test_havel_panel.py tests/test_havel_page.py tests/test_havel_palette.py tests/test_havel_browser.py tests/test_design_*.py tests/test_dev_ui.py tests/test_send_controls.py tests/test_stay_fee_detail.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py | tail -5 && python3 scripts/context_lint.py | tail -5
```
Browser tests must run with 0 skipped (`UBYHOST_REQUIRE_BROWSER=1`). Then `git checkout -- docs/tasks/screenshots-0*` for folders other than `screenshots-0373` (browser runs rewrite them). Write `docs/tasks/0373-report.md` (what changed, test output tail, screenshot list). Commit; do not push.
