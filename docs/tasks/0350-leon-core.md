# 0350: Leon (AI): the guest bot's core

Status: todo
Depends on: 0344, 0348 and 0310 merged | Base commit: after 0344, 0348 and 0310 | Branch: task/0300-leon-core
Executor: Haiku 5.5 (critical: Fable reviews the diff before merge) | Fits one session: 30 tool calls, 60k tokens (leon.py is pasted, not typed)

## 1. Objective

Add Leon (AI), the guest bot, behind the two guide doors of 0344: a guest writes a question, `claude-haiku-5-5` (through `ai.call`, feature `leon`, key = property id) answers only from the confirmed guide cards that door may read, the server checks every answer against the cited cards, and anything the guide does not answer (or Leon may not read: lifetime cap, spent budget, outage) becomes a question for the host (brief 0351 shows it to the host; the guest sees the answer on the page). This brief is the backend plus a minimal JSON endpoint per door; the chat UI is 0352.

## 2. Context

### Owner decisions that bind this brief ([plan](../plans/guest-guide.md))

- Two doors to one bot: the QR page (public, "everyone" cards) and the stay link ("booked" cards from 1 day before check-in until the checkout day, else "everyone"). Door codes stay with TTLock only; Leon never sees or repeats one.
- Never invent. Drafts (`state = 'check'`) and host-only cards never reach a guest or the prompt.
- Host replies reach the guest on the page only; no guest e-mail is collected.
- Chat logs: 30 days after checkout (QR chats: 30 days after the last message).
- Free for every host, with a daily cap per property.
- Leon is "Leon (AI)" everywhere and always says he is an AI. The plan's "Leon (AI): character" section is the system prompt's `YOUR CHARACTER` part (`leon.CHARACTER`, step 4). The QR page shows the host's name only (0344).

### Design

**Knowledge.** The only source is `guest_guide.for_guest(apartment_id, level)` (0341: `done` cards of that visibility, empty until the guide is live). `leon.system_blocks(cards, property_name)` returns two constant texts: `CHARACTER`, and a `<guide>` block with each card as `[c<id>] title`, `where:`, `steps:` (one per line, as the host wrote them), `watch out:`, `media: photo, video`, sorted by id, with `<` and `>` removed from host text so a card cannot close the tag. Nothing per request goes in `system`, so the prompt cache holds per property and level (5 minutes). The property name is the one the door already shows; check-in and checkout times reach Leon only as the host's checkin and checkout cards (the `cleaning_property` times are a cleaner's schedule, not guest copy, so they stay out). The page language and the redacted message go in the user turn inside `<guest_message>` tags. Leon never gets the guest's name or any other registration data, and answers briefly with only what the guest needs (owner, 2026-10-24).

**Kinds** (`SCHEMA`, strict JSON, `additionalProperties: false`, no length keywords: lengths are server checks as in the Havel plan §5):

| Kind | Who decides | Guest sees |
|---|---|---|
| `answer` | model, then `validate()` | the model's reply, only if it passes every check. Several questions in one message: one short line per covered part; the uncovered parts go in `host_summary`, the server opens one `guest_question` with that summary and appends the fixed line `leon_asked_host_part` |
| `ask_host` | model (guide silent, host must decide: dates, prices, refunds, complaints, pets), or `validate()` on any failed check | fixed copy `leon_asked_host` ("I don't want to guess about this, so I've asked Jana, your host. ..."), or `leon_asked_host_sorry` ("I'm sorry about this. ...") when the model set `upset`; a `guest_question` row (status `open`) is written for 0351. A repeat of a question that is still open in this chat (same folded words) gets `leon_asked_already` with no model call and no new row |
| `refuse` | model (off-topic, prompt reveal or change, other guests, host's private life, other flats, door codes, abuse) | fixed copy `leon_refuse`; the third refusal pauses the conversation for 24 hours (`leon_paused`) |
| `about_me` | model ("are you a person?", "who made you", "what model") | fixed copy `leon_about`: AI, the host's assistant, asks the host when the guide is silent. An "I am an AI" answer has no card to cite, so it is fixed copy rather than a guardrail failure |
| `emergency` | model (fire, smoke, gas, flooding, someone hurt, any risk to life), or the server's `looks_dangerous()` word list when the model cannot be asked | fixed `leon_emergency` ("If anyone is in danger, call 112 now ...") plus the host's `emergency` card as written; a `guest_question` with `urgent = 1`. Never model text, never troubleshooting |
| `unclear` | server (`is_noise()`: no letters, or only a link) before any model call, or model (gibberish) | fixed `leon_unclear`; no question |
| `smalltalk` | server, before any model call | fixed `leon_hi` / `leon_thanks` when the whole message is a greeting or thanks in en, cs, de, es, fr or uk |
| `passed` | server, no model call: the door's lifetime cap is reached, the guide is empty, or `ai.call` raised (`AIDisabled`, `AIBudgetError`, any `AIError`) | fixed `leon_passed_to_host` ("I've passed your message to Jana, your host. The answer will appear here."); a `guest_question` with `triaged = 0` (summary = the redacted message), and later passed messages of the same chat append to that open row instead of making new ones (`MAX_PASSED_CHARS`). If the message has a danger word, `emergency` instead (urgent, untriaged). There is no "resting" reply any more |
| `too_long`, `slow_down`, `paused` | server, no model call | fixed copy |
| `busy` | server: another request of this chat holds the guard (below) | fixed `leon_busy`; nothing stored, no model call, no cap count; 0352 re-queues and retries |
| `answered` | server: the same folded words as a question the host already answered in this chat | fixed `leon_see_above`; no model call, no new row |

**Never invent (`validate`).** An `answer` survives only if: at least one `sources` entry is `c<id>` of a card in this door's list (unknown, host-only, draft and malformed ids are dropped; none left fails `no_source`); the reply is 1 to 800 characters (`length`; 800 rather than 600 so three short parts plus one card's steps fit); it has no `http`, `www.`, `@`, `<`, `>`, `**` or backtick (`markup`); and every digit run in it (step numbers at a line start excepted) appears in the cited cards' text, in the guest's own message or in `EMERGENCY_NUMBERS` (112, and the Czech 150, 155, 158: fixed safe facts, orchestrator decision 2026-10-24) (`number`). This catches invented times, prices, codes and phone numbers. The whole text is checked, so a multi-part answer with one invented number fails as a whole. A failed answer becomes `ask_host` with the model's `host_summary` (redacted, 300 characters at most) or else the redacted question (the host sees the full redacted message on 0351's page anyway). Model text is shown only for a valid `answer`; every other kind shows fixed copy. The schema has one more field, `upset` (boolean): it only picks the sorry variant of the fixed `ask_host` copy. No Havel-style "next" tap suggestions for guests: Leon asks the host the uncovered parts himself, so nothing is left for the guest to re-ask, and the guest chat UI (0352) stays one input and one list.

**Conversations** (migration, step 3). `guest_chat`: stay door one row per reservation (unique partial index; every device of the stay shares it); QR door one row per property and `ubyhost_leon` cookie id (`secrets.token_urlsafe(24)`, HttpOnly, SameSite=Lax, `Secure` when `auth.secure_cookies()`, path `/g/<token>`, 30 days, set on the first POST only). `guest_chat_message`: role `guest` (redacted text), `leon` (with kind and cited `sources`), `host` (0351 writes it). `guest_question`: the handoff seam for 0351 (`summary` in English for the host, `status` open/answered/dismissed, `answer`, `answered_at`, `urgent` 0/1 for emergencies, `triaged` 1 when Leon read the message and 0 when it was passed unread). `guest_chat.model_messages` counts the model calls of a conversation for the lifetime cap. The model sees the last 6 turns (guest messages and valid answers and host answers only), which is what makes short follow-ups ("where is that?") work. **One request at a time** (owner, 2026-10-24): `reply` takes `guest_chat.busy_until` with one atomic `UPDATE ... WHERE busy_until IS NULL OR busy_until < now` (rowcount 1, `leon._take_turn`, 60 s: above `ai.call`'s worst case of a 20 s timeout plus one retry, so a dead worker's guard is taken over) and clears it in `finally`; `GET` reports `"answering"` while it is held. **Retries** (`guest_chat_message.client_id`, unique per chat): 0352 sends one random id per message batch; a retry with a stored id gets the stored reply (`_replay`) with no new turn, model call or rate-limit count. Every operational scenario: [leon-scenarios](../plans/leon-scenarios.md).

**Abuse and cost.** Message 500 characters at most. Per conversation 10 messages per 15 minutes (`rate_limit` scope `leon_chat`), per address 30 per 15 minutes across all conversations (`leon_addr`, key `rate_limit.client_key(request, "leon")`); every QR post also counts as a QR page view (`guide_qr`, 120 per 15 minutes, 0344), so one address cannot mint endless QR conversations. **Lifetime cap per conversation** (owner, 2026-10-24: save money; a guest over the cap is passed to the host): `STAY_MAX = 20` model-answered messages per stay, `QR_MAX = 10` per QR conversation, env `UBYHOST_LEON_STAY_MAX` / `UBYHOST_LEON_QR_MAX` override (`door_cap()`). Only messages that reach the model count: smalltalk, noise, too-long, repeats and passed messages do not. `max_tokens=500` (0310 clamps to its ceiling; 500 rather than 400 so a three-part Czech reply fits). Spend: `UBYHOST_AI_MONTHLY_USD_LEON` (default 10) with 0310's daily share, and `UBYHOST_AI_KEY_DAILY_USD_LEON` per property (owner sets 0.05; 0 means off). Leon is off until `UBYHOST_AI_FEATURES` lists `leon`; the endpoints 404 while the guide is not live. A past guest on the QR door gets everyone level only, because the QR door never looks at a stay.

**Cost per message** (0310 prices: input 0.10, output 0.50, cache read 0.01, cache write 0.125 USD per million). System prompt about 1,200 tokens plus the guide (20 cards: about 2,000 to 2,500), so about 3,000 cached tokens; user turn plus history 200 to 700 tokens; output 80 to 300 (a brief reply in JSON). Warm cache: about 0.0002 USD; cold (first message in 5 minutes): about 0.0007 USD. The 0.05 USD per-property day cap is at least 70 messages; 10 USD a month is 15,000 or more; the lifetime caps bound a stay at about 0.01 USD.

**Privacy.** `leon.redact()` replaces e-mails, phone numbers (7+ digits with spaces, dashes, dots or brackets) and id-like runs (6+ letters and digits with 4+ digits, such as `AB1234567`) with `[email]`, `[phone]`, `[number]` before the text is stored or sent; short numbers ("room 12") stay so the guest's own numbers can be echoed. No guest name or registration data reaches the model on either door. Logs carry chat id, kind, reason code, question id and source count, never text. A message over 500 characters is refused locally (`leon_too_long`), never stored or sent; pasted long text under the cap is just a guest's words to the model (CHARACTER says so) and the number and source checks still apply to the answer. Retention: `leon.purge` in the `retention.py` `guest_chats` step, a `RETENTION.md` row, cookie `ubyhost_leon` in `cookie_inventory.py` (all six languages) and in the privacy crawl.

**Host name.** The door shows the legal entity's name (0344). `leon.host_first_name()` keeps its first word ("Jana Nováková" gives "Jana") unless it looks like a company (`s.r.o.`, `a.s.`, `spol.`, `z.s.`, Ltd, GmbH, Inc, LLC or a digit), which keeps the whole name. No name gives `leon_asked_host_plain`.

**Seams.** 0351 lists `guest_question` rows with `status = 'open'` for a property (its alert becomes `critical` and mails at once when a row has `urgent = 1`; its page marks `urgent` and `triaged = 0` rows), writes `answer`, `answered_at`, `status = 'answered'` and a `guest_chat_message` with role `host`; its host alert hook goes directly under the comment `# 0351 adds its host alert hook directly below this line.` in `leon._open_question`; `leon.messages(chat_id)` and `GET .../leon` already return host turns, so 0352 renders them. 0352 posts the form fields `message` and `client_id` to the endpoints below and reads `{"kind", "text", "asked_host"}` (kinds: `answer`, `ask_host`, `refuse`, `about_me`, `emergency`, `unclear`, `smalltalk`, `passed`, `too_long`, `slow_down`, `paused`, `busy`, `answered`; `emergency` deserves a visible style in 0352); `GET` returns `{"messages": [{"role", "kind", "text", "at"}], "open_questions": n, "answering": bool}`.

| Route | Gate |
|---|---|
| `GET`/`POST /l/{token}/{reservation_id}/guide/leon` | `_stay_gate` (0344: link, PIN, stay, claim), level `booked_level(reservation)` |
| `GET`/`POST /g/{token}/leon` | `_qr_apartment` (0344: QR rate limit, token), level `everyone` |

Both routes send 0344's `HARDEN` headers (no-store, noindex, no-referrer). POSTs are guarded by `security.protect_guest_post` (CSRF, as every guest form). The model call runs in a threadpool.

Hard rules 2 (no text in logs, retention line, no tracking cookie), 3, 4 (no new dependency), 5 (SQL through `db.py`, Postgres-portable: partial unique indexes and `substr` exist in both), 9. Rule 7 does not apply: no template or CSS changes.

### Anchors (verbatim; a missing anchor means STOP)

From 0310, `App/app/ai.py`: `def call(feature: str, system_blocks: List[str], messages: List[Dict[str, Any]], schema: Dict[str, Any],` followed by `         key: Optional[str] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:`. If `max_tokens` is missing, STOP (the 0310 thread owns that change).

From 0344, `App/app/routes/guest_guide_view.py`: `HARDEN = {`, `def booked_level(reservation, today: Optional[date] = None) -> str:`, `def _stay_gate(request: Request, token: str, reservation_id: int):`, `def _qr_apartment(request: Request, token: str):`. `App/app/i18n.py`: five lines starting `        "guide_photo_alt": ` (en, cs, de, es, fr, in that order); `App/app/guest_uk_i18n.py`: `    "guide_photo_alt": "Фото %(n)s",`.

`App/app/main.py`: the import line containing `guest_guide_view, invoices,` and the line `app.include_router(guest_guide_view.router)`.

`App/app/cookie_inventory.py`: the two lines `    {` / `        "name": "ubyhost-sidebar-collapsed",` and, in `_GUEST_LANGUAGE_TEXT`, `            "fr": "60 jours",` / `        },` / `    },` / `    "ubyhost-sidebar-collapsed": {`. `App/app/guest_uk_i18n.py`: `    "ubyhost_guest_lang": ("Запам’ятовує мову гостя", "60 днів"),`.

`App/app/retention.py`: `# Each step takes (today, dry_run, owner_user_id) and returns the affected count.`, `    ("guide_imports", _guide_import_step),`, `        "legal_acceptance": (`.

`App/tests/test_privacy_first.py`: `from app import auth, claim, cookie_inventory, db, i18n, landing_i18n, public_guides`, `        guest.get(f"/l/{TOKEN}/privacy?lang=cs", follow_redirects=True)` followed by `    finally:`, and `        "ubyhost_guest_lang",` followed by `    }`.

`docs/privacy/RETENTION.md`: the row starting `| Submission envelopes (XML with doc numbers) |`. `docs/ENVIRONMENT.md`: the row starting ``| `UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT` |``. `docs/context/test-map.md`: the row starting `| Retention, privacy, personal data |`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/NNNN_guest_chat.sql` | create | Copied from `docs/plans/0350-files/guest_chat.sql` (NNNN from the lint, step 1) |
| `App/app/leon.py` | create | Copied from `docs/plans/0350-files/leon.py`: prompt, schema, redaction, guardrail, conversations, reply, caps, purge |
| `App/app/routes/guest_leon.py` | create | Copied from `docs/plans/0350-files/guest_leon.py`: both doors' JSON endpoints, the QR cookie |
| `App/app/main.py` | edit | Import and register the router |
| `App/app/i18n.py` | edit | 20 `leon_*` keys in en, cs, de, es, fr (script) |
| `App/app/guest_uk_i18n.py` | edit | The 20 keys in uk (script); the cookie's uk text |
| `App/app/cookie_inventory.py` | edit | `ubyhost_leon` row and its de, es, fr text |
| `App/app/retention.py` | edit | `guest_chats` step and cutoff line |
| `App/tests/test_privacy_first.py` | edit | Crawl reaches the Leon cookie; the set names it |
| `App/tests/test_leon.py` | create | Copied from `docs/plans/0350-files/` |
| `App/tests/eval/leon_cases.json` | create | Copied from `docs/plans/0350-files/` |
| `App/scripts/leon_eval.py` | create | Copied from `docs/plans/0350-files/` |
| `docs/privacy/RETENTION.md` | edit | One row |
| `docs/ENVIRONMENT.md` | edit | One row |
| `docs/context/test-map.md` | edit | One row |
| `docs/plans/guest-guide.md` | edit | 0350 row: state `review` |

No other file may change. `docs/plans/0350-files/add_leon_i18n.py` is run, not copied.

## 4. Steps

### Step 1: preflight

Commands run from `App/` unless a step says the repo root.

From the repo root: `grep -c 'max_tokens: Optional\[int\] = None' App/app/ai.py; grep -c '"guide_photo_alt"' App/app/i18n.py; python3 scripts/context_lint.py | grep 'next free'`. Expected: `1`, `5`, and a line naming the next free migration. Use that number as NNNN everywhere below (it was 0017 in the scratch copy) and say which in the report.

### Step 2: copy the test, eval and script files

```bash
cp docs/plans/0350-files/test_leon.py App/tests/test_leon.py
mkdir -p App/tests/eval && cp docs/plans/0350-files/leon_cases.json App/tests/eval/leon_cases.json
cp docs/plans/0350-files/leon_eval.py App/scripts/leon_eval.py
```

Command: `ls App/tests/test_leon.py App/tests/eval/leon_cases.json App/scripts/leon_eval.py | wc -l`. Expected: `3`.

### Step 3: migration

`cp docs/plans/0350-files/guest_chat.sql App/app/migrations/NNNN_guest_chat.sql` (from the repo root). The file is reviewed there; it holds the three tables in §2 (`guest_chat.model_messages` and `busy_until`, `guest_chat_message.client_id`, `guest_question.urgent` and `triaged` included) with `ON DELETE CASCADE` from `apartment`, `reservation` and the chat, partial unique indexes `uq_guest_chat_stay (reservation_id) WHERE door = 'stay'`, `uq_guest_chat_qr (apartment_id, cookie_id) WHERE door = 'qr'` and `uq_guest_chat_message_client (chat_id, client_id) WHERE client_id IS NOT NULL`, and CHECKs on `door`, `role` and `status`.

Command (from `App/`): `.venv/bin/python -c "from app import db; db.init_db(); print(db.query_one('SELECT COUNT(*) AS n FROM guest_question')['n'])" 2>&1 | tail -3`. Expected: `0`.

### Step 4: `App/app/leon.py`

`cp docs/plans/0350-files/leon.py App/app/leon.py` (from the repo root). The file is reviewed there: prompt (`CHARACTER` is the plan's Leon section turned into rules plus the SITUATIONS block; change it only together with the plan and re-run the eval), `SCHEMA`, redaction, `validate`, conversations, `reply`, `purge`. Do not edit it.

Command: `.venv/bin/python -c "from app import leon; print(leon.redact('a@b.cz +420 777 123 456 AB1234567 room 12'), leon.is_noise('?'), leon.looks_dangerous('fireplace'), leon.door_cap('stay'), len(leon.CHARACTER))"`. Expected: `[email] [phone] [number] room 12 True False 20 5034`.

### Step 5: `App/app/routes/guest_leon.py`

`cp docs/plans/0350-files/guest_leon.py App/app/routes/guest_leon.py` (from the repo root). It imports `HARDEN`, `_qr_apartment`, `_stay_gate` and `booked_level` from 0344's `guest_guide_view` and `_host_contact` from `guest`, on purpose: Leon can never be reached by a stay or token the guide page would refuse. Command (from `App/`): `.venv/bin/python -c "from app.routes import guest_leon; print(len(guest_leon.router.routes))"`. Expected: `4`.

### Step 6: register the router

`App/app/main.py`: in the import line replace `guest_guide_view, invoices,` with `guest_guide_view, guest_leon, invoices,`. Directly after the line `app.include_router(guest_guide_view.router)` insert:

```python
app.include_router(guest_leon.router)
```

Command: `grep -c 'guest_leon' app/main.py`. Expected: `2`.

### Step 7: guest copy

From the repo root: `python3 docs/plans/0350-files/add_leon_i18n.py`. Expected: `added 20 keys x 6 languages`. The script inserts the `leon_*` keys after each `guide_photo_alt` line (en, cs, de, es, fr) and after the uk one, and refuses to run twice. Command: `grep -c '"leon_about"' App/app/i18n.py App/app/guest_uk_i18n.py`. Expected: `5` and `1`.

### Step 8: cookie inventory

`App/app/cookie_inventory.py`: directly before the two lines `    {` / `        "name": "ubyhost-sidebar-collapsed",` insert:

```python
    {
        "name": "ubyhost_leon",
        "set_by": "routes/guest_leon.py:qr_leon",
        "party": "first",
        "kind": "cookie",
        "surface": "guest",
        "purpose": {
            "en": "Keeps your conversation with Leon (AI) on this property's guide page; a random number, nothing about you",
            "cs": "Udržuje vaši konverzaci s Leonem (AI) na stránce průvodce; náhodné číslo, nic o vás",
        },
        "lifetime": {"en": "30 days", "cs": "30 dní"},
    },
```

In `_GUEST_LANGUAGE_TEXT`, directly before `    "ubyhost-sidebar-collapsed": {` (the one that follows `            "fr": "60 jours",` / `        },` / `    },`), insert:

```python
    "ubyhost_leon": {
        "purpose": {
            "de": "Hält Ihr Gespräch mit Leon (KI) auf der Seite dieser Unterkunft; eine Zufallszahl, nichts über Sie",
            "es": "Mantiene su conversación con Leon (IA) en la página de este alojamiento; un número aleatorio, nada sobre usted",
            "fr": "Garde votre conversation avec Leon (IA) sur la page de ce logement ; un nombre aléatoire, rien sur vous",
        },
        "lifetime": {
            "de": "30 Tage",
            "es": "30 días",
            "fr": "30 jours",
        },
    },
```

`App/app/guest_uk_i18n.py`: directly after `    "ubyhost_guest_lang": ("Запам’ятовує мову гостя", "60 днів"),` insert:

```python
    "ubyhost_leon": ("Зберігає вашу розмову з Leon (ШІ) на сторінці цього помешкання; випадкове число, нічого про вас", "30 днів"),
```

Command: `.venv/bin/python -c "from app import cookie_inventory as c; print('ubyhost_leon' in c.STRICTLY_NECESSARY_COOKIES)"`. Expected: `True`.

### Step 9: retention

`App/app/retention.py`: directly before `# Each step takes (today, dry_run, owner_user_id) and returns the affected count.` insert:

```python
def _guest_chat_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Brief 0350: Leon conversations 30 days after checkout (stay) or the last message (QR)."""
    from . import leon
    return leon.purge(today, dry_run, owner_user_id)


```

Directly after `    ("guide_imports", _guide_import_step),` insert `    ("guest_chats", _guest_chat_step),`. Directly before `        "legal_acceptance": (` insert:

```python
        "guest_chats": f"stay ended, or QR chat last used, before {(today - timedelta(days=30)).isoformat()}",
```

Command: `grep -c 'guest_chats' app/retention.py`. Expected: `2`.

### Step 10: privacy crawl

`App/tests/test_privacy_first.py`: replace `from app import auth, claim, cookie_inventory, db, i18n, landing_i18n, public_guides` with `from app import auth, claim, cookie_inventory, db, guest_guide, guide_token, i18n, landing_i18n, public_guides`. Between `        guest.get(f"/l/{TOKEN}/privacy?lang=cs", follow_redirects=True)` and the `    finally:` after it, insert (blank line first):

```python

        # Leon (AI) on the public QR page: the conversation cookie (brief 0350).
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
        cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
        for kind in guest_guide.MUST_HAVE:
            guest_guide.save(apartment_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
        visitor = recorder.client()
        said = visitor.post(f"/g/{guide_token.ensure(apartment_id)}/leon", data={"message": "Hello"})
        assert said.status_code == 200, said.text
```

In `test_the_strictly_necessary_set_is_the_first_party_cookie_inventory`, after `        "ubyhost_guest_lang",` insert `        "ubyhost_leon",`.

### Step 11: docs

`docs/privacy/RETENTION.md`: directly before the row starting `| Submission envelopes (XML with doc numbers) |` insert:

```
| Guest chats with Leon (AI): the guest's messages (e-mails, phone numbers and long numbers removed before storing), Leon's replies, host answers, open questions for the host, the random QR browser id | `guest_chat`, `guest_chat_message`, `guest_question`; cookie `ubyhost_leon` | checkout (stay link) or last message (QR page) | 30 days | `leon.purge` (`retention.py` guest_chats step); cascade when the stay or property is deleted | Minimisation |
```

`docs/ENVIRONMENT.md`: directly after the row starting ``| `UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT` |`` insert:

```
| `UBYHOST_AI_MONTHLY_USD_LEON`, `UBYHOST_AI_KEY_DAILY_USD_LEON` | `10`, set `0.05` (from the Model API section) | Leon (AI), the guest bot (brief 0350, feature `leon`, key = property id): monthly cap for all properties and the daily cap per property. One message costs 0.0002 to 0.0007 USD (the higher figure when the prompt cache is cold), so 0.05 is at least 70 guest messages per property per day. `UBYHOST_AI_FEATURES` must list `leon`; without it, or past a cap, guests get the "passed to your host" reply and the host a question. |
| `UBYHOST_LEON_STAY_MAX`, `UBYHOST_LEON_QR_MAX` | `20`, `10` | Lifetime cap of model-answered guest messages per stay conversation and per QR-page conversation (brief 0350). Over the cap Leon makes no model call: the message goes to the host as an open question and the guest reads "I've passed your message to your host". |
```

`docs/context/test-map.md`: directly after the row starting `| Retention, privacy, personal data |` insert:

```
| Guest bot (Leon) | `test_leon.py test_privacy_first.py test_cookie_inventory.py test_guest_languages.py test_ai.py` |
```

`docs/plans/guest-guide.md`: in the row starting `| 3 | [0350](../tasks/0350-leon-core.md) |`, change the last cell `todo` to `review`.

### Step 12: tests and eval (offline)

From `App/`: the commands in §6.

## 5. Do not touch

`App/app/ai.py`, `App/tests/ai_fake.py`, `App/app/guest_guide.py`, `App/app/routes/guest_guide_view.py`, `App/app/routes/guest.py`, `App/app/db.py`, every template and CSS file, earlier migrations. No new dependency. Never log a message, a reply, a summary, a token or a cookie id. Hard rules 2, 3, 4, 5, 8 and 9 of AGENTS.md apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_leon.py -q --tb=short 2>&1 | tail -30`. Expected: `40 passed`.
- `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_cookie_inventory.py tests/test_guest_languages.py tests/test_retention*.py tests/test_guest_guide_view.py tests/test_guest_guide_merge.py tests/test_no_tracking.py tests/test_*_i18n.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed outside `test_host_i18n.py` (its three Vietnamese failures predate this brief; say so, do not fix).
- `.venv/bin/python -m pytest tests/test_ai.py -q --tb=short 2>&1 | tail -5`. Expected: passes. In the scratch copy `test_budget_month_day_and_key` failed on 0310's own day count (0.318 against 7/21); if it fails the same way, report it as 0310's and go on.
- `.venv/bin/python scripts/leon_eval.py --offline 2>&1 | tail -3`. Expected: last line `offline: case file OK`.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `grep -c 'def validate' App/app/leon.py` is `1`, and `test_leon.py` passes (40): both doors and levels, the four window edges, unsourced numbers and fake ids become `ask_host` with a `guest_question` row, 112 allowed without a card, host-only and draft cards never in the prompt, injection in a message and in a card, three refusals pause, smalltalk, noise and too-long messages make no model call, both rate limits, a multi-part answer opens one question for the rest and fails as a whole, an emergency shows 112 plus the host card with an urgent row (also with no model), an upset guest hears sorry first, a repeated open question is not asked twice, feature off, spent budgets and model errors pass the message to the host unread (one row per chat, later messages appended), the lifetime cap per door with no model call past it, the per-property cap keys on the property id, one conversation per stay, the QR cookie (HttpOnly, Lax, path, Secure in production, a bad cookie replaced), redaction before storing and sending, no message text in logs, retention after 30 days, a held guard gives `busy` (no model call, no cap count) and a stale one is taken over, a retried `client_id` returns the stored reply once, a repeat of an answered question gives `answered`.
- [ ] `test_privacy_first.py` and `test_cookie_inventory.py` pass with `ubyhost_leon` in the set.
- [ ] `grep -rn 'log\.\(info\|warning\|error\).*text' App/app/leon.py App/app/routes/guest_leon.py | wc -l` is `0`.
- [ ] No em dash in the new files: `grep -c '—' App/app/leon.py App/app/routes/guest_leon.py docs/plans/0350-files/add_leon_i18n.py` all `0`.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; `ai.call` has no `max_tokens`; a test fails twice; you reach 30 tool calls or about 50k tokens (report `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0350-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, the migration number used, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`docs/plans/0350-files/leon.py` (`CHARACTER`, `validate`, `redact`, `reply`, `_open_question`, `looks_dangerous`, `purge`), `docs/plans/0350-files/guest_leon.py` (gates, cookie), `docs/plans/0350-files/guest_chat.sql`, the `test_privacy_first.py` edit. Known limits: the number check does not catch an invented word-number ("five euros") or an invented place name; the eval set measures those (`no-invented-tip`, `honest-ask-host-*`). Unanswered `ask_host` turns are not sent back to the model, so a guest's follow-up to an open question reads as new (an identical repeat is caught by `_open_twin`). Emergency detection is the model's; the server word list (`_DANGER`) only runs when the model cannot be asked and then errs on the side of 112 ("gas" in "gas stove" also triggers it). The 43-case eval (33 must) is the measure of the situation rules (several questions, follow-ups, emergencies, requests for the host, safety, medical and tax, injection in pasted text, rude guests, about_me); ship only on PASS.

## Owner steps

1. Merge as usual with `scripts/merge-pr-on-green.sh` once CI is green.
2. On staging, in Lightsail, open the UbyHost container's environment and add `leon` to `UBYHOST_AI_FEATURES` (for example `guide_import,leon`), and set `UBYHOST_AI_KEY_DAILY_USD_LEON` to `0.05`. Save and restart the container.
3. On your computer, from `App/`, run `UBYHOST_ANTHROPIC_API_KEY=<staging key> UBYHOST_AI_FEATURES=leon .venv/bin/python scripts/leon_eval.py`. It makes 43 model calls (well under 0.05 USD) and ends with PASS or FAIL. Send the output to the orchestrator; ship only on PASS.
4. Production stays off (no `leon` in `UBYHOST_AI_FEATURES`) until 0351 (host answers) and 0352 (the chat on the page) are merged.
