# 0405: try Leon at the end of the setup wizard (capped test chat)

Status: review
Depends on: 0404 (same branch) | Branch: claude/0403-leon-setup-wizard (checked out; commit here)
Executor: Haiku 5.5 | Reviewer: Opus | Fits one session: 30 tool calls, 80k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "at the end once everything is set up let them try communicating with Leon few messages (set up a cap)".

The wizard's `try` step (0404 placeholder) gets a small chat: the host types a question as a guest would, Leon answers exactly as he would for a booked guest, from the cards marked Done.

- **Cap:** `leon.TRY_MAX = 5` model-answered test messages per property per rolling 24 hours (`rate_limit` scope `leon_try`, key = property id, window 86400 s). Small talk ("hi", "thanks") and too-long messages are answered locally and do not count. At the cap: no model call, the fixed line `leon_setup.try.cap`.
- **Nothing is stored** about the test: no `guest_chat`, `guest_chat_message` or `guest_question` row, no host notification, no mail. Only `ai.call`'s usage ledger (it counts against Leon's per-property daily budget, which is fine) and the rate-limit rows.
- No history is sent: each test message is answered on its own.
- When Leon would ask the host (kind `ask_host`, or `answer` with a summary, or a model error), the host sees Leon's guest text plus a host-only note `leon_setup.try.would_ask`.
- Works with and without JS: with JS the page posts by `fetch` and appends bubbles; without JS the form posts and the page shows the last question and answer.
- Never log message text.

## 2. Context (read only these)

- `App/app/leon.py`: `reply` / `_answer` (~483-640) for the order of checks, `smalltalk_kind`, `is_noise`, `redact`, `user_turn`, `system_blocks`, `SCHEMA` (grep `SCHEMA =`), `validate`, `emergency_text`, `_fixed`, `_named`, `MAX_MESSAGE_CHARS`, `MAX_TOKENS`, `FEATURE`, `switched_on`.
- `App/app/guide_facts.py` `for_guest(apartment_id, level, lang)` (what `_answer` passes as `cards`).
- `App/app/rate_limit.py` `blocked(scope, key, max_events, window)`, `record(scope, key)`, `_count`.
- `App/app/ai.py`: `call`, `AIError` (`.reason`), `enabled_for_property`.
- `App/app/routes/leon_setup.py` (0404) and `App/app/templates/leon_setup/try.html`.
- `App/app/routes/guest.py` `_host_contact(apartment)` (host name, as `routes/guest_leon.py` uses it).
- Chat look: classes in `docs/design/catalog.json` starting `havel-` (`havel-bubble`, `havel-answer`, `havel-composer`, `havel-input`, `havel-dots`, `havel-error`). Use only existing classes; `data-*` for hooks.
- `App/app/static/leon-setup.js` (0404).

## 3. Files

| Path | Action |
|---|---|
| App/app/leon.py | `TRY_MAX`, `try_left(apartment_id)`, `try_reply(apartment, text, *, lang, host_name)` |
| App/app/routes/leon_setup.py | POST `/apartments/{id}/leon/setup/try` (JSON or page) |
| App/app/templates/leon_setup/try.html | the chat |
| App/app/static/leon-setup.js | fetch + bubbles |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | copy |
| App/tests/test_0405_leon_try.py, App/tests/test_0404_leon_setup_browser.py | tests, screenshot |

## 4. Steps

1. `leon.py`, after `reply`:
   ```python
   # 0405: the host tries Leon at the end of the setup wizard. Nothing is stored but the
   # usage ledger and the rate-limit rows; the cap is per property per rolling day.
   TRY_MAX = 5
   TRY_WINDOW = 24 * 3600


   def try_left(apartment_id: int) -> int:
       return max(0, TRY_MAX - rate_limit._count("leon_try", str(apartment_id), TRY_WINDOW))


   def try_reply(apartment, text: str, *, lang: str, host_name: str) -> Dict[str, Any]:
       """One test message in, one reply out: {"kind", "text", "would_ask", "left"}. Never stores the chat."""
       apartment_id = int(apartment["id"])
       text = str(text or "").strip()

       def out(kind: str, body: str, would_ask: bool = False) -> Dict[str, Any]:
           return {"kind": kind, "text": body, "would_ask": would_ask, "left": try_left(apartment_id)}

       if not text or len(text) > MAX_MESSAGE_CHARS:
           return out("too_long", _fixed(lang, "leon_too_long", n=MAX_MESSAGE_CHARS))
       small = smalltalk_kind(text)
       if small:
           return out("smalltalk", _fixed(lang, "leon_hi" if small == "hi" else "leon_thanks"))
       if is_noise(text):
           return out("unclear", _fixed(lang, "leon_unclear"))
       if rate_limit.blocked("leon_try", str(apartment_id), TRY_MAX, TRY_WINDOW):
           return out("cap", "")
       redacted = redact(text)
       cards = guide_facts.for_guest(apartment_id, "booked", "en")
       if not cards:
           return out("no_guide", "")
       rate_limit.record("leon_try", str(apartment_id))
       try:
           data = ai.call(FEATURE, system_blocks(cards, apartment["internal_name"] or ""),
                          [{"role": "user", "content": user_turn(redacted, lang)}], SCHEMA,
                          key=str(apartment_id), max_tokens=MAX_TOKENS)
       except ai.AIError as exc:
           log.info("leon try property=%s failed reason=%s", apartment_id, exc.reason)
           return out("passed", _named(lang, "leon_passed_to_host", host_name), True)
       verdict = validate(data, cards, redacted)
       kind = verdict["kind"]
       log.info("leon try property=%s kind=%s reason=%s", apartment_id, kind, verdict["reason"])
       if kind == "answer":
           body = verdict["text"]
           if verdict["summary"]:
               body += "\n" + _fixed(lang, "leon_asked_host_part")
           return out("answer", body, bool(verdict["summary"]))
       if kind == "emergency":
           return out("emergency", emergency_text(lang, cards), True)
       if kind == "refuse":
           return out("refuse", _fixed(lang, "leon_refuse"))
       if kind == "about_me":
           return out("about_me", _fixed(lang, "leon_about"))
       if kind == "unclear":
           return out("unclear", _fixed(lang, "leon_unclear"))
       return out("ask_host", _named(lang, "leon_asked_host_sorry" if verdict["upset"] else "leon_asked_host", host_name), True)
   ```
   Check that `log`, `rate_limit`, `guide_facts`, `ai` are already imported in `leon.py` (grep the import line); add only what is missing. The guest copy keys (`leon_*`) are guest i18n keys already used by `reply`; `lang` here is the host's page language mapped to a guest language: use `"cs"` when the host page language is `cs`, else `"en"`.
2. `routes/leon_setup.py`: `POST /apartments/{apartment_id}/leon/setup/try` (register it above any `/{step}` GET is not needed: methods differ). Guards as the other wizard routes, plus 404 unless `leon.switched_on(apartment)` and `guest_guide.progress(id)["live"]`. Read `message` from the form. `result = await run_in_threadpool(leon.try_reply, apartment, message, lang=guest_lang, host_name=_host_contact(apartment).get("name", ""))`. If the request has `Accept: application/json` (the JS sets it) return `JSONResponse({...result, "note": <host note or "">, "text": <text, or the cap/no_guide copy>}, headers={"Cache-Control": "no-store"})`; else render `leon_setup/try.html` like the GET with extra `asked=message[:500]` and `answer=result`. Host-facing copy for kinds `cap` (`leon_setup.try.cap`) and `no_guide` (`leon_page.not_live`) and the note `leon_setup.try.would_ask` come from `host_i18n` (`t` in the route: `host_i18n.translate(host_i18n.lang_from_request(request), key)`).
   GET `try` (0404) also passes `try_left=leon.try_left(id)` and `try_max=leon.TRY_MAX`.
3. `leon_setup/try.html` (keep 0404's not-live branch and the Finish primary):
   ```jinja
   <p class="setup-wizard-lede">{{ t('leon_setup.try.lede') }} {{ t('leon_setup.try.limit', n=try_max) }}</p>
   <div class="havel-card" data-leon-try data-leon-try-url="/apartments/{{ apartment.id }}/leon/setup/try">
     <ol class="havel-bubbles" data-leon-try-log aria-live="polite">
       {% if asked %}<li class="havel-bubble" data-role="host">{{ asked }}</li>
       <li class="havel-answer" data-role="leon">{{ answer.text or (t('leon_setup.try.cap') if answer.kind == 'cap' else t('leon_page.not_live')) }}{% if answer.would_ask %}<p class="ui-sub">{{ t('leon_setup.try.would_ask') }}</p>{% endif %}</li>{% endif %}
     </ol>
     <form method="post" action="/apartments/{{ apartment.id }}/leon/setup/try" class="havel-composer" data-leon-try-form>
       <input type="hidden" name="_csrf" value="{{ csrf_token }}">
       <label class="visually-hidden" for="leon-try-input">{{ t('leon_setup.try.label') }}</label>
       <input class="havel-input" id="leon-try-input" name="message" maxlength="500" autocomplete="off" placeholder="{{ t('leon_setup.try.placeholder') }}" {% if try_left <= 0 %}disabled{% endif %} required>
       {{ ui_button(t('leon_setup.try.send'), 'secondary', type='submit', icon_name='send') }}
     </form>
     {% if try_left <= 0 %}<p class="ui-sub" data-leon-try-cap>{{ t('leon_setup.try.cap') }}</p>{% endif %}
   </div>
   ```
   Replace `havel-bubbles` / `visually-hidden` with whatever list and screen-reader classes exist in `catalog.json` (grep `havel-` and `sr-only|visually-hidden`); if none fits, use a plain `<ol>` with `data-*` and no class. The Send button is secondary; Finish stays the one primary.
4. `leon-setup.js`, add below the reload block:
   ```js
   // 0405: the test chat posts by fetch and appends bubbles; without JS the form posts the page.
   (function () {
     var box = document.querySelector("[data-leon-try]");
     if (!box) return;
     var form = box.querySelector("[data-leon-try-form]");
     var log = box.querySelector("[data-leon-try-log]");
     var input = form.querySelector("input[name=message]");
     function bubble(cls, role, text, note) {
       var li = document.createElement("li");
       li.className = cls; li.setAttribute("data-role", role); li.textContent = text;
       if (note) { var p = document.createElement("p"); p.className = "ui-sub"; p.textContent = note; li.appendChild(p); }
       log.appendChild(li); li.scrollIntoView({block: "nearest"});
     }
     form.addEventListener("submit", function (ev) {
       ev.preventDefault();
       var text = input.value.trim();
       if (!text) return;
       var body = new FormData(form);
       body.set("message", text);
       bubble("havel-bubble", "host", text);
       input.value = ""; input.disabled = true;
       fetch(box.getAttribute("data-leon-try-url"), {method: "POST", body: body, headers: {"Accept": "application/json"}, credentials: "same-origin"})
         .then(function (r) { return r.json(); })
         .then(function (d) { bubble("havel-answer", "leon", d.text, d.note); input.disabled = d.left <= 0; if (!input.disabled) input.focus(); })
         .catch(function () { input.disabled = false; });
     });
   })();
   ```
   Use the same class names as step 3. Bump the script `?v=` in `_layout.html` to `20261026-0405`.
5. Copy (en / cs; vi in `host_vi_i18n.py`):

   | key | en | cs |
   |---|---|---|
   | `leon_setup.try.limit` | You can send %(n)s test messages a day. | Denně můžete poslat %(n)s zkušebních zpráv. |
   | `leon_setup.try.label` | Your question for Leon | Vaše otázka pro Leona |
   | `leon_setup.try.placeholder` | For example: Where do I park? | Například: Kde mám parkovat? |
   | `leon_setup.try.send` | Send | Odeslat |
   | `leon_setup.try.cap` | That was today's last test message. You can try again tomorrow. | To byla dnešní poslední zkušební zpráva. Zkusit to můžete zase zítra. |
   | `leon_setup.try.would_ask` | In a real chat Leon now passes this to you, and you answer it in Guest questions. | Ve skutečném chatu vám to teď Leon předá a vy odpovíte v Otázkách hostů. |

6. Tests `test_0405_leon_try.py` (fixtures from `test_0404_leon_setup.py`; make the guide live and Leon switched on; monkeypatch `leon.ai.call` like `test_leon.py` does):
   - Answer path: the model returns an answer citing a Done card -> JSON `kind == "answer"`, text present, `left == 4`; **no rows** in `guest_chat`, `guest_chat_message`, `guest_question` afterwards.
   - `ask_host` verdict -> `would_ask` true, note present, still no `guest_question` row.
   - Small talk "hi" -> local reply, `left` unchanged, `ai.call` not called.
   - Six model messages: the sixth returns `kind == "cap"` without calling `ai.call`; the page then renders the input `disabled` and `data-leon-try-cap`.
   - Another property's counter is independent.
   - 404 when Leon is off or the guide is not live; 404 for a foreign property.
   - Without the JSON Accept header the response is the HTML page showing the question and the answer.
   - `ai.AIError` -> `kind == "passed"`, `would_ask` true, nothing stored.
7. Browser: in `test_0404_leon_setup_browser.py` the `try-390.png` screenshot now shows one exchange: monkeypatching is not possible in the live server, so set the env the server reads to keep AI off (as the other browser tests do) and only screenshot the empty chat with the composer; add `try-cap-390.png` after inserting `TRY_MAX` `rate_limit_event` rows for scope `leon_try` (copy how Havel browser fixtures delete/insert `rate_limit_event` rows; also DELETE `leon_try` rows at fixture start).

## 5. Do not touch

`leon.reply`, `_answer`, the guest pages and `guest-leon.js`, `CHARACTER`, `validate`, the 0404 steps other than `try`.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
.venv/bin/python -m pytest tests/test_0405_leon_try.py tests/test_0404_leon_setup.py tests/test_leon.py tests/test_guest_leon_chat.py tests/test_privacy_first.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_0404_leon_setup_browser.py -q -rs --tb=short 2>&1 | tail -15
```
From the repo root: `python3 scripts/design_lint.py | tail -5`.

## 7. Acceptance

- [ ] The try step answers like Leon for a booked guest, from Done cards only.
- [ ] 5 model messages per property per rolling day; small talk free; at the cap no model call and the input is disabled.
- [ ] No guest chat, message or question row is ever written by a test; nothing reaches the host's inbox.
- [ ] Works without JS. §6 passes with 0 skipped.

## 8. Stop and ask

If `ai.call` needs a per-feature switch other than `leon` for this, or the CSRF check rejects the fetch post.

## 9. Report

`docs/tasks/0405-report.md` (600 tokens at most). Commit `0405 step k` after each step. Do not push.
