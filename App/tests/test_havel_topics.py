"""0313: quick-help topics and the panel."""
from __future__ import annotations

import html
import re

import pytest

from app import ai, config, db, havel, havel_topics, host_i18n
from tests.ai_fake import FakeClient, reply
from tests.test_submission_retry_cap import host as host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.", "sources": ["guide.stays.body"],
          "links": [], "action": None, "support_summary": None}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    db.init_db()
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    yield
    ai.set_client_for_tests(None)


def test_every_topic_key_resolves_in_both_languages():
    for lang in ("en", "cs"):
        for topic in havel_topics.TOPICS:
            assert host_i18n.translate(lang, topic["label"]) not in ("", topic["label"])
            for q in topic["questions"]:
                answer = havel_topics.answer(lang, topic["id"], q["id"])
                expected = 1 if q.get("short") else len(q["keys"])
                assert len(answer["paragraphs"]) == expected, (lang, topic["id"], q["id"])
                for p in answer["paragraphs"]:
                    assert "%(" not in p and "<" not in p and not p.startswith(("guide.", "havel."))


def test_page_aware_order_and_read_keys():
    assert havel_topics.ordered("apartments")[0]["id"] == "guest_link"
    assert havel_topics.ordered("dashboard")[0]["id"] == "reporting"
    assert [t["id"] for t in havel_topics.ordered("")] == havel_topics.TOPIC_IDS
    assert havel_topics.read_keys("reporting", "when")[0] == "guide.reporting.body"
    assert havel_topics.read_keys("wrong", "error") == []
    assert havel_topics.answer("en", "nope", "x") is None


def test_topics_render_on_the_page_and_as_fragments(host):
    page = html.unescape(host.get("/havel?lang=en").text)
    assert page.count('data-havel-topic-link') == 6  # 0391: five topics + "Other topic"
    questions = html.unescape(host.get("/havel?topic=guest_link&lang=en").text)
    assert 'href="/havel?topic=guest_link&q=how"' in questions
    answer = html.unescape(host.get("/havel?topic=guest_link&q=where&lang=en", headers={"X-Havel": "1"}).text)
    assert "<html" not in answer and 'data-mode="replace"' in answer
    assert 'href="/havel?topic=guest_link&q=where&ask=1" data-havel-topic-link data-havel-ask-open' in answer
    assert host_i18n.translate("en", "havel.short.guest_link.where")[:20] in answer or \
        host_i18n.translate("cs", "havel.short.guest_link.where")[:20] in answer
    support = html.unescape(host.get("/havel?topic=wrong&q=error&lang=en").text)
    assert 'action="/havel/support"' in support
    assert host.get("/havel?topic=evil&q=../x&lang=en").status_code == 200


def test_hand_off_sends_topic_and_read_keys_to_the_engine(host, monkeypatch):
    seen = {}
    real = havel.ask

    def spy(h, history, message, today=None):
        seen["host"] = h
        return real(h, history, message, today)

    monkeypatch.setattr(havel, "ask", spy)
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    page = html.unescape(host.get("/havel?lang=en").text)
    csrf = re.search(r'name="_csrf" value="([^"]+)"', page).group(1)
    res = host.post("/havel", data={"_csrf": csrf, "message": "And a cancelled one?", "history": "", "history_sig": "",
                                    "page": "reservations", "device": "phone", "topic": "stays", "q": "cancelled"},
                    headers={"X-Havel": "1"})
    assert res.status_code == 200
    assert seen["host"].topic == "stays" and seen["host"].page == "stays"
    assert seen["host"].read_keys == ["guide.stays.cancelled", "guide.stays.dates_changed"]
    assert 'data-mode="append"' in res.text and "havel-msg-havel" in res.text


def test_short_answers_are_short_and_read_keys_stay_guide_keys():
    for lang in ("en", "cs", "vi"):
        for topic in havel_topics.TOPICS:
            for q in topic["questions"]:
                if not q.get("short"):
                    continue
                text = host_i18n.translate(lang, q["short"])
                assert text and text not in ("?", q["short"]), (lang, q["short"])
                assert len(text) <= 220, (lang, q["short"])
    assert havel_topics.read_keys("stays", "cancelled") == ["guide.stays.cancelled", "guide.stays.dates_changed"]
    assert havel_topics.read_keys("guest_link", "where")[0] == "guide.guest_links.find1"
