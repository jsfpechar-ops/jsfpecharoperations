# 0319: Havel (AI): one-tap support hand-off and the 80% budget mail

Status: todo
Depends on: 0314, 0325 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0319-havel-support
Executor: Haiku 5.5 | Fits one session: 28 tool calls, 60k tokens

## 1. Objective

When Havel cannot help (plan section 8), the host sends the question to UbyHost support from the page with one tap, instead of the `mailto:` link 0312 shipped. Support gets a mail with the context it needs. The operator also gets one mail per AI feature per month when 80% of its budget is spent.

## 2. Context

Plan section 8 (the card, the mail fields, idempotency key `havel-support-<user id>-<sha256>[:16]`), section 9 (`SUPPORT_MAX = 3` a week). Rules: AGENTS.md 2 (the mail goes to UbyHost's own address, no third party), 6 (the form works without JavaScript), 7, 9.

Today (`grep -nF` 2026-10-24):

- `App/app/mail.py` line 28 `KINDS = (`, ending `    "door_code",` `    "door_code_notice",` `)`. Line 80 `HOST_KINDS = (`, ending `    "stay_fee_report",` `    "stay_fee_blocked",` `)`. A kind must be in `GUEST_KINDS` or `HOST_KINDS` (`tests/test_claim_mail.py` line 1792) and have `notification.mail_kind.<kind>` in en and cs (`test_mail_failed_alert.py`). `mask_email(addr)` at line 140; `enqueue(*, kind, idempotency_key, to_email, subject, payload, ...)` at line 206. Rows land in `email_outbox` (`test_signup.py` line 342 reads it).
- `App/app/mail_notify.py`: imports `config, db, deadlines, host_i18n, i18n, mail, validation` and `hashlib`; `HOST_MAIL_LANGUAGE = "en"`; helpers `_text(lang, key, **kw)`, `_app(path)`, `_block_heading`, `_block_paragraph` and `_block_fact(label, value)` (both escape), `_block_button(url, label)`, `_shell(*, lang, title, preheader, blocks, footer_lines)`, `_signup_footer(lang)`. The pattern to copy is `build_signup_admin` / `signup_admin` (line 2390 and 2466): facts list, text lines, blocks, `mail.enqueue`.
- `App/app/host_i18n.py`: en line 4909 `        "notification.mail_kind.signup_admin": "new sign-up notice",`; cs line 5071 `        "notification.mail_kind.signup_admin": "oznámení o nové registraci",`.
- `App/app/auth.py`: `current_user(request)` and `workspace_user(request)` return account rows with `email`, `display_name`, `username`.
- `config.OPERATOR_EMAIL` (default `support@ubyhost.com`); templates call `operator().email`.

From brief 0310 (`App/app/ai.py`): in `call()`, the line `    _record(feature, key_text, usage)`; `budget_fraction(feature)`, `month_spend_usd(feature)`, `today()`, `log`; `config.ai_monthly_usd(feature)`. `tests/ai_fake.py`: `FakeClient([...])`, `reply(data)`.

From brief 0311 (`App/app/havel.py`): `MAX_MESSAGE_CHARS = 600`, `MAX_SUMMARY_CHARS = 800`, `support_blocked(user_id)` (scope `havel_support`, since Monday), `read_history`, `record_stat(kind)`, `PAGES`.

From briefs 0312 to 0314 (`App/app/routes/havel.py`): the import line `from .. import access, ai, auth, cleaning_i18n, db, havel, havel_actions, havel_topics, host_i18n, security`; `_t`, `_item(role, text, **extra)`, `_thread(request, exchanges, last)`, `_page_context(...)` whose return dict ends `        "havel_show_topics": len(exchanges) == 0 and not items,` then `    }`; `render(request, "havel.html", ctx)`. `_havel_thread.html` loops `{% for item in havel_items %}` and has, inside `<div class="havel-links">`:

```jinja
      {% if item.support and operator().email %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="mailto:{{ operator().email }}{% if item.support_summary %}?body={{ item.support_summary | urlencode }}{% endif %}">{{ icon('send', 16) }}{{ t('havel.support.mailto') }}</a>{% endif %}
```

`_havel_topics.html` (0313) has:

```jinja
      {% if havel_answer.support and operator().email %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="mailto:{{ operator().email }}">{{ icon('send', 16) }}{{ t('havel.support.mailto') }}</a>{% endif %}
```

and `App/tests/test_havel_topics.py` asserts `    assert "mailto:" in support`. Keys that exist (en, cs, vi): `havel.support.title`, `.add`, `.send`, `.sent`, `.replies_to` (`%(email)s`), `.mailto`; anchors en `        "havel.support.mailto": "E-mail support",`, cs `        "havel.support.mailto": "Napsat podpoře e-mail",`, vi `    "havel.support.mailto": "Gửi e-mail cho hỗ trợ",`. Form macros in `_ui.html`: `ui_textarea(id, label, value='', name='', help='', error='', optional=false, rows=3, attrs='')`, `ui_button(label, variant='secondary', href='', type='button', ..., icon_name='', ...)`. The browser harness: `tests/test_havel_browser.py` (0324) fixture `origin` (uses `host`) and `_context(pw, origin, width, js=True)`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail.py | edit | kinds `havel_support`, `ai_budget` |
| App/app/mail_notify.py | edit | `havel_support`, `ai_budget` builders and senders |
| App/app/ai.py | edit | `_warn_budget` after `_record` |
| App/app/routes/havel.py | edit | `POST /havel/support`, two context keys |
| App/app/templates/_havel_support.html | new | the card |
| App/app/templates/_havel_thread.html, _havel_topics.html | edit | card replaces `mailto:` |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | keys |
| App/app/static/host2.css, App/app/templates/base.html | edit | card rule, cache key |
| App/tests/test_havel_support.py, App/tests/test_havel_support_browser.py | new | |
| App/tests/test_havel_topics.py | edit | one assert |

## 4. Steps

1. **Kinds.** In `App/app/mail.py` add `    "havel_support",` and `    "ai_budget",` (with the comment line `    # 0319: Havel support hand-off and the AI budget warning, both to the operator.`) before the `)` that closes `KINDS` (after `"door_code_notice",`) and before the `)` that closes `HOST_KINDS` (after `"stay_fee_blocked",`). Check: `grep -c '"havel_support",\|"ai_budget",' app/mail.py` prints `4`.

2. **Keys.** In `App/app/host_i18n.py` after the en line `"notification.mail_kind.signup_admin": "new sign-up notice",` insert:

```python
        "notification.mail_kind.havel_support": "Havel (AI) support request",
        "notification.mail_kind.ai_budget": "AI budget warning",
        "mail.havel_support.subject": "Havel (AI) support request: %(workspace)s",
        "mail.havel_support.heading": "A host asked for help",
        "mail.havel_support.intro": "Havel (AI) could not help this host. Reply to the account e-mail below.",
        "mail.havel_support.account": "Account e-mail",
        "mail.havel_support.workspace": "Workspace",
        "mail.havel_support.language": "Language",
        "mail.havel_support.page": "Page",
        "mail.havel_support.summary": "Summary",
        "mail.havel_support.note": "Host's note",
        "mail.havel_support.turn": "Host message %(n)s",
        "mail.ai_budget.subject": "AI budget %(percent)s%% spent: %(feature)s",
        "mail.ai_budget.body": "%(feature)s has spent $%(spent)s of its $%(cap)s budget for %(month)s. At 100%% it switches off until the 1st.",
        "mail.ai_budget.action": "Open Operations",
```

   and after the cs line `"notification.mail_kind.signup_admin": "oznámení o nové registraci",`:

```python
        "notification.mail_kind.havel_support": "žádost o podporu z Havla (AI)",
        "notification.mail_kind.ai_budget": "upozornění na rozpočet AI",
        "mail.havel_support.subject": "Žádost o podporu z Havla (AI): %(workspace)s",
        "mail.havel_support.heading": "Hostitel žádá o pomoc",
        "mail.havel_support.intro": "Havel (AI) tomuto hostiteli nepomohl. Odpovězte na e-mail účtu níže.",
        "mail.havel_support.account": "E-mail účtu",
        "mail.havel_support.workspace": "Pracovní prostor",
        "mail.havel_support.language": "Jazyk",
        "mail.havel_support.page": "Stránka",
        "mail.havel_support.summary": "Shrnutí",
        "mail.havel_support.note": "Poznámka hostitele",
        "mail.havel_support.turn": "Zpráva hostitele %(n)s",
        "mail.ai_budget.subject": "Rozpočet AI vyčerpán na %(percent)s %%: %(feature)s",
        "mail.ai_budget.body": "%(feature)s utratil $%(spent)s z rozpočtu $%(cap)s za %(month)s. Při 100 %% se vypne do 1. dne dalšího měsíce.",
        "mail.ai_budget.action": "Otevřít Provoz",
```

   After the en line `"havel.support.mailto": "E-mail support",` insert:

```python
        "havel.support.summary": "What Havel will send",
        "havel.support.empty": "Write what you need help with, then send.",
        "havel.support.limit": "You have sent three requests this week. Write to %(email)s instead.",
```

   after the cs line `"havel.support.mailto": "Napsat podpoře e-mail",`:

```python
        "havel.support.summary": "Co Havel odešle",
        "havel.support.empty": "Napište, s čím potřebujete pomoct, a odešlete.",
        "havel.support.limit": "Tento týden jste poslali už tři žádosti. Napište prosím na %(email)s.",
```

   and in `App/app/host_vi_i18n.py` after `    "havel.support.mailto": "Gửi e-mail cho hỗ trợ",`:

```python
    "havel.support.summary": "Nội dung Havel sẽ gửi",
    "havel.support.empty": "Hãy viết bạn cần giúp gì, rồi gửi.",
    "havel.support.limit": "Tuần này bạn đã gửi ba yêu cầu. Hãy viết đến %(email)s.",
```

   Check: `.venv/bin/python -m pytest tests/test_host_i18n.py -q 2>&1 | tail -3` passes.

3. **Mails.** Append to `App/app/mail_notify.py`:

```python
# --- 0319: Havel (AI) support hand-off and the AI budget warning ------------


def _one_line(value: str) -> str:
    return " ".join(str(value or "").split())


def build_havel_support(
    *, account_email: str, workspace: str, lang: str, page: str, summary: str, note: str, turns: List[str],
) -> Dict[str, str]:
    out = HOST_MAIL_LANGUAGE
    subject = _text(out, "mail.havel_support.subject", workspace=_one_line(workspace or account_email)[:80])
    heading = _text(out, "mail.havel_support.heading")
    intro = _text(out, "mail.havel_support.intro")
    facts = [
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
    turns: List[str],
) -> Optional[int]:
    """The host's question to UbyHost support; the same text twice is one mail."""
    content = build_havel_support(account_email=account_email, workspace=workspace, lang=lang, page=page,
                                  summary=summary, note=note, turns=turns)
    digest = hashlib.sha256(f"{summary}\n{note}".encode("utf-8")).hexdigest()[:16]
    return mail.enqueue(
        kind="havel_support",
        idempotency_key=f"havel-support-{user_id}-{digest}",
        to_email=config.OPERATOR_EMAIL,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": HOST_MAIL_LANGUAGE},
    )


def build_ai_budget(*, feature: str, month: str, spent: float, cap: float) -> Dict[str, str]:
    out = HOST_MAIL_LANGUAGE
    percent = int(spent / cap * 100) if cap > 0 else 100
    subject = _text(out, "mail.ai_budget.subject", percent=percent, feature=feature)
    body = _text(out, "mail.ai_budget.body", feature=feature, spent=f"{spent:.2f}", cap=f"{cap:.2f}", month=month)
    action = _text(out, "mail.ai_budget.action")
    link = _app("/admin/operations")
    footer = _signup_footer(out)
    text = "\n".join([body, "", f"{action}: {link}", "", "--", *footer])
    blocks = [_block_heading(subject), _block_paragraph(body), _block_button(link, action)]
    return {"subject": subject, "text": text,
            "html": _shell(lang=out, title=subject, preheader=body, blocks=blocks, footer_lines=footer)}


def ai_budget(*, feature: str, month: str, spent: float, cap: float) -> Optional[int]:
    """One warning per feature per month (key ai-budget-<feature>-<YYYY-MM>)."""
    content = build_ai_budget(feature=feature, month=month, spent=spent, cap=cap)
    return mail.enqueue(
        kind="ai_budget",
        idempotency_key=f"ai-budget-{feature}-{month}",
        to_email=config.OPERATOR_EMAIL,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": HOST_MAIL_LANGUAGE},
    )
```

   Check: `.venv/bin/python -c "from app import mail_notify as m; print(m.build_ai_budget(feature='havel', month='2026-10', spent=8.1, cap=10)['subject'])"` prints `AI budget 81% spent: havel`.

4. **Budget hook.** In `App/app/ai.py` replace `    _record(feature, key_text, usage)` with:

```python
    _record(feature, key_text, usage)
    _warn_budget(feature)
```

   and add above `def call(`:

```python
def _warn_budget(feature: str) -> None:
    """Mail the operator once a month when 80% of the feature's budget is spent (0319)."""
    try:
        if budget_fraction(feature) < 0.8:
            return
        from . import mail_notify  # lazy: mail_notify imports much of the app

        mail_notify.ai_budget(feature=feature, month=today().strftime("%Y-%m"),
                              spent=month_spend_usd(feature), cap=config.ai_monthly_usd(feature))
    except Exception:  # a mail problem must never cost the host the answer
        log.warning("ai budget mail failed feature=%s", feature)
```

5. **Card.** Create `App/app/templates/_havel_support.html`:

```jinja
{#- 0319: the support hand-off (plan section 8). Works without JavaScript; the
    newest Havel reply carries it, prefilled with Havel's English summary. -#}
{% from "_ui.html" import ui_textarea, ui_button %}
{% if havel_support_blocked %}
<p class="havel-meta">{{ t('havel.support.limit', email=operator().email) }}</p>
{% else %}
<form method="post" action="/havel/support" class="havel-support" data-havel-support>
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="history" value="{{ havel_history }}">
  <input type="hidden" name="history_sig" value="{{ havel_history_sig }}">
  <input type="hidden" name="page" value="{{ havel_page }}">
  <input type="hidden" name="return_to" value="{{ havel_return_to }}">
  <h3 class="havel-support-title">{{ t('havel.support.title') }}</h3>
  {{ ui_textarea('havel-support-summary', t('havel.support.summary'), value=havel_support_prefill or '', name='summary', rows=4, attrs='maxlength="800"') }}
  {{ ui_textarea('havel-support-note', t('havel.support.add'), name='note', optional=true, rows=2, attrs='maxlength="600"') }}
  {% if havel_support_to %}<p class="havel-meta">{{ t('havel.support.replies_to', email=havel_support_to) }}</p>{% endif %}
  {{ ui_button(t('havel.support.send'), 'primary', type='submit', icon_name='send') }}
</form>
{% endif %}
```

   In `_havel_thread.html` replace the `mailto:` line of section 2 with:

```jinja
      {% if item.support and loop.last %}{% with havel_support_prefill = item.support_summary %}{% include "_havel_support.html" %}{% endwith %}{% endif %}
```

   In `_havel_topics.html` replace its `mailto:` line with:

```jinja
      {% if havel_answer.support %}{% with havel_support_prefill = '' %}{% include "_havel_support.html" %}{% endwith %}{% endif %}
```

   In `App/tests/test_havel_topics.py` replace `    assert "mailto:" in support` with `    assert 'action="/havel/support"' in support`. Check: `grep -c 'mailto:' app/templates/_havel_thread.html app/templates/_havel_topics.html` prints `0` twice. `t('havel.support.mailto')` stays in the i18n files (unused keys are allowed; say so in the report if a test objects, then delete it in en, cs and vi).

6. **CSS.** Append to the end of `App/app/static/host2.css`:

```css
/* 0319: Havel support card, full width under the reply's links */
.havel-links .havel-support { flex-basis: 100%; display: grid; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--line); border-radius: var(--card-radius); background: var(--surface); }
.havel-support-title { margin: 0; font-size: var(--size-16); }
.havel-links > .havel-meta { flex-basis: 100%; }
```

   Then bump the cache key: `grep -n 'host2.css?v=' app/templates/base.html`, replace that version with `20261024-0319`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3` and from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3` (expected OK).

7. **Route.** In `App/app/routes/havel.py` change the import line to `from .. import access, ai, auth, cleaning_i18n, config, db, havel, havel_actions, havel_topics, host_i18n, mail, mail_notify, rate_limit, security`. In `_page_context`, after `        "havel_show_topics": len(exchanges) == 0 and not items,` insert:

```python
        "havel_support_to": mail.mask_email(str((auth.current_user(request) or {"email": ""})["email"] or "")),
        "havel_support_blocked": havel.support_blocked(uid),
```

   Append at the end of the file:

```python
@router.post("/havel/support")
async def havel_support(request: Request):
    """Plan section 8: the host's one tap sends the summary to UbyHost support."""
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    uid = int(account["id"])
    form = await request.form()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    page = str(form.get("page", ""))
    page = page if page in havel.PAGES else ""
    return_to = security.safe_local_path(str(form.get("return_to", "")), "/havel")
    summary = str(form.get("summary", "")).strip()[: havel.MAX_SUMMARY_CHARS]
    note = str(form.get("note", "")).strip()[: havel.MAX_MESSAGE_CHARS]
    items = _thread(request, exchanges, None)
    if havel.support_blocked(uid):
        items.append(_item("havel", _t(request, "havel.support.limit", email=config.OPERATOR_EMAIL)))
    elif not summary and not note:
        items.append(_item("havel", _t(request, "havel.support.empty"), support=True))
    else:
        workspace = auth.workspace_user(request) or account
        mail_notify.havel_support(
            user_id=uid, account_email=str(account["email"] or ""),
            workspace=str(workspace["display_name"] or workspace["username"] or ""),
            lang=request.state.lang, page=page, summary=summary, note=note,
            turns=[exchange["host"] for exchange in exchanges][-4:],
        )
        rate_limit.record("havel_support", str(uid))
        havel.record_stat("support_sent")
        items.append(_item("havel", _t(request, "havel.support.sent")))
    ctx = _page_context(request, uid, items, exchanges, page=page, return_to=return_to)
    return render(request, "havel.html", ctx)
```

   Check: `.venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if r.path == '/havel/support'])"` prints `['/havel/support']`.

8. **Tests.** Create `App/tests/test_havel_support.py`:

```python
"""0319: the support hand-off and the 80% budget mail."""
import re

import pytest

from app import ai, config, db, havel, mail, mail_notify
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import host  # noqa: F401

ESCALATE = {"kind": "escalate", "reply": "I can send this to the team.", "sources": [], "links": [],
            "action": None, "support_summary": "Host sees error 4 on a police report."}


@pytest.fixture
def on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    db.execute("DELETE FROM rate_limit_event WHERE scope LIKE 'havel_%'")
    db.execute("DELETE FROM email_outbox WHERE kind IN ('havel_support', 'ai_budget')")
    yield
    ai.set_client_for_tests(None)


def _csrf(client):
    return re.search(r'name="_csrf" value="([^"]+)"', client.get("/havel").text).group(1)


def _outbox(kind):
    return db.query("SELECT to_email, subject, payload FROM email_outbox WHERE kind = ?", (kind,))


def test_escalate_shows_the_card_prefilled_and_sending_queues_one_mail(host, on):
    ai.set_client_for_tests(FakeClient([reply(ESCALATE)]))
    form = {"_csrf": _csrf(host), "history": "", "history_sig": "", "page": "reports", "device": "phone",
            "topic": "", "message": "Error 4 on my report"}
    page = host.post("/havel", data=form).text
    assert 'action="/havel/support"' in page and "Host sees error 4 on a police report." in page
    assert "mailto:" not in page
    history = re.search(r'name="history" value="([^"]*)"', page).group(1).replace("&#34;", '"').replace("&quot;", '"')
    sig = re.search(r'name="history_sig" value="([^"]*)"', page).group(1)
    send = {"_csrf": form["_csrf"], "history": history, "history_sig": sig, "page": "reports",
            "summary": "Host sees error 4 on a police report.", "note": "Since Monday"}
    done = host.post("/havel/support", data=send).text
    assert "Forwarded to the UbyHost team." in done
    host.post("/havel/support", data=send)
    rows = _outbox("havel_support")
    assert len(rows) == 1 and rows[0]["to_email"] == mail.normalise_email(config.OPERATOR_EMAIL)
    body = str(rows[0]["payload"])
    assert "Since Monday" in body and "Error 4 on my report" in body and "reports" in body


def test_empty_request_is_not_sent_and_the_weekly_cap_holds(host, on):
    csrf = _csrf(host)
    empty = host.post("/havel/support", data={"_csrf": csrf, "summary": " ", "note": ""}).text
    assert "Write what you need help with" in empty and not _outbox("havel_support")
    for n in range(havel.SUPPORT_MAX):
        host.post("/havel/support", data={"_csrf": csrf, "summary": f"Question {n}"})
    blocked = host.post("/havel/support", data={"_csrf": csrf, "summary": "One more"}).text
    assert "three requests this week" in blocked
    assert len(_outbox("havel_support")) == havel.SUPPORT_MAX


def test_budget_mail_once_a_month_at_80_percent(on, monkeypatch):
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 0.0001)
    data = {"kind": "answer", "reply": "Hi", "sources": [], "links": [], "action": None, "support_summary": None}
    ai.set_client_for_tests(FakeClient([reply(data)]))
    db.execute("DELETE FROM ai_usage WHERE feature = 'havel'")
    ai.call("havel", ["system"], [{"role": "user", "content": "hi"}], {"type": "object"})
    rows = _outbox("ai_budget")
    assert len(rows) == 1 and "havel" in rows[0]["subject"]
    mail_notify.ai_budget(feature="havel", month=ai.today().strftime("%Y-%m"), spent=1.0, cap=1.0)
    assert len(_outbox("ai_budget")) == 1
```

   (`email_outbox` stores `to_email` normalised and `payload` as JSON text, `mail.py` line 246.) Command in section 6 (first). Expected: 3 passed.

9. **Browser.** Create `App/tests/test_havel_support_browser.py`:

```python
"""0319: the support card at 390 px without JavaScript, and at 1280 px in the panel flow."""
from pathlib import Path

from playwright import sync_api

from app import ai
from tests.ai_fake import FakeClient, reply
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_havel_support import ESCALATE
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0319"


def test_support_card_sends_without_javascript_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(ESCALATE)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/havel")
        page.fill("#havel-message", "Error 4 on my report")
        page.locator("[data-havel-form] button[type=submit]").click()
        card = page.locator("[data-havel-support]")
        card.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        card.screenshot(path=str(SHOTS / "support-card-390.png"))
        page.fill("#havel-support-note", "Since Monday")
        card.locator("button[type=submit]").click()
        page.get_by_text("Forwarded to the UbyHost team.").first.wait_for()
        page.screenshot(path=str(SHOTS / "support-sent-390.png"))
        browser.close()
```

   If the composer's submit button or the message field id differs, read `grep -n 'type="submit"\|id="havel-message"' app/templates/_havel_thread.html app/templates/havel.html` and adjust the selectors only. Command in section 6 (second). Expected: 1 passed, 0 skipped, two PNGs; look at the card once (full width, labels above fields, one primary button).

## 5. Do not touch

`havel.py`, `havel_prompt.py`, the composer and `havel.js` (the card is a plain form; the panel's fetch stays on `[data-havel-form]`), other mail kinds, `test_mail*.py`.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_havel_support.py tests/test_havel_page.py tests/test_havel_topics.py tests/test_ai.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_havel_support_browser.py tests/test_havel_browser.py -q --tb=short -x -rs 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k havel -q --tb=short -rs 2>&1 | tail -10` and `.venv/bin/python -m pytest tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -10` (0 skipped)
- Mail row: `.venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_*_mail.py tests/test_notification_copy.py tests/test_signup.py -q --tb=short -x 2>&1 | tail -15` (`test_claim_mail.py` checks the kind groups)
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py -q 2>&1 | tail -5`; from the repo root `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] An escalate reply shows the card prefilled; Send queues one `havel_support` mail to the operator; the same text twice is one mail.
- [ ] Empty send asks for text; the fourth send in a week shows the limit sentence and sends nothing.
- [ ] Off or over cap (support items from 0312) show the card empty.
- [ ] `ai_budget` mail queued once per feature and month; a mail error never breaks `ai.call`.
- [ ] No `mailto:` left in the Havel templates; screenshots `docs/tasks/screenshots-0319/support-card-390.png`, `support-sent-390.png`.
- [ ] All section 6 commands pass, browser 0 skipped.

## 8. Stop and ask

- `mail.enqueue` refuses a kind or needs an argument not in section 2.
- `test_claim_mail.py` or `test_mail_failed_alert.py` asks for something more than the group and the `notification.mail_kind` key.

## 9. Report

Write `docs/tasks/0319-report.md` (600 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, both screenshots, deviations.

## Risk list (for the reviewer)

- The mail holds what the host typed (summary, note, last 4 turns): personal data to the operator's own mailbox, covered by the support purpose; retention of `email_outbox` rows applies.
- The kind is `ai_budget`, not the plan's `havel_budget`: the warning is for every AI feature (the guest bot too).
- The hash covers summary and note, so a second request with a new note is a new mail.
- `_warn_budget` runs one extra SUM query per AI call.
- The weekly `SUPPORT_MAX` cap counts `rate_limit_event` rows, and the nightly job deletes every row older than 24 hours (`retention.py` `_rate_limit_retention_step`, `config.RATE_LIMIT_RETENTION_HOURS`, verified 2026-10-24). The cap only holds once 0320's 32-day keep for `havel_*` scopes is merged. Havel stays off (`UBYHOST_AI_FEATURES` unset) until then; 0323 lists 0320 as a prerequisite.

## Owner steps

0. Do not set `UBYHOST_AI_FEATURES` on staging or production before 0320 is merged (see the risk list: the nightly purge resets Havel's caps until then).
1. Owner item 4 is answered (2026-10-24): "usually within a few hours", already in `havel.support.sent` (0312, 0325). The urgent checkbox and phone call come in 0330.
2. After deploy, send one test request from staging and check it arrives at the support mailbox.
