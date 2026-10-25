# 0391: Havel starts with topics; the text box opens only after "Other topic" or "Didn't help? Ask Havel"

Status: done
Depends on: main (0386 phone look merged) | Branch: claude/0391-havel-topics-first (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "force the user to first pick one of the topics and then if it won't help then they can click to ask Havel, or even put Other topic there so they can talk to Havel right away", and: "if they click other, automatically like write your issue and Havel will look into it".

1. When Havel opens with an empty chat, there is **no text box**. Only the greeting and the topic chips show, plus a new last chip **"Other topic"**.
2. "Other topic": the host's bubble says "Other topic", Havel answers with a fixed bubble "Write your issue in a few words and Havel will look into it.", and the text box appears, focused.
3. After a topic's guided answer, the existing chip (`havel.topic.ask`, now worded "Didn't help? Ask Havel") shows under the answer. Tapping it adds Havel's fixed bubble "What is still unclear? Write it below and Havel will look into it." and the text box appears, focused. The topic and question still travel with the message as today.
4. Once the host has sent a message, the text box stays for the rest of the chat, also across page changes (sessionStorage restore). "New chat" (reset) brings back the topics and hides the box again.
5. AI off or a limit hit: the composer area today shows the status line and "Write to support". It stays hidden until "Other topic" or "Didn't help?" is tapped, then shows as today. No prompt bubble in that case (the status line already explains).
6. Without JavaScript (/havel page) it works the same through links with `ask=1`.

No backend greeting change (`havel.intro` stays). No look change: same chips, bubbles, pill composer from 0386.

## 2. Context

- `App/app/routes/havel.py`: `havel_page` (GET, ~135) and `havel_send` (POST, ~176) both build the context with `_page_context(...)` (~108).
- `App/app/templates/_havel_topics.html`: three branches (answer / topic questions / topic list). The answer branch has the `data-havel-ask` chip, today shown only `if not havel_state`.
- `App/app/templates/_havel_form.html`: the `<form data-havel-form>` composer (status + support link when `havel_state`).
- `App/app/templates/_havel_panel.html`: the panel dialog; `data-src` is the URL `ensureForm()` fetches on first open (has `page` and `return_to`).
- `App/app/static/havel.js`: `load(url, mode)` fetches topic links (`[data-havel-topic-link]`) and swaps the fragment (thread + form wrap). `save()`/`restore()` keep the chat in sessionStorage; the form is re-fetched from `data-src` on every page, so its open/closed state must be saved too. `focusPanel()`, `window.UbyHavel.open`.
- `app.css:853` has `[hidden] { display: none !important; }`, so the `hidden` attribute is enough to hide the form.
- Copy: `App/app/host_i18n.py` (en ~1586, cs ~3220), `App/app/host_vi_i18n.py` (vi ~3368). Grep for any other language dict that holds `havel.topic.ask` and add the keys there too.
- Icons: `_icons.html` has `pencil`.

## 3. Files

| Path | Action |
|---|---|
| App/app/routes/havel.py | `ask` flag, `havel_locked`, `havel_ask` in context |
| App/app/templates/_havel_form.html | `hidden` when locked |
| App/app/templates/_havel_topics.html | "Other topic" chip, ask branch, prompt bubbles, ask chip href |
| App/app/static/havel.js | focus after an ask load, keep page/return_to, save/restore open composer, focusPanel, UbyHavel.open |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | 3 new keys, 1 changed |
| App/app/templates/base.html | bump havel.js key to `?v=20261025-0391` |
| App/tests/static_versions.json | `tests/test_static_versions.py --write` |
| App/tests/test_0391_havel_topics_first_browser.py | new test |
| App/tests/test_havel*_browser.py, test_0386_havel_phone_look_browser.py | only where a test types into the box on a fresh chat |

## 4. Steps

1. **Route** (`routes/havel.py`).
   - `_page_context(...)`: add keyword `ask: bool = False`. Add to the returned dict: `"havel_ask": ask` and `"havel_locked": len(exchanges) == 0 and not ask`.
   - `havel_page` (GET): `ask = request.query_params.get("ask") == "1"`, pass `ask=ask`.
   - `havel_send` (POST): pass `ask=form.get("reset") != "1"` to both `_page_context` calls (a host who posted has opened the box; reset closes it).

2. **Form** (`_havel_form.html`): on the `<form ...>` tag add `{% if havel_locked %} hidden data-havel-locked{% endif %}`. Nothing else changes.

3. **Topics** (`_havel_topics.html`).
   - Topic list branch (the last `{% else %}`): after the `{% for tp in havel_topics %}` loop, inside the same chips div, add
     `<a class="ui-chip havel-chip" href="/havel?ask=1" data-havel-topic-link data-havel-other>{{ icon('pencil', 16) }}{{ t('havel.topic.other') }}</a>`
   - The first `{% if havel_answer %}` becomes `{% if havel_answer %}` … then a new branch **before** `{% elif havel_topic_data %}`:
     ```
     {% elif havel_ask %}
     <a class="ui-chip havel-chip-back" href="/havel" data-havel-topic-link>{{ icon('chevron-left', 16) }}{{ t('havel.topic.back') }}</a>
     <div class="havel-msg havel-msg-host"><span class="sr-only">{{ t('havel.you') }}: </span><div class="havel-bubble"><p>{{ t('havel.topic.other') }}</p></div></div>
     {% if not havel_state %}<div class="havel-msg havel-msg-havel havel-answer" tabindex="-1"><div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div><div class="havel-bubble"><p>{{ t('havel.other_prompt') }}</p></div></div>{% endif %}
     ```
   - Answer branch, the ask chip line: replace `{% if not havel_state %}<a ... data-havel-ask ...>{% endif %}` with:
     ```
     {% if havel_ask %}
     {% if not havel_state %}<div class="havel-msg havel-msg-havel" tabindex="-1"><div class="havel-who"><span class="havel-avatar" aria-hidden="true">{{ icon('message-circle-question', 16) }}</span><span class="havel-name">{{ t('havel.name') }}</span></div><div class="havel-bubble"><p>{{ t('havel.ask_prompt') }}</p></div></div>{% endif %}
     {% else %}
     <a class="ui-chip havel-chip" href="/havel?topic={{ havel_topic }}&q={{ havel_q }}&ask=1" data-havel-topic-link data-havel-ask-open>{{ t('havel.topic.ask') }}</a>
     {% endif %}
     ```
     (The chip now shows also when `havel_state` is set, so an off or limited host reaches "Write to support" instead of a dead end.)
   - Leave the greeting condition as is: with `ask=1` and no topic the greeting still shows above "Other topic".

4. **Copy.** Add after `havel.topic.back` and change `havel.topic.ask`:

| key | en | cs | vi |
|---|---|---|---|
| havel.topic.other (new) | Other topic | Jiné téma | Chủ đề khác |
| havel.other_prompt (new) | Write your issue in a few words and Havel will look into it. | Napište v pár slovech, co řešíte, a Havel se na to podívá. | Hãy viết ngắn gọn vấn đề của bạn và Havel sẽ xem xét. |
| havel.ask_prompt (new) | What is still unclear? Write it below and Havel will look into it. | Co zůstává nejasné? Napište to níže a Havel se na to podívá. | Điều gì vẫn chưa rõ? Hãy viết bên dưới và Havel sẽ xem xét. |
| havel.topic.ask (changed) | Didn't help? Ask Havel | Nepomohlo to? Zeptejte se Havla | Chưa giúp được? Hỏi Havel |

   If an i18n completeness test lists keys per language, add the keys wherever it asks.

5. **JS** (`havel.js`).
   - Helper after `textarea()`: `function composerOpen() { var f = form(); return !!(f && !f.hidden); }` and
     `function openComposer() { var f = form(); if (f) { f.hidden = false; f.removeAttribute("data-havel-locked"); } }`.
   - `focusPanel()`: on computer focus the textarea only `if (composerOpen())`; otherwise focus `#havel-title` (as on phone).
   - `load(url, mode)`: (a) when `panel` exists, add the panel's `page` and `return_to` from its `data-src` to `url` if `url` has no `page=` (use `new URL(url, location.origin)` and `URLSearchParams`; build the final string as `u.pathname + u.search`). Today topic links lose them, so Havel gets page "guide" and cards return to /havel. (b) After `swap(...)`: if the url contains `ask=1` and `composerOpen()`, focus the textarea and `scrollDown()`; else keep today's code (focus `.havel-answer`, scrollTop 0).
   - `save()`: add `composer: composerOpen() || (!form() && prev.composer === true)` to `rec`.
   - `restore()` → inside `apply`, after `fill(s)`: `if (s.composer) openComposer();`.
   - `window.UbyHavel.open`: call `openComposer()` before reading the textarea.
   - Remove the now-unused `[data-havel-ask]` click handler block only if nothing renders `data-havel-ask` any more (grep templates first).

6. **Version key**: `templates/base.html` havel.js `?v=20261025-0391`, then `.venv/bin/python tests/test_static_versions.py --write` (check the file's docstring for the exact command).

7. **Existing tests**: grep `havel-message` in `tests/test_havel*_browser.py` and `tests/test_0386_havel_phone_look_browser.py`. Where a test types into the box on a fresh chat, first click `[data-havel-other]` (or load `/havel?ask=1` for the page view) and wait until `#havel-message` is visible. Do not weaken any assertion. Non-browser tests that GET `/havel` and look for the textarea still pass (the form is in the HTML, only hidden); if one asserts it is visible, add `?ask=1`.

8. **New test** `tests/test_0391_havel_topics_first_browser.py` (copy the fixture/seed pattern, the `importorskip` line and the rate-limit cleanup from `test_0386_havel_phone_look_browser.py`; Havel on, fake AI client as that file does). en, run at 390x844 and 1280x800:
   - Open the panel from the corner button: `#havel-message` is not visible; `[data-havel-other]` is visible and is the last chip.
   - Tap a topic, then a question: the answer shows, `#havel-message` still not visible, the chip "Didn't help? Ask Havel" is visible. Tap it: a bubble with the `havel.ask_prompt` text shows and `#havel-message` is visible and focused.
   - New chat via the panel's reset (or clear sessionStorage and reload): tap "Other topic": a host bubble "Other topic", a Havel bubble with the `havel.other_prompt` text, `#havel-message` visible and focused. Type "How do I add a stay?" + Enter: the fake reply shows.
   - Navigate to another host page (e.g. `/apartments`): the panel is restored and `#havel-message` is visible.
   - Non-JS check with the test client: `GET /havel` HTML has `data-havel-locked`; `GET /havel?ask=1` does not and contains the `havel.other_prompt` text.
   - `document.documentElement.scrollWidth <= viewport width`.
   - Screenshots of the panel (390: `topics-390.png`, `other-390.png`, `answer-ask-390.png`; 1280: `topics-1280.png`) to `docs/tasks/screenshots-0391/`.

## 5. Do not touch

havel.py (model call, caps, prompt), havel_topics.py, the look (CSS) from 0386, Leon files, `havel.intro`.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
node --check app/static/havel.js
.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0391_havel_topics_first_browser.py tests/test_0386_havel_phone_look_browser.py tests/test_havel*.py tests/test_ai*.py tests/test_static_versions.py tests/test_design_*.py -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep screenshots- | grep -v screenshots-0391) 2>/dev/null; true
```
If `scripts/design_lint.py` lives elsewhere, find it with `ls ../scripts`. If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] The four screenshots exist and you looked at each once: topics with "Other topic" and no box; Other prompt with the box; answer with "Didn't help?" then box.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

No report file. ONE commit `0391: Havel starts with topics, box after Other topic or Didn't help`, including this brief and the screenshots, ending with the Haiku Co-Authored-By trailer and `Claude-Session: https://claude.ai/code/session_017GNdySPNU4QowPqKkDneew`. Do not push.
