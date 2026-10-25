"""0312: the Havel page works as a plain form, applies the limits and shows only checked text."""
from __future__ import annotations

import re

import pytest

from app import ai, config, db, havel
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import host as host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.\n2. Pick the dates.", "sources": ["guide.stays.body"],
          "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None}


def _csrf(page: str) -> str:
    return re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


def _post(client, data, headers=None):
    page = client.get("/havel").text
    form = {"_csrf": _csrf(page), "history": "", "history_sig": "", "page": "dashboard", "device": "phone", "topic": ""}
    form.update(data)
    return client.post("/havel", data=form, headers=headers or {})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    yield
    ai.set_client_for_tests(None)


def test_page_renders_in_every_language_with_the_ai_label(host):
    for lang in ("en", "cs", "vi"):
        page = host.get(f"/havel?lang={lang}").text
        assert "Havel (AI)" in page and "havel." not in page.replace("/havel", ""), lang
        assert 'data-havel-thread' in page and 'name="message"' in page and 'name="history_sig"' in page


def test_greeting_is_answered_locally_and_not_counted(host):
    fake = FakeClient([])
    ai.set_client_for_tests(fake)
    page = _post(host, {"message": "Hello"}).text
    assert "Ask me how something works" in page and fake.calls == []
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'havel_week'", ())["n"] == 0


def test_answer_renders_steps_links_and_signed_history(host):
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "<ol><li>Tap Add stay.</li><li>Pick the dates.</li></ol>" in page
    assert 'href="/reservations?new=1"' in page
    history = re.search(r'name="history" value="([^"]*)"', page).group(1)
    sig = re.search(r'name="history_sig" value="([^"]*)"', page).group(1)
    assert "How do I add a stay?" in history.replace("&#34;", '"').replace("&quot;", '"') and len(sig) == 64
    assert "messages left this week" in page or "messages left this month" in page


def test_fragment_header_returns_only_the_thread(host):
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    res = _post(host, {"message": "How do I add a stay?"}, headers={"X-Havel": "1"})
    assert res.status_code == 200
    assert "<html" not in res.text and "data-havel-state" in res.text and "havel-msg-host" in res.text


def test_off_limit_and_failure_show_the_fixed_sentences(host, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "Havel is unavailable right now" in page
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    ai.set_client_for_tests(FakeClient([reply(text="{broken")]))
    page = _post(host, {"message": "How do I add a stay?"}).text
    assert "I don't know that, and I don't want to guess" in page
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_week")
    page = _post(host, {"message": "Again?"}).text
    assert "They come back on Monday" in page and 'name="message"' not in page


def test_too_long_is_refused_without_a_call(host):
    fake = FakeClient([])
    ai.set_client_for_tests(fake)
    page = _post(host, {"message": "x" * 601}).text
    assert "under 600 characters" in page and fake.calls == []
