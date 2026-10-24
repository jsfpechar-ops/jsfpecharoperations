# 0332: Havel (AI): several requests in one message, the "You can ask next" buttons

Status: todo
Depends on: 0324, 0314 (0325 for the vi key file; it is a one-line fallback if 0325 is not merged) | Base commit: de76c71 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0332-havel-next-requests
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 45k tokens

## 1. Objective

When a host asks for several things in one message, Havel handles the first and returns the rest in `next` (0311, plan 9a). This brief shows those entries as buttons under the newest Havel reply; a tap sends that text as the host's next message, with or without JavaScript, and counts as a normal message.

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` section 4 (block "WHEN THE HOST ASKS FOR SEVERAL THINGS AT ONCE"), 5 (`next`), 9a (row "Next"), 13 (cases 55 to 58, 75), 17d. Rules: AGENTS.md 6 (works without JavaScript), 7 (browser test at 390 px, 0 skipped, one screenshot), 9 (one copy key, three languages). MASTER 7.1 (buttons: `ui-btn ui-btn-secondary ui-btn-compact`).

From 0311: `havel.Reply.next: List[str]` (at most 3 clean strings, empty for refuse and fail). From 0312 and 0314 (`grep -n` each before editing; STOP if one is missing):

- `App/app/routes/havel.py`: `def _item(role: str, text: str, **extra: Any)` builds a dict with `"card": None` before `item.update(extra)`; the reply line
  `items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",` followed by `support_summary=reply.support_summary, card=card))` (0314 step c).
- `App/app/templates/_havel_thread.html`: the links block ends with the line `    {% endif %}` directly after the `havel.support.mailto` anchor line; the next line is `  </div>` closing `.havel-msg-havel`. The template has `havel_history`, `havel_history_sig`, `havel_page`, `havel_return_to` and `csrf_token` in its context (0312 `_page_context`).
- `App/app/static/havel.js` (0324, edited by 0314): `function swap(html, mode)` with `if (replace) t.innerHTML = "";` and `var old = t.querySelector("[data-havel-topics]");`; `function echo(text)`; `function send(extra)` (with `extra`, it does not echo); the submit listener starts `root.addEventListener("submit", function (event) {` and its first lines are `var f = event.target.closest ? event.target.closest("[data-havel-form]") : null;` / `if (!f) return;`.
- `App/app/host_i18n.py`: en line `        "havel.support.mailto": "E-mail support",` and cs line `        "havel.support.mailto": "Napsat podpoře e-mail",`. `App/app/host_vi_i18n.py`: `    "havel.support.mailto": "Gửi e-mail cho hỗ trợ",` (if 0325 is not merged, the vi key is added to `host_vi_i18n.py` after `    "stay_fees.pay.add_account": "Thêm tài khoản",` instead).
- `App/app/templates/base.html`: `host2.css?v=20261024-0314` and `havel.js?v=20261024-0314` (0314 step 9; if the dates differ, use what `grep -n 'host2.css?v=\|havel.js?v=' App/app/templates/base.html` prints).
- Tests: `App/tests/test_havel_page.py` has `_post(client, data, headers=None)`, `ANSWER`, the `host` fixture and `from tests.ai_fake import FakeClient, reply`. `App/tests/test_havel_browser.py` (0324) has `origin`, `_context(pw, origin, width, js=True)`, `SHOTS`, `ANSWER`.

Why mini-forms and not `form="havel-form"`: `_havel_form.html` is rendered twice on `/havel` (the page and the panel in `base.html`), so one form id would be duplicated and a `form=` attribute would point at the wrong composer. Each next block is its own small form; JavaScript intercepts it and sends through the live composer instead.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/havel.py | edit | pass `next=reply.next` into the item; `_item` default |
| App/app/templates/_havel_thread.html | edit | the next block |
| App/app/static/havel.js | edit | tap handling, remove old blocks |
| App/app/static/host2.css | edit | `.havel-next` |
| App/app/templates/base.html | edit | cache keys |
| App/app/host_i18n.py | edit | `havel.next_title` en, cs |
| App/app/host_vi_i18n.py | edit | `havel.next_title` vi |
| App/tests/test_havel_page.py | edit | one unit test |
| App/tests/test_havel_browser.py | edit | one browser test at 390 |
| docs/tasks/screenshots-0332/next-390.png | new | screenshot |

No other file may change.

## 4. Steps

Commit after each step: `0332 step k`.

1. **Branch and anchors.** `git fetch origin && git checkout -b task/0332-havel-next-requests origin/main` (0314 merged; else from `origin/task/0314-havel-action-cards`). Then `grep -n 'card=card))' App/app/routes/havel.py; grep -n "havel.support.mailto" App/app/templates/_havel_thread.html App/app/host_i18n.py App/app/host_vi_i18n.py; grep -n 'function swap\|function echo\|data-havel-topics\|closest("\[data-havel-form\]")' App/app/static/havel.js; grep -n 'next' App/app/havel.py | head -5`. Expected: one hit each (two for `data-havel-topics`), and `havel.py` mentions `next`. If `Reply` has no `next`, STOP (0311 was merged before this plan change; report it).

2. **Route.** In `App/app/routes/havel.py`, in `_item`, add `"next": [],` directly before `"card": None` in the dict it builds. Then change the two-line `items.append(_item("havel", reply_text, ...` call so its last line reads `support_summary=reply.support_summary, card=card, next=reply.next))`. Command: `cd App && .venv/bin/python -c "from app.main import app" && grep -c 'next=reply.next' app/routes/havel.py`. Expected: no error, `1`.

3. **Template.** In `_havel_thread.html`, directly after the `    {% endif %}` that closes the `havel-links` block (the one after the `havel.support.mailto` line) and before `  </div>`, insert:

```jinja
    {% if item.next %}
    <form method="post" action="/havel" class="havel-next" data-havel-next>
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <input type="hidden" name="history" value="{{ havel_history }}">
      <input type="hidden" name="history_sig" value="{{ havel_history_sig }}">
      <input type="hidden" name="page" value="{{ havel_page }}">
      <input type="hidden" name="return_to" value="{{ havel_return_to }}">
      <p class="havel-meta">{{ t('havel.next_title') }}</p>
      {% for q in item.next %}<button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" name="message" value="{{ q }}">{{ q }}</button>{% endfor %}
    </form>
    {% endif %}
```

   The button posts `message=<its text>`, so the route needs no new field and the host's tap is an ordinary message (counted, limited, redacted). `next` is set only on the newest reply (`_thread` rebuilds older turns from the history without it), so older blocks vanish on a full render. Without JavaScript the form has no `device` field; the route defaults to "computer", which is acceptable for the no-JS path.

4. **Copy.** `host_i18n.py`: after the en `havel.support.mailto` line add `        "havel.next_title": "You can ask next:",`; after the cs one add `        "havel.next_title": "Můžete se dál zeptat:",`. `host_vi_i18n.py`: after its `havel.support.mailto` line add `    "havel.next_title": "Bạn có thể hỏi tiếp:",`. Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.translate('en','havel.next_title'), '|', h.translate('cs','havel.next_title'), '|', h.translate('vi','havel.next_title'))"`. Expected: `You can ask next: | Můžete se dál zeptat: | Bạn có thể hỏi tiếp:`.

5. **havel.js.** Three edits:

   a. In `swap`, directly after `var old = t.querySelector("[data-havel-topics]");` add:

```js
      if (!replace) t.querySelectorAll("[data-havel-next]").forEach(function (n) { n.remove(); });
```

   b. In the submit listener, directly after `root.addEventListener("submit", function (event) {` and before the `var f = ...` line, add:

```js
    var nf = event.target.closest ? event.target.closest("[data-havel-next]") : null;
    if (nf) {
      event.preventDefault();
      var picked = event.submitter && event.submitter.value;
      if (!picked) return;
      nf.remove();
      echo(picked);
      send({ message: picked });
      return;
    }
```

   c. `send(extra)` already sets `message` from `extra` on the live composer's FormData (current history and device) and appends the fragment. Nothing else changes.

   Bump the key in `base.html`: `havel.js?v=20261024-0314` → `havel.js?v=20261024-0332`. Command: `node -e "new Function(require('fs').readFileSync('App/app/static/havel.js','utf8'))" && grep -c 'havel.js?v=20261024-0332' App/app/templates/base.html` from the repo root. Expected: no error, `1`.

6. **CSS.** Append to the very end of `App/app/static/host2.css`:

```css
/* 0332: Havel "You can ask next" buttons under the newest reply */
.havel-next { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.havel-next .havel-meta { flex-basis: 100%; margin: 0; }
.havel-next .ui-btn { max-width: 100%; white-space: normal; text-align: left; }
```

   Then `sed -i 's/host2.css?v=20261024-0314"/host2.css?v=20261024-0332"/' App/app/templates/base.html && grep -c 'host2.css?v=20261024-0332"' App/app/templates/base.html` (expected `1`), `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`, and from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3` (expected OK).

7. **Unit test.** Append to `App/tests/test_havel_page.py`:

```python
NEXT = {**ANSWER, "reply": "Two things: the guest link, and a stay. Open Guest links first.",
        "next": ["Add a stay at Vinohrady flat Friday to Sunday for 2", "Sync my calendars"]}


def test_next_requests_render_as_buttons_only_on_the_newest_reply(host):
    ai.set_client_for_tests(FakeClient([reply(NEXT), reply(ANSWER)]))
    page = _post(host, {"message": "Guest link and a stay Friday to Sunday for 2 and sync"}).text
    assert page.count("data-havel-next") == 1 and "You can ask next:" in page
    assert 'name="message" value="Sync my calendars"' in page and page.count('class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" name="message"') == 2
    history = re.search(r'data-havel-next.*?name="history" value="([^"]*)"', page, re.S).group(1)
    sig = re.search(r'data-havel-next.*?name="history_sig" value="([^"]*)"', page, re.S).group(1)
    again = _post(host, {"message": "Sync my calendars", "history": html.unescape(history), "history_sig": sig}).text
    assert "data-havel-next" not in again and again.count('class="havel-msg havel-msg-host"') == 2
```

   Add `import html` to the imports if it is missing. Command: `cd App && .venv/bin/python -m pytest tests/test_havel_page.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

8. **Browser test and screenshot** (rule 7). Append to `App/tests/test_havel_browser.py`:

```python
NEXT = {**ANSWER, "reply": "Two things. Open Guest links first.", "next": ["Sync my calendars", "What does the red badge mean?"]}


def test_phone_next_buttons_send_the_tapped_request(origin):
    SHOTS_0332 = SHOTS.parent / "screenshots-0332"
    SHOTS_0332.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(NEXT), reply(ANSWER)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/havel")
        page.locator("#havel-message").fill("guest link, sync and the red badge")
        page.keyboard.press("Enter")
        page.locator("[data-havel-next]").wait_for()
        buttons = page.locator("[data-havel-next] button")
        assert buttons.count() == 2 and buttons.first.bounding_box()["height"] >= 36
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.screenshot(path=str(SHOTS_0332 / "next-390.png"))
        buttons.first.click()
        page.locator(".havel-msg-havel:not([data-havel-writing])").nth(2).wait_for()
        assert page.locator("[data-havel-next]").count() == 0
        assert page.locator(".havel-msg-host").nth(1).inner_text().strip() == "Sync my calendars"
        browser.close()
```

   If `/havel` opens the panel over the page (it should not; the launcher is only on other pages), use the page's `[data-havel-thread]` instead and note it. Commands, from `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`: `.venv/bin/python -m pytest tests/test_havel_browser.py -q 2>&1 | tail -30` (expected: all pass, 0 skipped; `docs/tasks/screenshots-0332/next-390.png` exists; look at it once and say what you see: the host bubble, Havel's bubble, the "You can ask next:" line and two buttons that fit the width).

9. **No-JS check.** `cd App && .venv/bin/python -m pytest tests/test_havel_page.py tests/test_host_i18n.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -10` (the unit test of step 7 posts the mini-form's own fields, which is the no-JavaScript path). Expected: pass.

## 5. Do not touch

`App/app/havel.py`, `App/app/havel_prompt.py` (0311), `_havel_form.html`, `_havel_card.html`, the i18n blocks beyond the one key, `ai.py`. AGENTS.md rules 6, 7 and 9.

## 6. Commands

From `App/` (browser ones with the two exports from step 8):

```
.venv/bin/python -m pytest tests/test_havel_page.py tests/test_havel_browser.py tests/test_host_i18n.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
```

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: all pass, 0 skipped, OK.

## 7. Acceptance

- [ ] A reply with `next` shows "You can ask next:" and one button per entry under the newest Havel bubble only; the next reply removes the block (JavaScript and no-JavaScript).
- [ ] A tap posts `message=<entry>` and is answered like a typed message (counted by the same limits).
- [ ] `havel.next_title` exists in en, cs and vi; parity check from 0325 step 3 prints `[] []`.
- [ ] `docs/tasks/screenshots-0332/next-390.png`, no horizontal scroll at 390.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: `Reply` has no `next` (0311 shipped before this change), or an anchor in section 2 is missing.

## 9. Report

Write `docs/tasks/0332-report.md` (400 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, what the screenshot shows. Do not push.

## Risk list (for the reviewer)

`_havel_thread.html` (button values are autoescaped; the hidden history is the signed one from the context), `havel.js` (the next handler runs before the composer handler and never double-sends), `routes/havel.py` (one keyword added, nothing else).

## Owner steps

None until 0323; there, after a reply to "give me the guest link and sync my calendars", tap the button under Havel's answer and check that it is answered and counted.
