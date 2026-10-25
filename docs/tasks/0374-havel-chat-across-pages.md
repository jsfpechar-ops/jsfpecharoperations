# 0374: Havel (AI) keeps the chat while the host moves between pages

Status: todo
Depends on: 0373 (same branch, must be committed first) | Base commit: the 0373 commit on task/0373-havel-corner | Branch: task/0373-havel-corner
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner request (Josef, 2026-10-25): Havel "leads you and supports you" while the host keeps using the app, like the in-app support chat in Wolt: the chat floats in the corner, survives every page change, and closing it only minimises it. Havel answers contain links to app pages; after the host taps one, the new page must show the same chat, still open if it was open.

After this brief:

1. The chat (thread HTML plus the signed history fields) is kept in the tab's `sessionStorage` under one key and restored on every host page and on `/havel`. The server still stores nothing.
2. If the panel was open when the page changed, it opens again on the new page (with `show()`, no focus steal, scrolled to the newest message).
3. "New chat" (the reset submit) and signing out clear the stored chat. A stored chat from another user is ignored and removed.
4. The `/havel` no-JavaScript fallback page (reached only by direct URL) also restores the same chat; there is no link to it in the panel.
5. If a Havel reply arrives while the panel is closed, the corner button shows a small dot until the panel is opened again.

## 2. Context

0373 added: `[data-havel-fab]` corner link, `data-havel-modeless` dialog opened with `panel.show()`, `fab()` helper and the `opener`/close focus code in `App/app/static/havel.js`, the greeting `[data-havel-greeting]` in `_havel_topics.html`. `grep -n` these first; STOP if 0373 is not committed on this branch.

`havel.js` facts (`grep -n` each): `var root = panel || page;`, `function swap(html, mode)` (replaces the thread on "replace", appends otherwise, then copies the server's `[data-havel-form-wrap]` into the live one), `function send(extra)` (success path calls `swap(...)` then `focusAnswer()`), `function ensureForm(done)` (fetches `panel.getAttribute("data-src")` once to get the composer), the submit listener's reset branch `if (submitter && submitter.name === "reset") { send({ reset: "1", message: "" }); return; }`. The composer `_havel_form.html` has hidden inputs `[data-havel-history]` (name `history`), `[data-havel-sig]` (name `history_sig`), `[data-havel-topic]`, `[data-havel-q]`, and also `page` and `return_to`, which belong to the CURRENT page and must never be restored. Do NOT edit `_havel_form.html` or `App/app/routes/havel.py` (another branch changes them); if the form renders a "messages left" line, do not store or restore it, the server renders it fresh.

The page behind each panel is different, so only these are stored: thread HTML, `history`, `history_sig`, `topic`, `q`, `open` (bool), `owner`, `saved` (ms time). Sign-out: `grep -n 'logout' App/app/templates/*.html | head` to find the sign-out form or link.

Privacy (AGENTS.md rule 2): `sessionStorage` is per tab, is gone when the tab closes, is never sent to the server, and is not a tracking cookie. Add one sentence about it under the Havel row in `docs/privacy/ROPA.md` only if that file has a Havel row (`grep -n -i havel docs/privacy/ROPA.md`); otherwise mention it in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_havel_panel.html | edit | `data-havel-owner` on the dialog |
| App/app/templates/havel.html | edit | `data-havel-owner` on `[data-havel-page]` |
| App/app/static/havel.js | edit | save, restore, clear, unread dot |
| App/app/static/host2.css | edit | `.havel-fab-dot` |
| docs/design/catalog.json | edit | add `havel-fab-dot` |
| App/app/templates/base.html | edit | cache keys `20261025-0374` |
| App/tests/test_havel_browser.py | edit | two browser tests |
| docs/tasks/screenshots-0374/*.png | new | screenshots |

## 4. Steps

1. **Owner marker.** Add `data-havel-owner="{{ current_user.id }}"` to the `<dialog id="havel-sheet" ...>` and to `<section class="ui-section havel-page" data-havel-page>`.

2. **Storage helpers** in `havel.js` (every access in `try { } catch (e) { }`, the app must work when storage throws):
   ```
   var KEY = "ubyhost.havel.chat";
   function owner() { return root.getAttribute("data-havel-owner") || ""; }
   function load() { try { var s = JSON.parse(sessionStorage.getItem(KEY) || "null"); if (s && s.owner === owner()) return s; sessionStorage.removeItem(KEY); } catch (e) {} return null; }
   function save(extra) { ... }   // writes {owner, saved: Date.now(), html, history, sig, topic, q, open, unread}
   function clear() { try { sessionStorage.removeItem(KEY); } catch (e) {} }
   ```
   (Name it `loadChat` if `load` already exists in the file: it does, for topic links. Do not shadow it.) `html` is `thread().innerHTML` with any `[data-havel-writing]` and error-retry bubbles removed (clone the thread, remove them, take `innerHTML`). `open` is `panel ? panel.open : false`. Keep `unread` from the previous value unless `extra` sets it.

3. **When to save:** at the end of `swap()` (after every server fragment), after `echo()`, in the panel `close` listener (with `open: false`), and when the panel opens (`open: true`). Do not save while `send()` is waiting: save happens in `swap()` after the reply.

4. **Restore on page load** (before `setDevice(); bindCounter();` at the end):
   - `var s = loadChat();` if `s` and `s.html`: set `thread().innerHTML = s.html`. On the panel, call `ensureForm(fill)`; on `/havel` the form is already there, so call `fill()` directly. `fill` sets `[data-havel-history]`, `[data-havel-sig]`, `[data-havel-topic]`, `[data-havel-q]` values from `s`, then `scrollDown()`.
   - If `/havel` was server-rendered with its own non-empty thread (a non-JS post), the page wins: if `[data-havel-history]` already has a value on the page and `s.history` differs, do not restore; `save()` the page's state instead.
   - Panel only: if `s.open`, call `panel.show()` and hide the fab, without moving focus. If `s.unread` and not open, show the dot (step 6).
   - Stale guard: ignore and clear a stored chat older than 12 hours (`Date.now() - s.saved > 43200000`).

5. **Clear:** in the reset branch, call `clear()` before `send({ reset: "1", message: "" })` (the fresh fragment is then saved by `swap`). On the sign-out form `submit` (or link `click`), call `clear()` (one `document.addEventListener` matching the selector you found).

6. **Unread dot.** In `send()` success, if `panel && !panel.open`, call `save({ unread: true })` and set `fab().setAttribute("data-unread", "")`. When the panel opens, remove the attribute and `save({ unread: false })`. CSS: `.host-workspace .havel-fab[data-unread]::after { content: ""; position: absolute; top: var(--space-1); right: var(--space-1); width: var(--space-3); height: var(--space-3); border-radius: var(--radius-pill); background: var(--danger); border: 2px solid var(--surface); }` and `position: fixed` already makes the fab a containing block. No new copy key and no new class (the attribute selector needs no catalog entry).

7. **base.html**: bump `host2.css` and `havel.js` to `?v=20261025-0374`.

8. **Tests** in `test_havel_browser.py` (reuse `_context`, `origin`, `SHOTS` patterns; write new shots to `docs/tasks/screenshots-0374/`):
   - `test_chat_follows_the_host_across_pages` (1280 and 390): open the panel with `[data-havel-fab]`, send one message (the fake AI answers), wait for the answer, `page.goto(origin + "/properties")` (or any other host page; grep one that exists), assert `#havel-sheet[open]` is visible without clicking, the host bubble with the same text is in the thread, `[data-havel-history]` value equals the one before the navigation. Close the panel, navigate again, assert it stays closed but the chat is in the thread after opening. Screenshot `restored-390.png`.
   - `test_new_chat_and_other_user_clear_it`: after one message, submit "New chat" (`button[name=reset]`), navigate, assert no `.havel-msg-host` in the thread and the greeting is shown. Then write a fake stored chat with `owner: "999999"` via `page.evaluate` (a Python string is fine here: `page.evaluate` is allowed, only `wait_for_function` strings are blocked), reload, assert it was not restored and the key is gone.
   - Do not add a dot test if it needs a slow fake reply; a unit-level check that `data-unread` is set after a reply that arrives while closed is enough if the fake can delay (grep `ai_fake` for a delay option; skip if none and say so in the report).

## 5. Do not touch

`App/app/routes/havel.py`, `App/app/templates/_havel_form.html`, `App/app/havel.py`, the server: nothing is stored server-side.

## 6. Commands

From `App/` (browser tests: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`):
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_havel_panel.py tests/test_havel_page.py tests/test_havel_palette.py tests/test_havel_browser.py tests/test_design_*.py tests/test_dev_ui.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py | tail -5 && python3 scripts/context_lint.py | tail -5
```

## 7. Acceptance

All the Objective points hold; the commands pass with 0 skipped browser tests; ruff, design_lint and context_lint pass. Then `git checkout --` the other `docs/tasks/screenshots-0*` folders the run rewrote.

## 8. Stop and ask

A `grep -n` anchor from section 2 is missing, a copy key already exists, a test outside the Havel files fails in a way this change could cause, or the work needs an edit in a "Do not touch" file.

## 9. Report

`docs/tasks/0374-report.md`: what changed per step, the test output tail (passed/failed/skipped), the screenshot list, deviations. Commit on the branch; do not push.
