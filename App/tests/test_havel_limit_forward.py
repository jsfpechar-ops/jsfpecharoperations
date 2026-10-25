"""0333: a hit limit sends the host's message to support instead of the model."""
import html
import re

import pytest

from app import ai, config, db, havel, rate_limit
from tests.ai_fake import FakeClient
from tests.test_submission_retry_cap import USERNAME, host  # noqa: F401

FORWARDED = "to the UbyHost team. They usually reply"


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
    csrf = html.unescape(re.search(r'name="_csrf" value="([^"]+)"', client.get("/havel?lang=en").text).group(1))
    form = {"_csrf": csrf, "history": "", "history_sig": "", "page": "dashboard", "device": "phone",
            "topic": "", "message": message, "lang": "en"}
    return html.unescape(client.post("/havel?lang=en", data=form).text)


def _mails():
    return db.query("SELECT subject, payload FROM email_outbox WHERE kind = 'havel_support'")


@pytest.mark.parametrize("limit", ["limit_week", "limit_month"])
def test_week_and_month_limits_forward_the_message(host, on, monkeypatch, limit):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: limit)
    page = _send(host)
    assert FORWARDED in page
    rows = _mails()
    assert len(rows) == 1 and "Where do I change my invoice details?" in str(rows[0]["payload"])
    assert limit in str(rows[0]["payload"])


def test_budget_spent_forwards(host, on, monkeypatch):
    def spent(*args, **kwargs):
        raise ai.AIBudgetError("day")
    monkeypatch.setattr(havel, "ask", spent)
    assert FORWARDED in _send(host)
    assert "budget_day" in str(_mails()[0]["payload"])


def test_conversation_cap_forwards(host, on, monkeypatch):
    full = [{"host": f"question {n}", "havel": "answer"} for n in range(havel.MAX_EXCHANGES)]
    monkeypatch.setattr(havel, "read_history", lambda uid, history, sig: list(full))
    assert FORWARDED in _send(host)
    assert "question 5" in str(_mails()[0]["payload"])


@pytest.mark.parametrize("limit", ["limit_burst", "paused"])
def test_burst_and_pause_do_not_forward(host, on, monkeypatch, limit):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: limit)
    page = _send(host)
    assert FORWARDED not in page and not _mails()


def test_greeting_is_not_forwarded(host, on, monkeypatch):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    _send(host, "thanks")
    assert not _mails()


def test_support_cap_stops_forwarding(host, on, monkeypatch):
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    uid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"])
    for _ in range(havel.SUPPORT_MAX):
        rate_limit.record("havel_support", str(uid))
    page = _send(host)
    assert FORWARDED not in page and "this week's messages" in page and not _mails()
