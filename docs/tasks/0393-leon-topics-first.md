# 0393: Leon starts with topics, "Other question" opens the box; brief premium-concierge voice

Status: blocked (see docs/tasks/0393-report.md)
Depends on: main (0387-0390 merged) | Branch: claude/0393-leon-topics-first (checked out in /home/claude/wt-leon; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "Also make Leon start with topics first and other if they want to ask", and: "make him answer brief and direct, but he has a different personality: he needs to sound like a premium concierge but still brief." Same idea as Havel's 0391/0392.

1. When the chat has no stored messages, Leon's welcome bubble and the situation chips show, and **no text box**. The chips get a new last chip **"Other question"** that is always there.
2. "Other question": the guest bubble says "Other question", Leon answers with a fixed bubble "Of course. Write your question below and I'll take care of it.", and the text box appears, focused. Like the chips, this exchange is drawn by the page only: never sent, stored or counted.
3. Once the box is open it stays open on this page. If the stay already has stored messages (history from the server), the box shows from the start.
4. Leon's model replies get shorter, with a premium-concierge voice (prompt change in `leon.py` CHARACTER).

## 2. Context

- `App/app/templates/guest/_leon.html`: the chat section; `<ul hidden data-leon-situations>` lists the chips; the form `[data-leon-form]` starts `hidden` and `guest-leon.js` sets `form.hidden = false` at the end of the file.
- `App/app/static/guest-leon.js`: `welcome()` draws the welcome bubble and the chips (`chips(topics(), answerSituation, "")`); `answerSituation(tp)` answers a chip and redraws the chips; `render(data)` empties the log, calls `welcome()`, re-adds `local` nodes, then `data.messages`. Text is set with `textContent` only: keep that.
- `App/app/leon.py` `CHARACTER` (~66-100): bullets under "YOUR CHARACTER", the "Brief." bullet ~79.
- Copy: `App/app/i18n.py` (en, cs, de, es, fr; Leon keys near `leon_sit_emergency_help`) and `App/app/guest_uk_i18n.py` (uk).
- CSS: reuse `.g-leon-chip`; no CSS change expected.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/guest/_leon.html | 2 data attributes |
| App/app/static/guest-leon.js | "Other question" chip, box locked until opened |
| App/app/leon.py | CHARACTER edits only |
| App/app/i18n.py, App/app/guest_uk_i18n.py | 2 new keys × 6 languages |
| App/app/templates/guest/base.html | bump guest-leon.js key to `?v=20261025-0393` |
| App/tests/static_versions.json | `.venv/bin/python tests/test_static_versions.py --write` |
| App/tests/test_guest_leon_browser.py | new test + adapt tests that type on a fresh chat |
| App/tests/test_leon.py | only if a test pins the changed CHARACTER sentences |

## 4. Steps

1. **Copy**, after `leon_sit_emergency_help` in each language:

| key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| leon_sit_other | Other question | Jiný dotaz | Andere Frage | Otra pregunta | Autre question | Інше питання |
| leon_other_prompt | Of course. Write your question below and I'll take care of it. | Samozřejmě. Napište svůj dotaz níže a postarám se o to. | Selbstverständlich. Schreiben Sie Ihre Frage unten, ich kümmere mich darum. | Por supuesto. Escriba su pregunta abajo y yo me encargo. | Bien sûr. Écrivez votre question ci-dessous, je m'en occupe. | Звісно. Напишіть своє питання нижче, і я про все подбаю. |

2. **Template** (`_leon.html`): on the root section add `data-text-other="{{ t('leon_sit_other') }}"` and `data-text-other-prompt="{{ t('leon_other_prompt') }}"`.

3. **JS** (`guest-leon.js`):
   - Add `var opened = false;` near the other state vars, and:
     ```js
     // 0393: the box opens with "Other question" or when the stay already has messages.
     function openBox(focus) {
       opened = true;
       form.hidden = false;
       if (focus) input.focus();
     }
     function askOther() {
       Array.prototype.forEach.call(log.querySelectorAll(".g-leon-chips"), function (n) {
         log.removeChild(n);
         local = local.filter(function (x) { return x !== n; });
       });
       keep(bubble("guest", "", text("text-other")));
       keep(bubble("leon", "", text("text-other-prompt")));
       openBox(true);
     }
     ```
   - `topicChips()` and the chips call in `welcome()`: append an "Other question" item that calls `askOther` instead of `answerSituation`. Do it inside `chips()` callers, e.g. pass `topics().concat([{ title: text("text-other"), other: true }])` and in the click handler use `it.other ? askOther() : onPick(it)`. The welcome chips must show even when `topics()` is empty (today `if (!local.length && tp.length)`; drop the `tp.length` condition since "Other question" is always there).
   - `render(data)`: after drawing `data.messages`, `if ((data.messages || []).length) openBox(false);`.
   - At the end of the file replace `form.hidden = false;` with nothing (the form stays hidden until `openBox`). If `jump` (the "Ask Leon" link elsewhere on the page) should focus the input, leave it as is.
   - On submit nothing changes.

4. **Prompt** (`leon.py` CHARACTER). Exactly these edits, nothing else:
   - Replace the line `YOUR CHARACTER: the best hotel concierge in the world, kind, quick, understanding and helpful.` with `YOUR CHARACTER: the concierge of a five-star hotel: polished, gracious, quick and discreet.`
   - Insert a new bullet right after that line: `- Premium but brief. Sound composed and courteous, never chatty. You may open with one short courtesy ("Of course.", "Certainly.", "With pleasure.") at most once per reply, and never when something is wrong. Keep the whole reply to about 40 words plus the card's steps.`
   - In the "Answers first." bullet replace `Steps follow, one per line, exactly as the host wrote them.` with `Give steps only when the guest needs to do something: one per line, exactly as the host wrote them, at most four; if the card has more, give the first ones and say the rest is on that card on this page.`
   - Run `grep -rn "best hotel concierge\|Steps follow, one per line" App/tests` and update any test that pins the old text.

5. **Version key**: `templates/guest/base.html` guest-leon.js `?v=20261025-0393`, then `.venv/bin/python tests/test_static_versions.py --write`.

6. **Tests** (`tests/test_guest_leon_browser.py`):
   - grep `data-leon-input\|leon-message` in that file and `tests/test_guest_*browser*.py`: where a test types into the box on a fresh chat, first click the chip with text "Other question" (`.g-leon-chip` has_text) and wait for the input to be visible.
   - New test `test_leon_other_question_opens_box` (same seed and phone setup as the 0390 chips test, en, 390x844): before any action `[data-leon-input]` is not visible and the last `[data-leon-welcome-chips] .g-leon-chip` is "Other question"; tap it: a guest bubble "Other question", a Leon bubble with the `leon_other_prompt` text, the input is visible and focused, and no request went to the Leon URL (count requests as the 0390 test does). Then type "Hello" + Enter and check the input stays visible. `scrollWidth <= 390`. Save `#leon` screenshots `leon-topics-first-390.png` (before) and `leon-other-390.png` (after the tap) to `docs/tasks/screenshots-0393/`.

## 5. Do not touch

Caps, MAX_* values, routes, stored history, the guide cards, Havel files, CSS (unless the screenshot shows the new chip broken; then report instead).

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
node --check app/static/guest-leon.js
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_leon_chat.py tests/test_leon.py tests/test_guest_guide_browser.py tests/test_guest_browser_e2e.py tests/test_guest_languages.py tests/test_static_versions.py -q --tb=short -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep screenshots- | grep -v screenshots-0393) 2>/dev/null; python3 scripts/context_lint.py 2>&1 | tail -3
```
If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped; context lint OK.
- [ ] Both screenshots exist and you looked at each once: welcome + chips ending in "Other question" with no box; then the prompt bubble with the box.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0393-report.md` (same shape as `docs/tasks/0387-report.md`) and set this brief's Status to done. ONE commit `0393: Leon starts with topics, brief premium-concierge voice`, including this brief, the report and the screenshots, ending with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_017GNdySPNU4QowPqKkDneew`. Do not push.
