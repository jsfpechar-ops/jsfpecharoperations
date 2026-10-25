# 0386: Havel (AI) looks like a support chat on the phone

Status: todo
Depends on: 0373, 0374 (merged) | Base commit: HEAD of origin/main | Branch: claude/0386-havel-phone-look (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner phone screenshot (Josef, 2026-10-25, 390 px): "This looks horrible." What was wrong: (a) iPhone draws a red focus box around the "Havel (AI)" title when the sheet opens; (b) the topics are a boxed menu with chevrons, like a settings list; (c) with chat off, "Havel is unavailable right now. You can still write to support here." has no button, so it leads nowhere; (d) two grey disclaimer paragraphs; (e) the sheet is short. The benchmark is Wolt's in-app support. Mockups: `/mnt/project-files/havel-phone/havel-phone-f1.png` (home), `-f2.png` (topic and answer), `-f3.png` (chat off).

After this brief, in the panel AND on `/havel`:

1. No visible focus ring on the title or on a Havel bubble when the script moves focus there (keyboard focus on links and buttons keeps its ring).
2. The header avatar is a solid accent circle with a white icon.
3. The topics, a topic's questions and the follow-up questions (`[data-havel-next]`) are pill chips that wrap, left-aligned under Havel's bubble. No boxed menu, no chevrons.
4. On a topic screen, the chosen topic shows as the host's bubble (right). On an answer screen, the chosen question shows as the host's bubble. The "All topics" back link is a quiet chip.
5. The composer is one rounded input with a round send icon button inside it on the right. It grows with the text up to about 5 lines. "New conversation" is a quiet compact button under the input, only when the chat is not fresh. Under that comes one short AI line.
6. When chat is off or a limit is reached (`havel_state` set), there is no input and no AI line. Instead there is a one-line status (`havel.<state>`) and a full-width "Write to support" button that opens the existing support answer.
7. Phone (< 768 px): the sheet is almost full height. Its top is `var(--space-12)` below the top of the viewport and it covers the tab bar while open. It is still non-modal (no backdrop) and keeps its handle and X.

## 2. Context

Rules: AGENTS.md 6 (works without JavaScript: every chip is a real link or submit button), 7 (browser tests 0 skipped, 390 px screenshots), 9 (copy in en, cs, vi; no em dashes). Team pitfalls:
- `base.html` pages must not render `ui-btn-primary`. The composer loads lazily (havel.js `ensureForm`), so the send button may stay `ui-btn-primary`. The support button in the off state must be `ui-btn-secondary`.
- Every new CSS class goes into `docs/design/catalog.json` `"classes"` (next to `"havel-composer"`), or `scripts/design_lint.py` fails. CSS uses tokens only (no hex, no bare px except 1px).
- Playwright `wait_for_function("string")` is blocked by the CSP. Use `expect(locator)`.
- Browser tests need `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium` locally.

Current code (`grep -n` each before editing; STOP and report if one is missing):
- `App/app/static/host2.css` ~556: `.host-workspace :is(a, button, input, select, textarea, summary, [tabindex]):focus-visible { outline: 2px solid var(--coral-600) !important; ...}`. This beats `.havel-head h2[tabindex="-1"]:focus { outline: none; }` (~962), and iOS treats script focus as focus-visible. That is cause (a).
- `host2.css` ~911-1006: all `.havel-*` rules. Phone block `@media (max-width: 767px) { .host-workspace .havel-dialog { position: fixed; inset: auto 0 calc(var(--tabbar-h) + var(--tabbar-safe)) 0; ... } .havel-dialog .ui-sheet { max-height: 70dvh; height: 70dvh; } ...}`. `.ui-chip` already exists (~71). Tab bar z-index is `var(--z-sticky)`, dialog `var(--z-drawer)`.
- `App/app/templates/_havel_panel.html`: header `<span class="havel-avatar" ...>{{ icon('message-circle-question', 16) }}</span>`.
- `App/app/templates/_havel_topics.html`: three branches (answer / topic / home). The topic and home branches render `<div class="ui-menu-panel" ...>` with `<a class="ui-menu-item havel-topic" ... data-havel-topic-link>... {{ icon('chevron-right', 16) }}</a>`. The back links are `ui-btn ui-btn-quiet ui-btn-compact` with `data-havel-topic-link`.
- `App/app/templates/_havel_thread.html`: `[data-havel-next]` buttons are `ui-btn ui-btn-secondary ui-btn-compact`.
- `App/app/templates/_havel_form.html`: the whole composer, including `{% if havel_state %}<p class="havel-meta">{{ t('havel.' ~ havel_state) }}</p>{% else %}...{% endif %}` and `<p class="havel-meta havel-note">{{ t('havel.ai_note') }}</p>` at the end.
- `App/app/static/havel.js` `bindCounter()`: `ta.insertAdjacentElement("afterend", counter);`.
- `App/tests/test_havel_browser.py` `test_phone_launcher_and_sheet`: asserts `sheet["height"] <= 900 * 0.7 + 1`, `sheet bottom <= tabbar y + 1`, and that the tab bar centre is hit-testable while the sheet is open. These encode the old 70% sheet and change in step 7.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_havel_panel.html | avatar icon size |
| App/app/templates/_havel_topics.html | chips, host bubbles |
| App/app/templates/_havel_thread.html | next buttons as chips |
| App/app/templates/_havel_form.html | pill composer, off state |
| App/app/static/host2.css | append one block (overrides) |
| App/app/static/havel.js | counter placement, auto-grow |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | 3 copy values, 1 new key |
| docs/design/catalog.json | new classes |
| App/app/templates/base.html | bump host2 and havel.js `?v=` keys to `20261025-0386` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_havel_browser.py | update the phone sheet test |
| App/tests/test_0386_havel_phone_look_browser.py | new |

## 4. Steps

1. **Panel header** (`_havel_panel.html`): in `.havel-head`, change that avatar's icon to `icon('message-circle-question', 20)`. Do not change anything else in the file.

2. **Topics** (`_havel_topics.html`):
   - Home branch (`{% else %}`): delete the `<h2 class="havel-answer-title">` line. Replace the `ui-menu-panel` div with `<div class="ui-chips havel-chips" role="group" aria-label="{{ t('havel.topics_title') }}">`, and each item with `<a class="ui-chip havel-chip" href="/havel?topic={{ tp.id }}" data-havel-topic-link>{{ icon(tp.icon, 16) }}{{ t(tp.label) }}</a>` (no grow span, no chevron).
   - Topic branch (`{% elif havel_topic_data %}`): keep the back link but make it `class="ui-chip havel-chip-back"` (keep its href, `data-havel-topic-link`, chevron-left icon and text). Replace the `<h2 class="havel-answer-title">` with a host bubble: `<div class="havel-msg havel-msg-host"><span class="sr-only">{{ t('havel.you') }}: </span><div class="havel-bubble"><p>{{ t(havel_topic_data.label) }}</p></div></div>`. Replace the `ui-menu-panel` with the same `ui-chips havel-chips` group, with chips `<a class="ui-chip havel-chip" href="/havel?topic={{ havel_topic }}&q={{ q.id }}" data-havel-topic-link>{{ t(q.label) }}</a>`.
   - Answer branch (`{% if havel_answer %}`): make the back link `class="ui-chip havel-chip-back"` the same way. Replace `<h2 class="havel-answer-title">{{ t(havel_answer.question.label) }}</h2>` with the same host-bubble markup, showing `t(havel_answer.question.label)`. Leave the answer bubble, `.havel-links` and `.havel-ask` as they are, but change `havel-ask` from `ui-btn ui-btn-secondary` to `ui-chip havel-chip`.
   - Every link keeps `data-havel-topic-link` and its href, so `/havel` works without JavaScript and `test_havel_topics.py` (5 topic links) still passes.

3. **Follow-up questions** (`_havel_thread.html`): in `[data-havel-next]`, change the buttons from `ui-btn ui-btn-secondary ui-btn-compact` to `ui-chip havel-chip`, and wrap them in `<div class="ui-chips havel-chips">...</div>` after the `<p class="havel-meta">`. Keep `type="submit" name="message" value="{{ q }}"`.

4. **Composer** (`_havel_form.html`). Keep every hidden input as is. Replace everything from `{% if havel_state %}` to the end of the form (the `havel-note` line included) with:
```jinja
  {% if havel_state %}
  <p class="havel-meta havel-status">{{ t('havel.' ~ havel_state) }}</p>
  <a class="ui-btn ui-btn-secondary havel-support-open" href="/havel?topic=wrong&q=error" data-havel-topic-link>{{ icon('mail', 16) }}{{ t('havel.write_support') }}</a>
  {% else %}
  <label for="havel-message" class="sr-only">{{ t('havel.placeholder') }}</label>
  <div class="havel-input">
    <textarea id="havel-message" name="message" rows="1" maxlength="{{ havel_max }}" placeholder="{{ t('havel.placeholder') }}" required{% if havel_error %} aria-invalid="true" aria-describedby="havel-error"{% endif %}></textarea>
    <button class="ui-btn ui-btn-primary ui-btn-icon havel-send" type="submit" data-havel-send aria-label="{{ t('havel.send') }}">{{ icon('arrow-up', 20) }}</button>
  </div>
  {% if havel_error %}<p id="havel-error" class="havel-error">{{ havel_error }}</p>{% endif %}
  {% if not havel_fresh %}<div class="havel-actions"><button class="ui-btn ui-btn-quiet ui-btn-compact" type="submit" name="reset" value="1" formnovalidate>{{ t('havel.new') }}</button></div>{% endif %}
  <p class="havel-meta havel-note">{{ t('havel.ai_note') }}</p>
  {% endif %}
</form>
```
   Add `{% from "_icons.html" import icon with context %}` at the top of the file if it is not there. `_icons.html` has no `'arrow-up'` or `'mail'` entry: add each one from Lucide 0.552.0 (arrow-up: `<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>`; mail: `<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/>`), next to `'send'`. Check the topic link in the off state: `wrong`/`error` must exist in `havel_topics.py` (it does, with `"support": True`).

5. **Copy** (host_i18n.py en and cs dicts, host_vi_i18n.py). Change the values, and add `havel.write_support` next to `havel.off` in all three:

| key | en | cs | vi |
|---|---|---|---|
| havel.off | Chat is paused right now. Quick answers above still work. | Chat je teď pozastavený. Rychlé odpovědi výše fungují dál. | Trò chuyện đang tạm dừng. Các câu trả lời nhanh ở trên vẫn dùng được. |
| havel.ai_note | AI can be wrong. Don't share passwords or guests' ID numbers. | AI se může mýlit. Nepište hesla ani čísla dokladů hostů. | AI có thể sai. Đừng chia sẻ mật khẩu hay số giấy tờ của khách. |
| havel.placeholder | Ask Havel anything | Zeptejte se Havla na cokoli | Hỏi Havel bất cứ điều gì |
| havel.write_support (new) | Write to support | Napsat podpoře | Viết cho bộ phận hỗ trợ |

   If any test asserts the old text of these keys, update that assertion to the new text (grep `tests/` for "unavailable right now", "can make mistakes", "Write your question here", and the cs/vi equivalents).

6. **havel.js**:
   - In `bindCounter()`, change `ta.insertAdjacentElement("afterend", counter);` to `(ta.closest(".havel-input") || ta).insertAdjacentElement("afterend", counter);`.
   - In the same function, after the `input` listener, add an auto-grow:
```js
    function grow() { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 132) + "px"; }
    ta.addEventListener("input", grow);
```
   - `send()` already does `ta.value = ""; ta.dispatchEvent(new Event("input"));` (~line 198), so the height resets by itself. Check it, change nothing there.

7. **CSS**: append ONE block at the end of host2.css. Do not edit the old rules. Later rules win at equal specificity, and the two `!important` rules need the higher specificity shown:
```css
/* 0386: Havel looks like a support chat (owner 2026-10-25, benchmark Wolt).
   Chips instead of a menu, a pill composer, no ring on script focus, tall phone sheet. */
.host-workspace .havel-head h2[tabindex="-1"]:focus-visible,
.host-workspace .havel-msg[tabindex="-1"]:focus-visible,
.host-workspace .havel-answer[tabindex="-1"]:focus-visible { outline: none !important; box-shadow: none; }
.host-workspace .havel-head .havel-avatar { width: calc(var(--space-8) + var(--space-1)); height: calc(var(--space-8) + var(--space-1)); background: var(--accent); color: var(--on-accent); }
.host-workspace .havel-head { border-bottom-color: var(--line); padding-bottom: var(--space-3); }
.host-workspace .havel-msg-havel .havel-bubble { background: var(--surface-2); border: 0; }
.host-workspace .havel-msg-host .havel-bubble { background: var(--accent); color: var(--on-accent); }
.host-workspace .havel-chips { gap: var(--space-2); }
.host-workspace .havel-chip { height: auto; min-height: var(--control-h); padding: var(--space-2) var(--space-4); background: var(--surface); color: var(--accent-ink); border: 1px solid var(--accent-soft); font-weight: 600; text-align: left; white-space: normal; }
.host-workspace .havel-chip:hover { background: var(--accent-soft); color: var(--accent-ink); }
.host-workspace .havel-chip-back { align-self: flex-start; background: transparent; color: var(--ink-2); padding-left: var(--space-2); }
.host-workspace .havel-next .havel-chips, .host-workspace .havel-topics .havel-chips { margin-top: var(--space-1); }
.host-workspace .havel-composer { gap: var(--space-2); padding-top: var(--space-3); }
.host-workspace .havel-input { display: flex; align-items: flex-end; gap: var(--space-2); padding: var(--space-1) var(--space-1) var(--space-1) var(--space-4); border-radius: var(--radius-pill); background: var(--surface-2); }
.host-workspace .havel-input:focus-within { box-shadow: var(--focus-ring-2); }
.host-workspace .havel-composer .havel-input textarea { flex: 1 1 auto; min-height: 0; height: var(--control-h); padding: var(--space-2) 0; border: 0; border-radius: 0; background: transparent; resize: none; line-height: 1.5; }
.host-workspace .havel-composer .havel-input textarea:focus-visible, .host-workspace .havel-composer .havel-input textarea:focus { outline: none !important; box-shadow: none; }
.host-workspace .havel-send { flex: none; width: var(--control-h); height: var(--control-h); border-radius: var(--radius-pill); }
.host-workspace .havel-actions { justify-content: flex-start; }
.host-workspace .havel-note { text-align: center; }
.host-workspace .havel-status { text-align: center; }
.host-workspace .havel-support-open { width: 100%; justify-content: center; border-radius: var(--radius-pill); min-height: var(--control-h-phone); }
@media (max-width: 767px) {
  .host-workspace .havel-dialog { inset: var(--space-12) 0 0 0; height: auto; z-index: var(--z-drawer); }
  .host-workspace .havel-dialog .ui-sheet { height: calc(100dvh - var(--space-12)); max-height: none; padding-bottom: calc(var(--space-2) + env(safe-area-inset-bottom)); }
  .host-workspace .havel-composer textarea { font-size: var(--size-16); }
}
```
   `--size-16` keeps iOS from zooming into the input. Check `--focus-ring-2`, `--on-accent`, `--accent-soft`, `--accent-ink`, `--surface-2`, `--radius-pill` exist (grep tokens.css). Do not add any raw colour.

8. **Catalog**: add `havel-chips`, `havel-chip`, `havel-chip-back`, `havel-input`, `havel-send`, `havel-status`, `havel-support-open` to `docs/design/catalog.json` `"classes"`, after `"havel-composer"`.

9. **Version keys**: bump `host2.css` and `havel.js` `?v=` in base.html to `20261025-0386`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write`.

10. **Old test** (`test_havel_browser.py::test_phone_launcher_and_sheet`): replace the three lines after `sheet = ...bounding_box()` (the 70% height, bottom above tab bar, tab bar hit-test) with:
```python
        assert sheet["width"] == 390 and sheet["height"] >= 900 - 48 - 2
        assert sheet["y"] <= 48 + 1
```
   Keep everything else in that test.

11. **New test** `App/tests/test_0386_havel_phone_look_browser.py`. Model the server, sign-in and `_context` on `test_havel_browser.py` (import its fixtures and helpers or copy the smallest part). Start with `sync_api = pytest.importorskip("playwright.sync_api")`. Shots go to `docs/tasks/screenshots-0386/`. Tests, all at 390 px unless named:
   - `test_no_ring_on_open`: open the sheet with the corner button. `#havel-title` is focused and its computed `outline-style` is `none`. Save `home-390.png` (page screenshot).
   - `test_topics_are_chips`: in the open sheet, `.havel-chip[data-havel-topic-link]` count is 5, and there is no `.ui-menu-panel` inside `#havel-sheet`. Two chips' boxes sit in the left half or wrap (just assert every chip's right edge ≤ 390 and its height ≥ 40). Tap the first chip, then wait for `.havel-msg-host` to show the topic label. Save `topic-390.png`. Tap the first question chip, wait for `.havel-answer`, and check there is one `.havel-msg-host` with the question text. Save `answer-390.png`.
   - `test_pill_composer`: `.havel-input #havel-message` and `.havel-input .havel-send` exist. The send box is inside the input box. Fill 6 lines of text (`"line\n" * 6`). The textarea height grows but stays ≤ 132. `document.documentElement.scrollWidth <= 390`.
   - `test_off_state_has_support_button`: switch Havel off the way existing tests do (grep `test_havel_*.py` for how they set the "off" state, e.g. monkeypatching `ai.enabled_for` or the `UBYHOST_AI_FEATURES` env var). Open the sheet: no `#havel-message`, no `.havel-note`, one `.havel-support-open`. Click it, then `[data-havel-support]` becomes visible. Save `off-390.png` before the click.
   - `test_cs_home_1280`: at 1280 px with `?lang=cs`, open the panel; 5 chips; save `home-cs-1280.png` (the computer panel must still look right).

## 5. Do not touch

Everything outside §3. No change to routes, havel.py, prompts, limits or cards (`_havel_card.html`). Do not change the desktop panel size or place.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0386_havel_phone_look_browser.py tests/test_havel_browser.py tests/test_havel_topics.py tests/test_havel_panel.py tests/test_havel_page.py tests/test_havel_support.py tests/test_havel_support_browser.py tests/test_havel_cards_browser.py tests/test_havel_launcher_skeleton_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_*.py tests/test_dev_ui.py tests/test_send_controls.py tests/test_stay_fee_detail.py -q --tb=short 2>&1 | tail -15
cd .. && python3 scripts/design_lint.py 2>&1 | tail -3 && git checkout -- $(git ls-files -m docs/tasks | grep -v 0386 | grep screenshots- ) 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only if the cause is in a file from §3; otherwise stop.

## 7. Acceptance

- [ ] All §6 commands pass, or the failure is in the report.
- [ ] Screenshots home-390, topic-390, answer-390, off-390, home-cs-1280 are in `docs/tasks/screenshots-0386/`.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0386-report.md` (200 tokens), `Status: review`. One commit `0386: Havel looks like a support chat on the phone`, including this brief and the screenshots. Do not push.
