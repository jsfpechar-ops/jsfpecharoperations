# 0333: Havel (AI): when a limit is hit, pass the host's message to support

Status: todo
Depends on: 0319, 0332 | Base commit: 4057916 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0333-havel-limit-forward
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 35k tokens

## 1. Objective

The owner (2026-10-24) wants Havel to cost as little as possible: 6 messages per conversation, 8 a week and 15 a month per host (the defaults are already lowered in 0310 and 0311). When the host hits one of those limits, or the monthly or daily AI budget is spent, Havel does not call the model. It sends the host's message to UbyHost support through the existing 0319 hand-off and says "I've passed your message to the UbyHost team. They usually reply within a few hours by e-mail." The 0319 cap of 3 support sends per host per week still applies, so this cannot flood the support mailbox.

## 2. Context

- Plan `docs/plans/havel-support-assistant.md` sections 8 and 9.
- `App/app/routes/havel.py`, after 0312, 0319 and 0332. `havel_send` (POST `/havel`) has, in this order, `key = havel.local_reply(message)`, the `elif len(exchanges) >= havel.MAX_EXCHANGES:` branch, `elif not ai.enabled(havel.FEATURE):`, `limit = havel.limit_state(uid)` and the `except ai.AIBudgetError as exc:` branch, then `if len(items) == 1:`. `grep -n` each line before editing. The module already imports `auth`, `config`, `mail_notify`, `rate_limit` (0319); check with `grep -n '^from\|^import' app/routes/havel.py`.
- 0319: `mail_notify.havel_support(*, user_id, account_email, workspace, lang, page, summary, note, turns)` (the same summary and note twice is one mail), `havel.support_blocked(uid)`, `rate_limit.record("havel_support", str(uid))`, `havel.record_stat(kind)`.
- Which limits forward: `limit_week`, `limit_month`, the conversation cap (`MAX_EXCHANGES`), `AIBudgetError` with `month` or `day`. Which do not forward: greetings and thanks (`local_reply`), too-long or empty messages, `limit_burst` (5 in 10 minutes: the host just waits), `paused` (3 refusals: likely abuse), and Havel switched off (`not ai.enabled`). When `support_blocked(uid)` is true the host sees the normal limit text as today.

## 3. Files

| File | Change | Why |
|---|---|---|
| App/app/routes/havel.py | edit | `_forward` helper; forward in four branches |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | `havel.forwarded` en, cs, vi |
| App/tests/test_havel_limit_forward.py | new | |

## 4. Steps

1. **Helper.** In `App/app/routes/havel.py`, directly above `@router.post("/havel")`, add:

```python
def _forward(request: Request, uid: int, message: str, exchanges: List[Dict[str, str]], page: str,
             reason: str) -> bool:
    """0333: a limit was hit, so the host's message goes to support instead of the model.

    False when the weekly support cap is used up; the caller then shows the limit text.
    """
    if havel.support_blocked(uid):
        return False
    account = auth.current_user(request)
    workspace = auth.workspace_user(request) or account
    mail_notify.havel_support(
        user_id=uid, account_email=str(account["email"] or ""),
        workspace=str(workspace["display_name"] or workspace["username"] or ""),
        lang=request.state.lang, page=page,
        summary=f"Havel limit reached ({reason}). The host's message below was forwarded without an AI answer.",
        note=message, turns=[exchange["host"] for exchange in exchanges][-4:],
    )
    rate_limit.record("havel_support", str(uid))
    havel.record_stat("support_forwarded")
    return True
```

   If `List` or `Dict` is not imported from `typing` in this file, add them to the existing `from typing import` line.

2. **Branches.** In `havel_send`:
   - Directly after the line `        support = False` (inside `elif message:`), add `        forward, prior = "", exchanges`.
   - In the `elif len(exchanges) >= havel.MAX_EXCHANGES:` branch, add `            forward = "conversation"` as its first line (before `reply_text = ...`). `prior` still holds the old exchanges after `exchanges = []`.
   - In the `if limit:` branch, after `havel.record_stat("limit_hit")`, add `                forward = limit if limit in ("limit_week", "limit_month") else ""`.
   - In the `except ai.AIBudgetError as exc:` branch, after the `reply_text, support = ...` line, add `                    forward = "budget_" + exc.reason`.
   - Directly above `        if len(items) == 1:` add:

```python
        if forward and _forward(request, uid, message, prior, page, forward):
            reply_text, support = _t(request, "havel.forwarded"), False
```

   Check: `grep -c 'forward' app/routes/havel.py` prints `9` or more.

3. **Copy.** In `App/app/host_i18n.py`, after the en line `        "havel.resting": "Havel is resting until tomorrow. You can still write to support here.",` insert `        "havel.forwarded": "I've passed your message to the UbyHost team. They usually reply within a few hours by e-mail.",`. After the cs `havel.resting` line insert `        "havel.forwarded": "Vaši zprávu jsem předal týmu UbyHostu. Obvykle odpoví e-mailem do několika hodin.",`. In `App/app/host_vi_i18n.py`, after the `    "havel.resting":` line insert `    "havel.forwarded": "Tôi đã chuyển tin nhắn của bạn cho đội ngũ UbyHost. Họ thường trả lời qua e-mail trong vòng vài giờ.",`. Check: `grep -c '"havel.forwarded"' app/host_i18n.py app/host_vi_i18n.py` prints `2` and `1`.

4. **Tests.** Create `App/tests/test_havel_limit_forward.py`:

```python
"""0333: a hit limit sends the host's message to support instead of the model."""
import re

import pytest

from app import ai, config, db, havel, rate_limit
from tests.ai_fake import FakeClient
from tests.test_submission_retry_cap import host  # noqa: F401


@pytest.fixture
def on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    db.execute("DELETE FROM rate_limit_event WHERE scope LIKE 'havel_%'")
    db.execute("DELETE FROM email_outbox WHERE kind = 'havel_support'")
    ai.set_client_for_tests(FakeClient([]))  # any model call fails the test
    yield
    ai.set_client_for_tests(None)


def _send(client, message="Where do I change my invoice details?"):
    csrf = re.search(r'name="_csrf" value="([^"]+)"', client.get("/havel").text).group(1)
    form = {"_csrf": csrf, "history": "", "history_sig": "", "page": "dashboard", "device": "phone",
            "topic": "", "message": message}
    return client.post("/havel", data=form).text


def _mails():
    return db.query("SELECT subject, payload FROM email_outbox WHERE kind = 'havel_support'")


@pytest.mark.parametrize("limit", ["limit_week", "limit_month"])
def test_week_and_month_limits_forward_the_message(host, on, monkeypatch, limit):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: limit)
    page = _send(host)
    assert "passed your message to the UbyHost team" in page
    rows = _mails()
    assert len(rows) == 1 and "Where do I change my invoice details?" in str(rows[0]["payload"])
    assert limit in str(rows[0]["payload"])


def test_budget_spent_forwards(host, on, monkeypatch):
    def spent(*args, **kwargs):
        raise ai.AIBudgetError("day")
    monkeypatch.setattr(havel, "ask", spent)
    assert "passed your message to the UbyHost team" in _send(host)
    assert "budget_day" in str(_mails()[0]["payload"])


def test_conversation_cap_forwards(host, on, monkeypatch):
    full = [{"host": f"question {n}", "havel": "answer"} for n in range(havel.MAX_EXCHANGES)]
    monkeypatch.setattr(havel, "read_history", lambda uid, history, sig: list(full))
    assert "passed your message to the UbyHost team" in _send(host)
    assert "question 5" in str(_mails()[0]["payload"])


@pytest.mark.parametrize("limit", ["limit_burst", "paused"])
def test_burst_and_pause_do_not_forward(host, on, monkeypatch, limit):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: limit)
    page = _send(host)
    assert "passed your message" not in page and not _mails()


def test_greeting_is_not_forwarded(host, on, monkeypatch):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    _send(host, "thanks")
    assert not _mails()


def test_support_cap_stops_forwarding(host, on, monkeypatch):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    uid = int(db.query_one("SELECT id FROM users WHERE username = ?", ("hostuser",))["id"])
    for _ in range(havel.SUPPORT_MAX):
        rate_limit.record("havel_support", str(uid))
    page = _send(host)
    assert "passed your message" not in page and "this week's messages" in page and not _mails()
```

   Before running, check the `host` fixture's username: `grep -n 'username' tests/test_submission_retry_cap.py | head -5`. If it is not `hostuser`, use the real one. If `local_reply("thanks")` returns None (`grep -n '_THANKS' app/havel.py`), use a word from that list. Check `db.query_one` exists (`grep -n 'def query_one' app/db.py`); if not, use `db.query(...)[0]`.

## 5. Do not touch

`App/app/havel.py`, `App/app/mail_notify.py`, the prompt, every other route. No new mail kind, no migration.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_havel_limit_forward.py tests/test_havel_support.py tests/test_havel_page.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q 2>&1 | tail -5`; from the repo root `python3 scripts/context_lint.py | tail -5`

Expected: all pass; `context lint: OK`.

## 7. Acceptance

- [ ] Week, month, conversation and budget limits send one `havel_support` mail with the host's message and the reason, and the host sees `havel.forwarded`; no model call.
- [ ] Burst, pause, greetings and switched-off Havel never forward.
- [ ] With 3 support sends this week, the host sees the normal limit text and no mail is queued.
- [ ] `havel.forwarded` exists in en, cs and vi.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: an anchor line in section 4 is missing, or `mail_notify.havel_support` has a different signature.

## 9. Report

`docs/tasks/0333-report.md` (400 tokens at most): files, each command's last 5 lines, section 7 ticked, Deviations, Questions. Set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/routes/havel.py` (only the four branches forward; `prior` holds the exchanges from before the conversation reset).

## Owner steps

None. The support mailbox gets these mails with subjects like any Havel support request; the summary line starts "Havel limit reached".
