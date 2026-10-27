"""0405: the host tries Leon at the end of the setup wizard (capped, nothing stored)."""
from __future__ import annotations

from app import ai, db, guide_facts, leon, rate_limit
from tests.test_0376_ai_gates import _csrf, ws  # noqa: F401 (fixture)
from tests.test_0404_leon_setup import _live

CARDS = [{
    "id": 7, "kind": "parking", "title": "Parking", "location": "", "steps": "Park in the yard.",
    "text": "Park in the yard.", "level": "booked", "state": "done", "visibility": "booked",
}]
ANSWER = {"kind": "answer", "reply": "Park in the yard.", "sources": ["c7"], "host_summary": None, "upset": False}
ASK = {"kind": "ask_host", "reply": "", "sources": [], "host_summary": "Asks about a late check-in", "upset": False}
STORED = ("guest_chat", "guest_chat_message", "guest_question")


def _setup(ws, monkeypatch, *answers):
    monkeypatch.setattr(leon, "switched_on", lambda apartment: True)
    monkeypatch.setattr(leon, "host_state", lambda apartment, live: "on")
    monkeypatch.setattr(guide_facts, "for_guest", lambda apartment_id, level, lang: CARDS)
    monkeypatch.setattr(leon, "system_blocks", lambda cards, name: ["guide"])
    _live(monkeypatch, True)
    calls = []

    def fake(feature, system_blocks, messages, schema, **kwargs):
        calls.append(messages)
        result = answers[min(len(calls), len(answers)) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(ai, "call", fake)
    return ws["home"], calls


def _stored():
    return {t: db.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in STORED}


def _try(client, apt_id, message, *, as_json=True):
    page = client.get("/apartments?lang=en").text
    headers = {"Accept": "application/json"} if as_json else {}
    return client.post(
        f"/apartments/{apt_id}/leon/setup/try", data={"_csrf": _csrf(page), "message": message},
        headers=headers, follow_redirects=False,
    )


def test_answer_is_shown_and_nothing_is_stored(ws, monkeypatch):
    home, calls = _setup(ws, monkeypatch, ANSWER)
    before = _stored()
    r = _try(ws["host"], home, "Where do I park?")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "answer" and "Park in the yard." in body["text"]
    assert body["blocked"] is False and body["note"] == ""
    assert set(body) == {"kind", "text", "would_ask", "blocked", "note", "cap"}
    assert _stored() == before
    assert len(calls) == 1


def test_a_question_for_the_host_is_flagged_and_not_sent(ws, monkeypatch):
    home, _ = _setup(ws, monkeypatch, ASK)
    before = _stored()
    body = _try(ws["host"], home, "Can I check in at midnight?").json()
    assert body["kind"] == "ask_host" and body["would_ask"] is True
    assert body["note"]
    assert _stored() == before


def test_small_talk_is_free(ws, monkeypatch):
    home, calls = _setup(ws, monkeypatch, ANSWER)
    body = _try(ws["host"], home, "hi").json()
    assert body["kind"] == "smalltalk" and body["blocked"] is False
    assert "left" not in body
    assert calls == []


def test_the_sixth_model_message_is_refused_without_a_call(ws, monkeypatch):
    home, calls = _setup(ws, monkeypatch, *[ANSWER] * 5)
    responses = [_try(ws["host"], home, "Where do I park?").json() for _ in range(leon.TRY_MAX)]
    assert [body["blocked"] for body in responses] == [False] * (leon.TRY_MAX - 1) + [True]
    assert all("left" not in body for body in responses)
    body = _try(ws["host"], home, "Where do I park?").json()
    assert body["kind"] == "cap" and body["text"] and body["blocked"] is True
    assert len(calls) == leon.TRY_MAX
    page = ws["host"].get(f"/apartments/{home}/leon/setup/try?lang=en").text
    assert "data-leon-try-cap" in page and " disabled" in page


def test_the_cap_is_per_property(ws, monkeypatch):
    home, _ = _setup(ws, monkeypatch, ANSWER)
    for _ in range(5):
        rate_limit.record("leon_try", str(home))
    assert leon.try_left(home) == 0
    assert leon.try_left(home + 1000) == 5


def test_model_error_passes_to_the_host_and_stores_nothing(ws, monkeypatch):
    home, _ = _setup(ws, monkeypatch, ai.AIError("timeout"))
    before = _stored()
    body = _try(ws["host"], home, "Where do I park?").json()
    assert body["kind"] == "passed" and body["would_ask"] is True and body["note"]
    assert _stored() == before


def test_without_javascript_the_page_shows_the_exchange(ws, monkeypatch):
    home, _ = _setup(ws, monkeypatch, ANSWER)
    r = _try(ws["host"], home, "Where do I park?", as_json=False)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Where do I park?" in r.text and "Park in the yard." in r.text
    assert "test messages a day" not in r.text
    assert "usage limits" in r.text


def test_try_is_404_when_leon_is_off_not_live_or_unknown(ws, monkeypatch):
    home, calls = _setup(ws, monkeypatch, ANSWER)
    monkeypatch.setattr(leon, "switched_on", lambda apartment: False)
    assert _try(ws["host"], home, "Where do I park?").status_code == 404
    monkeypatch.setattr(leon, "switched_on", lambda apartment: True)
    _live(monkeypatch, False)
    assert _try(ws["host"], home, "Where do I park?").status_code == 404
    assert _try(ws["host"], 999999, "Where do I park?").status_code == 404
    assert calls == []
