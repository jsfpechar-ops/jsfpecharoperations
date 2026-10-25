# 0389: Leon greets the guest first

Status: todo
Depends on: 0387, 0388 (same branch, not merged) | Branch: claude/0387-leon-chat-look (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner (Josef, 2026-10-25): Havel greets first, Leon should too. Today the Leon card shows an empty chat until the guest writes. After this brief, the chat log always starts with one Leon bubble holding a fixed welcome (`leon_welcome`). It is rendered by the page script, with no AI call, never stored, never counted against caps, and not sent to the model. Because the welcome now introduces Leon, his reply to a bare "hi" (`leon_hi`) becomes a short "Hello! What can I do for you?" so he does not introduce himself twice.

## 2. Context

- `App/app/static/guest-leon.js`: `bubble(role, kind, body)` appends `div.g-leon-msg.g-leon-msg--<role>` with `data-leon-msg=<role>` to `log`. `render(data)` empties `log`, adds one bubble per `data.messages`, appends queued items, then sets `log.hidden = !log.firstChild;`. `history()` runs on load (~283) and calls `render`. `text(name)` reads `data-<name>` from the root.
- `App/app/templates/guest/_leon.html`: the root `<section ... data-leon ...>` carries `data-text-*` attributes. The log is `<div class="g-leon-log" ... data-leon-log hidden></div>`.
- Copy lives in `App/app/i18n.py` (en, cs, de, es, fr dicts) and `App/app/guest_uk_i18n.py` (uk). `leon_hi` is used by `leon.py` (`_fixed(lang, "leon_hi" ...)`) as the local small-talk reply.
- `App/tests/test_guest_leon_browser.py` waits for `[data-leon-msg=leon]` after sending. The welcome must NOT carry `data-leon-msg="leon"`, or that wait passes too early.

## 3. Files

| Path | Action |
|---|---|
| App/app/i18n.py, App/app/guest_uk_i18n.py | new `leon_welcome`, new `leon_hi` values |
| App/app/templates/guest/_leon.html | one data attribute |
| App/app/static/guest-leon.js | welcome bubble in render |
| App/app/templates/guest/base.html | bump guest-leon.js `?v=` to `20261025-0389` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_guest_leon_browser.py, other tests asserting `leon_hi` text | update or add assertions |

## 4. Steps

1. **Copy.** Add `leon_welcome` right after `leon_hi` in each language, and change `leon_hi`:

| lang | leon_welcome (new) | leon_hi (new value) |
|---|---|---|
| en | Hello, I'm Leon, your 24/7 concierge for this stay. What can I do for you? | Hello! What can I do for you? |
| cs | Dobrý den, jsem Leon, váš concierge nonstop po celý pobyt. Co pro vás můžu udělat? | Dobrý den! Co pro vás můžu udělat? |
| de | Hallo, ich bin Leon, Ihr Concierge rund um die Uhr für diesen Aufenthalt. Was kann ich für Sie tun? | Hallo! Was kann ich für Sie tun? |
| es | Hola, soy Leon, su conserje 24/7 durante esta estancia. ¿Qué puedo hacer por usted? | ¡Hola! ¿Qué puedo hacer por usted? |
| fr | Bonjour, je suis Leon, votre concierge 24h/24 pendant ce séjour. Que puis-je faire pour vous ? | Bonjour ! Que puis-je faire pour vous ? |
| uk | Вітаю, я Leon, ваш консьєрж 24/7 на час проживання. Чим можу допомогти? | Вітаю! Чим можу допомогти? |

2. **Template**: add `data-text-welcome="{{ t('leon_welcome') }}"` to the root `<section>`, next to `data-text-queued`.

3. **JS** (`guest-leon.js`):
   - Add a function after `bubble`:
```js
  // 0389: Leon speaks first. A fixed welcome drawn by the page: never stored, never sent, never counted.
  function welcome() {
    var item = bubble("leon", "", text("text-welcome"));
    item.setAttribute("data-leon-msg", "welcome");
    return item;
  }
```
   - In `render(data)`, right after the `while (log.firstChild) ...` line, add `welcome();`.
   - Also call `welcome();` once at start-up, just before the initial `history().catch(...)` call at the bottom (~283), so the bubble shows before the first fetch returns. `render` clears and redraws it, so it never appears twice. Check that nothing else empties the log without calling `render`. If something does, add `welcome();` after it.
   - `log.hidden = !log.firstChild;` stays. The log is never empty now, so it shows.

4. **Version key**: bump guest-leon.js in `templates/guest/base.html` to `?v=20261025-0389`, then run `tests/test_static_versions.py --write` from `App/`.

5. **Tests**:
   - grep `App/tests/` for the old `leon_hi` texts (`your 24/7 concierge for this stay`, `concierge nonstop po celý pobyt`, plus the uk/de/es/fr versions) and update any assertion that checks the small-talk reply to the new `leon_hi`.
   - In `test_guest_leon_browser.py`, add `test_leon_greets_first` (seed and monkeypatch like `test_the_chat_works_and_lays_out_on_a_phone`, en, 390x844). Load the page and check: `[data-leon-msg=welcome]` has count 1 and is visible, its text contains "your 24/7 concierge", there is no `[data-leon-msg=leon]` yet, and the welcome is the first child of `[data-leon-log]`. Send "Is there parking?" with the fake AI reply the existing test uses, wait for `[data-leon-msg=leon]`, and check `[data-leon-msg=welcome]` still has count 1. Reload the page: welcome count is 1 and it is still the first child. Save `#leon` screenshots before sending: `leon-welcome-390.png` into `SHOTS` and into `docs/tasks/screenshots-0387/`.
   - Run the existing chat test too. The leon screenshot `leon-chat-390.png` now also shows the welcome bubble on top.

## 5. Do not touch

Everything outside §3. No change to leon.py logic, routes, caps, stored history, or the prompt.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_leon_chat.py tests/test_leon.py tests/test_guest_guide_browser.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep -v -e screenshots-0387 -e 0389) 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] `docs/tasks/screenshots-0387/leon-welcome-390.png` shows the welcome bubble in an otherwise empty chat. You looked at it once.

## 9. Report

`docs/tasks/0389-report.md` (150 tokens), `Status: review`. ONE commit `0389: Leon greets the guest first`, including this brief and the screenshots, ending with:
```
Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Lvzax2VbKkYR4rb7JYLc3K
```
Do not push.
