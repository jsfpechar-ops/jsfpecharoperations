# 0330: Havel (AI): "It's urgent, please call me" on the support card

Status: todo
Depends on: 0319 | Base commit: f4c76d7 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0330-havel-support-urgent
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

The host can mark a support request urgent and give a phone number, prefilled from their business contact phone; the operator mail then starts with "URGENT" and shows the number, and the team calls the host (owner, 2026-10-24, plan section 8 step 5). Split from 0319 for the one-session limit.

## 2. Context

Rules: AGENTS.md 2 (no new stored field: the phone travels only in the outbox mail, purged after 14 days by `mail.purge_old`), 6 (works without JavaScript), 7, 9. CSRF stays (the card's hidden `_csrf`); the 0319 caps stay (`SUPPORT_MAX = 3` a week, recorded only when a mail is queued).

From 0319 (`grep -nF` before each step; if an anchor is missing, stop):

- `App/app/templates/_havel_support.html` has the line `  {{ ui_textarea('havel-support-note', t('havel.support.add'), name='note', optional=true, rows=2, attrs='maxlength="600"') }}` and imports `{% from "_ui.html" import ui_textarea, ui_button %}`. `_ui.html` has `ui_check(id, label, name='', checked=false, value='1', attrs='')` and `ui_field(id, label, name='', value='', type='text', help='', error='', optional=false, attrs='', placeholder='')`; both autoescape their values.
- `App/app/routes/havel.py`: `_page_context` has the line `        "havel_support_blocked": havel.support_blocked(uid),`; `havel_support` has the lines `    note = str(form.get("note", "")).strip()[: havel.MAX_MESSAGE_CHARS]`, `        items.append(_item("havel", _t(request, "havel.support.empty"), support=True))` and `            turns=[exchange["host"] for exchange in exchanges][-4:],`. `access` is imported.
- `App/app/access.py` line 149 `def entities(request: Request, include_archived: bool = False):` returns the host's `legal_entity` rows (`SELECT *`, so `contact_phone` is there; column from `db.py` line 119).
- `App/app/mail_notify.py`: `def build_havel_support(` and `def havel_support(` (0319 step 3), followed by `def build_ai_budget(`.
- `App/app/host_i18n.py` en `        "mail.havel_support.turn": "Host message %(n)s",`, cs `        "mail.havel_support.turn": "Zpráva hostitele %(n)s",`; en `        "havel.support.limit": "You have sent three requests this week. Write to %(email)s instead.",`, cs `        "havel.support.limit": "Tento týden jste poslali už tři žádosti. Napište prosím na %(email)s.",`; `App/app/host_vi_i18n.py` `    "havel.support.limit": "Tuần này bạn đã gửi ba yêu cầu. Hãy viết đến %(email)s.",`. `havel.support.sent` en `"Forwarded to the UbyHost team. They know about it and usually reply within a few hours."` (0312), cs `"Předáno týmu UbyHostu. Vědí o tom a obvykle odpoví do několika hodin."`, vi `"Đã chuyển đến đội UbyHost. Họ đã biết và thường trả lời trong vòng vài giờ."` (0325).
- Tests: `tests/test_havel_support.py` has `on`, `_csrf(client)`, `_outbox(kind)`, `ESCALATE`; `tests/test_havel_support_browser.py` the 390 px flow.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_havel_support.html | edit | checkbox and phone field |
| App/app/routes/havel.py | edit | prefill, read, check, pass on |
| App/app/mail_notify.py | edit | `urgent`, `phone` in the support mail |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | keys, `havel.support.sent` |
| App/tests/test_havel_support_urgent.py | new | |

## 4. Steps

Commit after each step: `0330 step k`.

1. **Card.** In `_havel_support.html` change the import to `{% from "_ui.html" import ui_textarea, ui_button, ui_check, ui_field %}` and insert after the `havel-support-note` line:

```jinja
  {{ ui_check('havel-support-urgent', t('havel.support.urgent'), name='urgent') }}
  {{ ui_field('havel-support-phone', t('havel.support.phone'), name='phone', value=havel_support_phone or '', type='tel', help=t('havel.support.phone_help'), optional=true, attrs='maxlength="40" autocomplete="tel"') }}
```

   Check: `grep -c 'havel-support-urgent\|havel-support-phone' app/templates/_havel_support.html` prints `2`.

2. **Route.** In `routes/havel.py` add `import re` at the top if `grep -n '^import re' app/routes/havel.py` prints nothing. Above `def _page_context(` add:

```python
def _contact_phone(request: Request) -> str:
    """0330: the host's existing business contact phone, only to prefill the urgent call field."""
    for entity in access.entities(request):
        phone = str(entity["contact_phone"] or "").strip()
        if phone:
            return phone[:40]
    return ""
```

   After `        "havel_support_blocked": havel.support_blocked(uid),` insert `        "havel_support_phone": _contact_phone(request),`. After the `note = ...` line insert:

```python
    urgent = str(form.get("urgent", "")) == "1"
    phone = re.sub(r"[^0-9+() -]", "", " ".join(str(form.get("phone", "")).split()))[:40].strip() if urgent else ""
```

   After the `havel.support.empty` line insert:

```python
    elif urgent and sum(ch.isdigit() for ch in phone) < 6:
        items.append(_item("havel", _t(request, "havel.support.phone_needed"), support=True, support_summary=summary))
```

   Replace `            turns=[exchange["host"] for exchange in exchanges][-4:],` with `            turns=[exchange["host"] for exchange in exchanges][-4:], urgent=urgent, phone=phone,`. Check: `grep -c 'urgent' app/routes/havel.py` prints `4` or more.

3. **Mail.** In `mail_notify.py` replace everything from `def build_havel_support(` up to (not including) `def build_ai_budget(` with:

```python
URGENT_PREFIX = "URGENT: "  # owner, 2026-10-24: the team calls the host


def build_havel_support(
    *, account_email: str, workspace: str, lang: str, page: str, summary: str, note: str, turns: List[str],
    urgent: bool = False, phone: str = "",
) -> Dict[str, str]:
    out = HOST_MAIL_LANGUAGE
    subject = _text(out, "mail.havel_support.subject", workspace=_one_line(workspace or account_email)[:80])
    subject = (URGENT_PREFIX + subject) if urgent else subject
    heading = _text(out, "mail.havel_support.heading")
    intro = _text(out, "mail.havel_support.intro")
    facts = [(_text(out, "mail.havel_support.phone"), _one_line(phone) or "-")] if urgent else []
    facts += [
        (_text(out, "mail.havel_support.account"), account_email or "-"),
        (_text(out, "mail.havel_support.workspace"), workspace or "-"),
        (_text(out, "mail.havel_support.language"), lang),
        (_text(out, "mail.havel_support.page"), page or "-"),
        (_text(out, "mail.havel_support.summary"), summary or "-"),
        (_text(out, "mail.havel_support.note"), note or "-"),
    ]
    facts.extend((_text(out, "mail.havel_support.turn", n=i), turn) for i, turn in enumerate(turns, 1))
    footer = _signup_footer(out)
    text = "\n".join([intro, "", *[f"{label}: {value}" for label, value in facts], "", "--", *footer])
    blocks = [_block_heading(heading), _block_paragraph(intro)]
    blocks.extend(_block_fact(label, value) for label, value in facts)
    return {"subject": subject, "text": text,
            "html": _shell(lang=out, title=heading, preheader=intro, blocks=blocks, footer_lines=footer)}


def havel_support(
    *, user_id: int, account_email: str, workspace: str, lang: str, page: str, summary: str, note: str,
    turns: List[str], urgent: bool = False, phone: str = "",
) -> Optional[int]:
    """The host's question to UbyHost support; the same request twice is one mail."""
    content = build_havel_support(account_email=account_email, workspace=workspace, lang=lang, page=page,
                                  summary=summary, note=note, turns=turns, urgent=urgent, phone=phone)
    digest = hashlib.sha256(f"{summary}\n{note}\n{int(urgent)}\n{phone}".encode("utf-8")).hexdigest()[:16]
    return mail.enqueue(
        kind="havel_support",
        idempotency_key=f"havel-support-{user_id}-{digest}",
        to_email=config.OPERATOR_EMAIL,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": HOST_MAIL_LANGUAGE},
    )


```

   Check: `.venv/bin/python -c "from app import mail_notify as m; print(m.build_havel_support(account_email='a@b.cz', workspace='W', lang='cs', page='', summary='s', note='', turns=[], urgent=True, phone='+420 777 100 200')['subject'])"` prints `URGENT: Havel (AI) support request: W`.

4. **Keys.** In `host_i18n.py` after the en `mail.havel_support.turn` line insert `        "mail.havel_support.phone": "Urgent: call the host on",`; after the cs one `        "mail.havel_support.phone": "Naléhavé: zavolejte hostiteli na",`. After the en `havel.support.limit` line insert:

```python
        "havel.support.urgent": "It's urgent, please call me",
        "havel.support.phone": "Phone number for the call",
        "havel.support.phone_help": "Used only for this call. Not saved to your account.",
        "havel.support.phone_needed": "Add a phone number so the team can call you.",
```

   after the cs one:

```python
        "havel.support.urgent": "Je to naléhavé, zavolejte mi prosím",
        "havel.support.phone": "Telefon pro zavolání",
        "havel.support.phone_help": "Použijeme ho jen pro toto zavolání. Do účtu se neukládá.",
        "havel.support.phone_needed": "Doplňte telefon, ať vám tým může zavolat.",
```

   and in `host_vi_i18n.py` after its `havel.support.limit` line:

```python
    "havel.support.urgent": "Việc gấp, vui lòng gọi cho tôi",
    "havel.support.phone": "Số điện thoại để gọi",
    "havel.support.phone_help": "Chỉ dùng cho cuộc gọi này. Không lưu vào tài khoản của bạn.",
    "havel.support.phone_needed": "Hãy thêm số điện thoại để đội có thể gọi cho bạn.",
```

   Then change the three `havel.support.sent` values by appending one sentence: en ` If you marked it urgent, they will call you.`, cs ` Pokud jste označili, že je to naléhavé, zavolají vám.`, vi ` Nếu bạn đánh dấu là khẩn cấp, họ sẽ gọi cho bạn.` Check: `grep -c 'they will call you' app/host_i18n.py` prints `1`.

5. **Tests.** Create `App/tests/test_havel_support_urgent.py`:

```python
"""0330: the urgent checkbox, the prefilled phone and the URGENT operator mail."""
import json

from app import db
from tests.test_havel_support import _csrf, _outbox, on  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401


def _send(client, **extra):
    return client.post("/havel/support", data={"_csrf": _csrf(client), "summary": "Report failed", **extra}).text


def test_card_prefills_the_business_phone_escaped(host, on):
    saved = db.query("SELECT id, contact_phone FROM legal_entity")
    try:
        db.execute("UPDATE legal_entity SET contact_phone = ?", ('+420 777 100 200"><b>',))
        page = _send(host, summary=" ")  # the empty-request reply shows the card
        assert 'name="urgent"' in page and "It&#39;s urgent, please call me" in page
        assert "+420 777 100 200&#34;&gt;&lt;b&gt;" in page and '200"><b>' not in page
    finally:
        for row in saved:
            db.execute("UPDATE legal_entity SET contact_phone = ? WHERE id = ?", (row["contact_phone"], row["id"]))


def test_urgent_mail_has_prefix_and_phone_and_plain_mail_has_neither(host, on):
    _send(host, note="plain", phone="+420 777 100 200")
    _send(host, note="call", urgent="1", phone="+420 777 <b>100 200")
    rows = sorted(_outbox("havel_support"), key=lambda r: r["subject"])
    assert len(rows) == 2
    plain, urgent = rows[0], rows[1]
    assert not plain["subject"].startswith("URGENT") and "777" not in json.loads(plain["payload"])["text"]
    assert urgent["subject"].startswith("URGENT: ")
    body = json.loads(urgent["payload"])["text"]
    assert "Urgent: call the host on: +420 777 100 200" in body and "<b>" not in body


def test_urgent_without_phone_sends_nothing_and_keeps_the_cap(host, on):
    page = _send(host, urgent="1", phone="12")
    assert "Add a phone number so the team can call you." in page
    assert not _outbox("havel_support")
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'havel_support'")["n"] == 0
```

   The first test reads the card from the empty-request reply (0319 shows it with `havel.support.empty`). If Jinja escapes `"` as `&quot;` here, change only that string and say so. If the `host` fixture has no `legal_entity` row, insert the phone assertion through `mail_notify.build_havel_support` only and report it. Command in section 6 (first). Expected: 3 passed.

6. **Browser.** In `App/tests/test_havel_support_browser.py`, in the 390 px test, before `card.screenshot(...)` insert `        assert card.locator("#havel-support-urgent").is_visible() and card.locator("#havel-support-phone").is_visible()`, and after `page.fill("#havel-support-note", "Since Monday")` insert `        page.check("#havel-support-urgent")` and `        page.fill("#havel-support-phone", "+420 777 100 200")`. Change the screenshot folder to `screenshots-0330` only if `screenshots-0319` is already committed. Command in section 6 (second). Expected: 1 passed, 0 skipped; look at the card at 390 (checkbox and phone full width, no overflow).

## 5. Do not touch

`havel.py`, the caps, `mail.py`, `retention.py`, `db.SCHEMA` and migrations (no new field), other mail kinds, `legal_entity` writes (the prefill only reads).

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_havel_support_urgent.py tests/test_havel_support.py tests/test_havel_page.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_havel_support_browser.py -q --tb=short -x -rs 2>&1 | tail -10` and `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k havel -q --tb=short -rs 2>&1 | tail -10` (0 skipped)
- Mail row: `.venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_notification_copy.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_privacy_first.py -q 2>&1 | tail -5`; from the repo root `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] The card shows "It's urgent, please call me" and a phone field, prefilled and escaped from the business contact phone when there is one.
- [ ] Urgent with a phone: one mail, subject starts `URGENT: `, body shows the cleaned number; not urgent: no prefix and no phone in the mail.
- [ ] Urgent without a usable phone: the sentence asks for one, no mail, no cap row.
- [ ] No new table, column or stored field; CSRF and `SUPPORT_MAX` unchanged; screenshot at 390.
- [ ] All section 6 commands pass, browser 0 skipped.

## 8. Stop and ask

- An anchor in section 2 is missing (0319 not merged or changed).
- A test asks for a `notification.mail_kind` or a retention line: there is no new kind or field, so report it.

## 9. Report

Write `docs/tasks/0330-report.md` (400 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, the screenshot path.

## Risk list (for the reviewer)

- The phone is sent only when "urgent" is ticked. It lives in `email_outbox` 14 days, then in the support mailbox under that mailbox's retention (ROPA "Support mailbox", open for counsel; 0329 names it).
- Prefill reads `legal_entity.contact_phone`, which the host gave as a business contact; the host sees and can change it before sending, and nothing is written back.
- If the phone is missing, the note and the tick are not kept on the re-shown card; the host types them again.
- The digest now covers urgent and phone, so a second send marked urgent is a new mail.

## Owner steps

1. Decide who answers the phone for "URGENT" mails and in which hours; the copy promises a call, not a time.
2. After deploy, send one urgent test request from staging and check the subject and number in the support mailbox.
