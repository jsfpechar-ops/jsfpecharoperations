# 0351: Leon (AI): host handoff and "Add to guide"

Status: todo
Depends on: 0350 merged | Base commit: after 0350 | Branch: task/0301-guest-handoff
Executor: Haiku 5.5 (critical: Fable reviews the diff before merge) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When Leon gives `ask_host` (0350 writes a `guest_question` row), the host is alerted, answers in the app, the answer reaches the guest's conversation on the guide page (no guest e-mail is collected), and one tap turns the answer into a guide card. Backend module, two host pages, the alert and one mail. The guest-side rendering of host turns is 0352 (0350's `GET .../leon` already returns them).

## 2. Context

### Owner decisions that bind this brief ([plan](../plans/guest-guide.md))

Leon never gets the guest's name or registration data (nothing here changes the prompt). The host answer is shown to the guest as the host wrote it. QR page shows the host's name only. No new dependency or vendor. Chat rows live 30 days (0350's `leon.purge` deletes `guest_question` with the chat; nothing to add).

### Design

**Alert channel.** The existing "needs you" stack: `alerts.raise_alert` with `dedupe_key = "guest_question:<apartment_id>"`, level `warning`, `params = {"property", "count"}`. One line per property, refreshed with the open count on every new question and resolved (`alerts.resolve`) when the last open question is answered or dismissed. The line's button (`_ACTIONS["guest_question"]`) opens the questions page. The dashboard already renders open alerts (`needs_you.build`), so no dashboard code changes. **One mail per batch:** `mail.enqueue(kind="guest_question")` to the legal entity's contact address (`mail_notify._entity_contact_email`, as the filing watchdog does) only when the new question is the *only* open one for the property; later questions join the batch silently until the host clears it. This needs no column and no scheduler. **Urgent and unread rows (0350 change, 2026-10-24).** `guest_question.urgent = 1` is an emergency (Leon showed 112; the guest may be in danger): `refresh_alert` raises the line at level `critical` while any open row of the property is urgent, and `on_new_question` sends the batch mail for an urgent row even when other questions are open (idempotency key per question already allows it). `triaged = 0` means Leon never read the message (lifetime cap, spent budget or outage) and `summary` is the guest's redacted words, possibly several messages joined by newlines: the list and the question page show a badge (`guest_questions.badge.urgent` "Urgent", `guest_questions.badge.unread` "Not read by Leon (AI)", en and cs), an urgent row also gets a banner on its page (`guest_question.urgent_banner`) and the red line its own title (`notification.guest_question.title.urgent`, via the alert `variant` param); urgent rows sort first in the list and the question page renders the summary one `<p>` per line like the answer. Neither the alert nor the mail carries message text: the mail says "a guest at <property> asked something your guide does not answer" and links the page. Host mail language: `mail_notify.HOST_MAIL_LANGUAGE` (en), as every host mail. `mail_enabled()` false (tests, dev) skips the mail; the alert still stands.

**Where the host answers.** Two pages under the property's guide, `App/app/routes/guest_questions.py`: `GET /apartments/{id}/guide/questions` (list: open first, oldest first; then the rest, newest first; 50 rows) and `GET /apartments/{id}/guide/questions/{qid}` (one question: the redacted guest message, Leon's English summary, a textarea, primary "Send to guest"; a quiet "Dismiss without answering"). The guide page gets a second secondary button "Guest questions (n)". The router is registered *before* the guide router because `/guide/{item_id}` would otherwise catch `/guide/questions` (422).

**The answer.** `guest_handoff.answer`: 1 to 1000 characters, plain text as typed (CRLF normalised, stripped), stored in `guest_question.answer` and as a `guest_chat_message` with role `host`, kind `answer`; `status = 'answered'`, `answered_at` set, `guest_chat.last_message_at` bumped (so the QR retention clock restarts). Jinja autoescape renders it on the host page; 0352 renders it escaped on the guest page from 0350's JSON. An answered or dismissed question can still be answered (a second host turn is written).

**Add to guide.** `guest_handoff.add_to_guide(apartment_id, qid, topic)`: `guest_guide.add_custom(topic, title)` then `guest_guide.save(steps=answer, visibility=...)`, so the card is `state = 'done'`, `source = 'host'` (the host typed every word) and editable like any card. Title: Leon's summary, else the redacted question, cut to 120 characters. Visibility: `everyone` for a QR question, `booked` for a stay question (the host can change it on the card). The host picks the topic from the same select as "Add a card" (default `rules`); the redirect lands on the card editor with the flash "Added to your guide. Check the card and save." A second tap finds the card by title (`card_for`) and opens it instead of making a twin; the page then shows "This answer is in your guide" with a link. No migration: `guest_question` gets no `item_id` column (the plan has no migration number left; 0014 is 0350's).

**Security.** Every page goes through `guest_guide._home` (`access.apartment`: owner check, archived 404) and `guest_handoff.get(apartment_id, qid)` (the row must belong to that property): another host's property and another property's question id under the host's own path both 404. POSTs are CSRF-guarded by `security.protect_host_post` on the router. Topic validated by `guest_guide.add_custom`; answer length capped server-side and `maxlength` client-side.

**Privacy.** Logs carry question id, apartment id and counts, never text (test `caplog`). The mail body has the property name and a link only. The guest's message is already redacted by 0350.

**Catalog.** Macros only (`ui_section`, `ui_table_begin`, `ui_badge`, `ui_empty`, `ui_textarea`, `ui_select`, `ui_button`, `ui_banner`); one primary button per template (list: none; question page: "Send to guest" while open, "Add to guide" once answered). Multi-line text is rendered as one `<p>` per line (no new class). Both templates are added to `docs/design/catalog.json` and the list page to the layout guard (`test_design_guardrails_browser.py`, with the `wide_host` property, so the empty state is what it checks). Copy: host en and cs through `host_i18n` (49 keys, script); guest copy `leon_host_answered` and `leon_host_answered_plain` in en, cs, de, es, fr, uk for 0352's label above a host turn.

Hard rules 2, 3, 4, 5, 6 (forms work without JavaScript), 7, 8, 9 apply. Rule 7: the layout guard covers the list page; CI runs the browser test if Chromium is missing locally.

### Anchors (verbatim; a missing anchor means STOP)

`App/app/leon.py` (0350): the comment line `    # 0351 adds its host alert hook directly below this line.` inside `_open_question` (4 spaces of indent).
`App/app/alerts.py`: `    "submission_stuck": ("notification.action.guests", "/reservations/{reservation}#guests"),`.
`App/app/mail.py`: in `KINDS`, the three lines `    "cancelled_with_guests",` / `    "deadline_at_risk",` / `    "deadline_digest",`; in `HOST_KINDS`, the three lines `    # digest. Neither goes to a guest.` / `    "deadline_at_risk",` / `    "deadline_digest",`.
`App/app/main.py`: the import line containing `guest_guide_view, guest_leon, invoices,` and the line `app.include_router(guest_guide_routes.router)`.
`App/app/routes/guest_guide.py`: `from .. import access, auth, config, guest_guide, guest_guide_import,` (start of the import line) and the two lines `        import_drafts=guest_guide_merge.drafted_count(apartment_id),` / `    )`.
`App/app/templates/guest_guide.html`: `{% block secondary_actions %}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }}{% endblock %}`.
`App/app/host_i18n.py`: `        "guest_guide.add.button": "Add a card",` and `        "guest_guide.add.button": "Přidat kartu",` (the script checks them). `App/app/i18n.py`: five lines starting `        "leon_about":`; `App/app/guest_uk_i18n.py`: one line starting `    "leon_about":`.
`docs/design/catalog.json`: `    "App/app/templates/guest_guide_qr.html"` (no comma after it). `App/tests/test_design_guardrails_browser.py`: `    "guest-guide-qr": "/apartments/{property_id}/guide/qr",`.
`docs/context/test-map.md`: the row starting `| Guest bot (Leon) |`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guest_handoff.py` | create | Copied from `docs/plans/0351-files/`: alert, mail, answer, dismiss, add_to_guide |
| `App/app/routes/guest_questions.py` | create | Copied: the two pages and three POSTs |
| `App/app/templates/guest_questions.html`, `guest_question.html` | create | Copied |
| `App/tests/test_guest_handoff.py` | create | Copied (14 tests) |
| `App/app/leon.py` | edit | Two lines: the hook after the `guest_question` insert |
| `App/app/alerts.py` | edit | One `_ACTIONS` row |
| `App/app/mail.py` | edit | `guest_question` in `KINDS` and `HOST_KINDS` |
| `App/app/main.py` | edit | Import and register the router before the guide router |
| `App/app/routes/guest_guide.py`, `App/app/templates/guest_guide.html` | edit | Open count and the "Guest questions (n)" button |
| `App/app/host_i18n.py`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | By the script `docs/plans/0351-files/add_handoff_i18n.py` (run, not copied) |
| `docs/design/catalog.json`, `App/tests/test_design_guardrails_browser.py` | edit | Two templates; one layout-guard route |
| `docs/context/test-map.md`, `docs/plans/guest-guide.md` | edit | One row each |

No other file may change. No migration.

## 4. Steps

Commands run from `App/` unless a step says the repo root.

### Step 1: preflight

From the repo root: `grep -c 'guest_question' App/app/leon.py; grep -c 'guest_guide_routes.router' App/app/main.py; python3 scripts/context_lint.py | grep 'next free'`. Expected: a number of `1` or more, `1`, and a line naming the next free task. If the first is `0`, 0350 is not merged: STOP.

### Step 2: copy the files

From the repo root:

```bash
cp docs/plans/0351-files/guest_handoff.py App/app/guest_handoff.py
cp docs/plans/0351-files/guest_questions.py App/app/routes/guest_questions.py
cp docs/plans/0351-files/guest_questions.html docs/plans/0351-files/guest_question.html App/app/templates/
cp docs/plans/0351-files/test_guest_handoff.py App/tests/test_guest_handoff.py
```

Command: `ls App/app/guest_handoff.py App/app/routes/guest_questions.py App/app/templates/guest_question.html App/app/templates/guest_questions.html App/tests/test_guest_handoff.py | wc -l`. Expected: `5`.

### Step 3: the hook in `App/app/leon.py`

Directly after the line `    # 0351 adds its host alert hook directly below this line.` insert (4 spaces of indent, like the comment):

```python
    from . import guest_handoff  # local: guest_handoff reads this module's tables
    guest_handoff.on_new_question(int(question_id))
```

`_open_question` is the one place 0350 writes a `guest_question` row (ask_host, emergency, the uncovered part of a multi-part answer, and messages passed unread), so the hook covers them all. Appends to an existing unread row (over the cap) do not call it: the alert count is unchanged.

Command: `grep -c 'guest_handoff' app/leon.py`. Expected: `2`.

### Step 4: the alert's button, `App/app/alerts.py`

Directly after `    "submission_stuck": ("notification.action.guests", "/reservations/{reservation}#guests"),` insert:

```python
    "guest_question": ("notification.action.guest_questions", "/apartments/{apartment}/guide/questions"),
```

Command: `grep -c 'guest_question' app/alerts.py`. Expected: `1`.

### Step 5: the mail kind, `App/app/mail.py`

In `KINDS`, directly after the three lines `    "cancelled_with_guests",` / `    "deadline_at_risk",` / `    "deadline_digest",` insert:

```python
    # 0351: one host mail per batch of open guest questions (Leon handoff).
    "guest_question",
```

In `HOST_KINDS`, directly after the three lines `    # digest. Neither goes to a guest.` / `    "deadline_at_risk",` / `    "deadline_digest",` insert:

```python
    "guest_question",
```

Command: `grep -c '"guest_question",' app/mail.py`. Expected: `2`.

### Step 6: register the router, `App/app/main.py`

In the import line replace `guest_guide_view, guest_leon, invoices,` with `guest_guide_view, guest_leon, guest_questions, invoices,`. Directly before the line `app.include_router(guest_guide_routes.router)` insert:

```python
# 0351 before the guide router: its '/guide/{item_id}' would otherwise catch '/guide/questions'.
app.include_router(guest_questions.router)
```

Command: `grep -n 'guest_questions' app/main.py | wc -l`. Expected: `2`.

### Step 7: the button on the guide page

`App/app/routes/guest_guide.py`: in the import line replace `from .. import access, auth, config, guest_guide, guest_guide_import,` with `from .. import access, auth, config, guest_guide, guest_guide_import, guest_handoff,`. Directly after the line `        import_drafts=guest_guide_merge.drafted_count(apartment_id),` (the one followed by `    )`) insert:

```python
        questions_open=guest_handoff.open_count(apartment_id),
```

`App/app/templates/guest_guide.html`: replace the whole line

```
{% block secondary_actions %}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }}{% endblock %}
```

with

```
{% block secondary_actions %}{{ ui_button(t('guest_guide.qr.link'), 'secondary', href=base_url ~ '/qr') }} {{ ui_button(t('guest_questions.link', n=questions_open), 'secondary', href=base_url ~ '/questions') }}{% endblock %}
```

Command: `grep -c 'guest_handoff' app/routes/guest_guide.py; grep -c 'questions_open' app/templates/guest_guide.html`. Expected: `2` and `1`.

### Step 8: copy

From the repo root: `python3 docs/plans/0351-files/add_handoff_i18n.py`. Expected: `added 49 host keys x 2 languages and 2 guest keys x 6 languages`. The script refuses to run twice. Command: `grep -c '"guest_question.send"' App/app/host_i18n.py; grep -c '"leon_host_answered"' App/app/i18n.py App/app/guest_uk_i18n.py`. Expected: `2`, then `5` and `1`.

### Step 9: catalog and layout guard

`docs/design/catalog.json`: replace the line `    "App/app/templates/guest_guide_qr.html"` with

```
    "App/app/templates/guest_guide_qr.html",
    "App/app/templates/guest_questions.html",
    "App/app/templates/guest_question.html"
```

`App/tests/test_design_guardrails_browser.py`: directly after `    "guest-guide-qr": "/apartments/{property_id}/guide/qr",` insert:

```python
    "guest-questions": "/apartments/{property_id}/guide/questions",
```

Command (repo root): `python3 scripts/design_lint.py 2>&1 | tail -2`. Expected: last line `design lint: OK`.

### Step 10: docs

`docs/context/test-map.md`: in the row starting `| Guest bot (Leon) |`, replace `` `test_leon.py `` with `` `test_leon.py test_guest_handoff.py `` (the backtick stays where it was). `docs/plans/guest-guide.md`: in the row starting `| 3 | [0351](../tasks/0351-guest-handoff.md) |`, change the last cell `todo` to `review`.

### Step 11: tests

The commands in §6.

## 5. Do not touch

`App/app/guest_guide.py`, `App/app/routes/guest_leon.py`, `App/app/needs_you.py`, `App/app/mail_notify.py`, `App/app/db.py`, every CSS file, every migration. No new dependency. Never log a message, an answer or a summary. Hard rules 2, 3, 4, 5, 8 and 9 of AGENTS.md apply.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_handoff.py -q --tb=short 2>&1 | tail -30`. Expected: `14 passed`.
- `.venv/bin/python -m pytest tests/test_leon.py tests/test_guest_guide_pages.py tests/test_host_i18n.py tests/test_guest_languages.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_alert_language.py tests/test_alert_stack.py tests/test_0280_short_notifications.py tests/test_account_emails.py tests/test_privacy_first.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed outside `test_host_i18n.py` (its three Vietnamese failures predate this brief; say so, do not fix).
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -k every_host_page -rs 2>&1 | tail -30`. Expected: `1 passed`, 0 skipped. If Chromium is missing on your machine (`Executable doesn't exist`), say so in the report; CI runs it.
- From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (`design lint: OK`) and `python3 scripts/context_lint.py 2>&1 | tail -3` (`context lint: OK`).

## 7. Acceptance

- [ ] `test_guest_handoff.py` passes (14): one alert per property that counts and resolves, one mail per batch with no message text, an urgent row turns the line red and mails at once and sorts first, an unread row shows its badge and the guest's words per line, the hook fires from `leon.reply` for `ask_host` and for `emergency`, no host address means alert only, no text in logs, another host's property and question 404 on every route, the list and the guide button, the empty state, the answer reaches the chat as written and the page shows it escaped, empty and over-long answers are 422, dismiss writes no guest turn, Add to guide makes a done host card with the door's visibility and never a twin, a bad topic is 422.
- [ ] `grep -c 'ui-' App/app/templates/guest_question.html` is above `0` and `python3 scripts/design_lint.py` says OK (catalog classes only).
- [ ] `grep -rn 'log\.\(info\|warning\|error\|exception\).*\(text\|answer\|summary\)' App/app/guest_handoff.py App/app/routes/guest_questions.py | wc -l` is `0`.
- [ ] No em dash in the new files: `grep -c '—' App/app/guest_handoff.py App/app/routes/guest_questions.py App/app/templates/guest_question.html App/app/templates/guest_questions.html` all `0`.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; 0350 is not merged (step 1); a test fails twice; you reach 30 tool calls or about 50k tokens (report `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0351-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, whether the browser guard ran, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`docs/plans/0351-files/guest_handoff.py` (`on_new_question`: never raises into the guest reply; the batch rule `count == 1`; `answer`; `add_to_guide` and `card_for`), `docs/plans/0351-files/guest_questions.py` (owner check on every route, router order), `guest_question.html` (escaping, one primary button), the `leon.py` hook. Known limits: `card_for` matches by title, so two questions with the same summary share one card; the question page has no browser screenshot (the layout guard sees only the list page's empty state; the orchestrator could not run Chromium in the scratch copy); the host mail is English only (`HOST_MAIL_LANGUAGE`, as every host mail); the `guide_item.source` value `guest_question` from 0341 stays unused because the owner wants a host-saved card.

## Owner steps

1. Merge as usual with `scripts/merge-pr-on-green.sh` once CI is green.
2. Nothing to configure: the mail uses the existing outbox and the alert the existing dashboard. Production Leon stays off until 0352 is merged (0350, owner step 4).
