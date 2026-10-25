"""0319: the support hand-off and the 80% budget mail."""
import html
import re

import pytest

from app import ai, config, db, havel, host_i18n, mail, mail_notify
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
    return html.unescape(re.search(r'name="_csrf" value="([^"]+)"', client.get("/havel?lang=en").text).group(1))


def _outbox(kind):
    return db.query("SELECT to_email, subject, payload FROM email_outbox WHERE kind = ?", (kind,))


def test_escalate_shows_the_card_prefilled_and_sending_queues_one_mail(host, on):
    ai.set_client_for_tests(FakeClient([reply(ESCALATE)]))
    form = {"_csrf": _csrf(host), "history": "", "history_sig": "", "page": "reports", "device": "phone",
            "topic": "", "message": "Error 4 on my report", "lang": "en"}
    raw = host.post("/havel?lang=en", data=form).text
    page = html.unescape(raw)
    assert 'action="/havel/support"' in page and "Host sees error 4 on a police report." in page
    assert "Your last four messages in this conversation and your account e-mail are sent too." in page
    assert 'ui-btn-compact" href="mailto:' not in page  # the nav has its own mailto; the Havel link is gone
    history = html.unescape(re.search(r'name="history" value="([^"]*)"', raw).group(1))
    sig = html.unescape(re.search(r'name="history_sig" value="([^"]*)"', raw).group(1))
    send = {"_csrf": form["_csrf"], "history": history, "history_sig": sig, "page": "reports",
            "summary": "Host sees error 4 on a police report.", "note": "Since Monday", "lang": "en"}
    done = html.unescape(host.post("/havel/support?lang=en", data=send).text)
    assert "Forwarded to the UbyHost team." in done
    host.post("/havel/support?lang=en", data=send)
    rows = _outbox("havel_support")
    assert len(rows) == 1 and rows[0]["to_email"] == mail.normalise_email(config.OPERATOR_EMAIL)
    body = str(rows[0]["payload"])
    assert "Since Monday" in body and "Error 4 on my report" in body and "reports" in body


def test_empty_request_is_not_sent_and_the_weekly_cap_holds(host, on):
    csrf = _csrf(host)
    empty = html.unescape(host.post("/havel/support?lang=en", data={"_csrf": csrf, "summary": " ", "note": ""}).text)
    assert "Write what you need help with" in empty and not _outbox("havel_support")
    for n in range(havel.SUPPORT_MAX):
        host.post("/havel/support?lang=en", data={"_csrf": csrf, "summary": f"Question {n}"})
    blocked = html.unescape(host.post("/havel/support?lang=en", data={"_csrf": csrf, "summary": "One more"}).text)
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


FAIL = {"kind": "fail", "reply": "", "sources": [], "links": [], "action": None, "support_summary": None}
ESCALATE_NO_SUMMARY = dict(ESCALATE, support_summary=None)
WRONG_ERROR_LABEL = "havel.q.wrong.error"


def _summary_box(page):
    """The text inside the support hand-off's summary textarea (unescaped)."""
    match = re.search(r'<textarea[^>]*name="summary"[^>]*>(.*?)</textarea>', html.unescape(page), re.S)
    assert match, "no summary textarea on the page"
    return html.unescape(match.group(1))


def _ask(client, message, **extra):
    form = {"_csrf": _csrf(client), "history": "", "history_sig": "", "page": "reports", "device": "phone",
            "topic": "", "message": message, "lang": "en", **extra}
    return html.unescape(client.post("/havel?lang=en", data=form).text)


def test_a_fail_reply_prefills_the_support_card_with_the_host_message(host, on):
    ai.set_client_for_tests(FakeClient([reply(FAIL)]))
    message = "Why does the export button vanish on Tuesdays"
    page = _ask(host, message)
    assert 'action="/havel/support"' in page
    assert _summary_box(page) == message


def test_ai_off_prefills_the_support_card_with_the_host_message(host, on, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    message = "How do I add a stay?"
    page = _ask(host, message)
    assert "Havel is unavailable right now" in page
    assert 'action="/havel/support"' in page
    assert _summary_box(page) == message


def test_escalate_without_a_summary_prefills_the_host_message(host, on):
    ai.set_client_for_tests(FakeClient([reply(ESCALATE_NO_SUMMARY)]))
    message = "Error 4 on my report"
    assert _summary_box(_ask(host, message)) == message


def test_escalate_with_a_summary_keeps_the_model_summary(host, on):
    ai.set_client_for_tests(FakeClient([reply(ESCALATE)]))
    assert _summary_box(_ask(host, "Error 4 on my report")) == ESCALATE["support_summary"]


def test_quick_help_support_card_prefills_the_question_label(host, on):
    # Only the "wrong / error" question sets support in havel_topics.TOPICS.
    page = html.unescape(host.get("/havel?lang=en&topic=wrong&q=error").text)
    assert 'action="/havel/support"' in page
    assert _summary_box(page) == host_i18n.translate("en", WRONG_ERROR_LABEL)


def test_the_composer_no_longer_shows_a_remaining_count(host, on):
    page = host.get("/havel?lang=en").text
    assert 'name="message"' in page
    assert "messages left" not in html.unescape(page)
