"""0301: the host side of Leon (AI): alert, one mail per batch, answer, dismiss, Add to guide."""
from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import ai, alerts, auth, claim, config, db, guest_guide, guest_handoff, leon, mail
from app.main import app
from tests.ai_fake import FakeClient, reply
from tests.conftest import login_as

QUESTION = "Where is the iron? My mail is anna@example.test"
SUMMARY = "Guest asks where the iron is."


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "handoff.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 10.0)
    monkeypatch.setattr(config, "ai_key_daily_usd", lambda feature: 0.0)
    db.init_db()
    owner = auth.create_account("handoff-owner@example.test", "Handoff owner", username="handoff-owner", role="host")
    other = auth.create_account("handoff-other@example.test", "Other owner", username="handoff-other", role="host")
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "Jana Nováková", "owner_user_id": owner, "created_at": now,
                                        "contact_email": "jana@example.test"})

    def home(name, user, **extra):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", **extra,
        })
    mine = home("Vinohrady flat", owner, legal_entity_id=entity)
    foreign = home("Other workspace", other)
    for apt in (mine, foreign):
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt,)))
    client = TestClient(app)
    assert login_as(client, "handoff-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "owner": owner, "client": client}
    ai.set_client_for_tests(None)


def _stay(apt_id):
    start = claim.prague_today()
    return db.insert("reservation", {
        "apartment_id": apt_id, "uid": f"handoff-{apt_id}", "source": "airbnb", "status": "active",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def _ask(apt_id, door="stay", text=QUESTION, summary=SUMMARY, urgent=False, triaged=True):
    """What leon.reply does for an ask_host verdict (0300): the row through ``_open_question``, which runs the hook."""
    if door == "stay":
        chat = leon.stay_chat(apt_id, _stay(apt_id), "en")
    else:
        chat = leon.qr_chat(apt_id, leon.new_cookie_id(), "en")
    message_id = leon._store(chat["id"], "guest", "", leon.redact(text))
    leon._store(chat["id"], "leon", "ask_host", "I have asked Jana.")
    qid = leon._open_question(chat["id"], apt_id, message_id, summary, urgent=urgent, triaged=triaged)
    return int(qid), chat


def _outbox():
    return db.query("SELECT kind, to_email, subject, payload FROM email_outbox WHERE kind = 'guest_question' ORDER BY id")


def _url(ws, qid=None):
    base = f"/apartments/{ws['home']}/guide/questions"
    return f"{base}/{qid}" if qid else base


# --- alert and mail --------------------------------------------------------------

def test_a_new_question_raises_one_needs_you_line_and_one_mail_per_batch(ws):
    qid1, _ = _ask(ws["home"])
    key = guest_handoff.dedupe_key(ws["home"])
    alert = alerts.open_alert(key)
    assert alert and alert["kind"] == "guest_question" and alert["apartment_id"] == ws["home"]
    assert len(_outbox()) == 1
    sent = _outbox()[0]
    assert sent["to_email"] == "jana@example.test" and "Vinohrady flat" in sent["subject"]
    assert f"/apartments/{ws['home']}/guide/questions" in sent["payload"]
    assert "iron" not in sent["payload"] and "iron" not in (alert["message"] + alert["detail"])
    qid2, _ = _ask(ws["home"], door="qr", text="Is there a hair dryer?", summary="Hair dryer?")
    assert len(_outbox()) == 1, "a second open question joins the batch, no second mail"
    assert db.query_one("SELECT COUNT(*) AS n FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,))["n"] == 1
    assert "2" in (alerts.open_alert(key)["message"])
    dashboard = ws["client"].get("/?lang=en").text
    assert "2 guest question(s) at Vinohrady flat" in dashboard
    assert f"/apartments/{ws['home']}/guide/questions" in dashboard
    # Clearing the batch resolves the line; the next question starts a new batch with a new mail.
    guest_handoff.answer(ws["home"], qid1, "In the wardrobe.")
    assert alerts.open_alert(key)
    guest_handoff.dismiss(ws["home"], qid2)
    assert alerts.open_alert(key) is None
    _ask(ws["home"], door="qr", text="Third?", summary="Third")
    assert len(_outbox()) == 2


def test_an_urgent_question_turns_the_line_red_and_mails_at_once(ws):
    _ask(ws["home"])
    assert len(_outbox()) == 1
    key = guest_handoff.dedupe_key(ws["home"])
    assert alerts.open_alert(key)["level"] == "warning"
    qid, _ = _ask(ws["home"], door="qr", text="Smoke in the kitchen", summary="Smoke in the kitchen.", urgent=True)
    assert len(_outbox()) == 2, "an emergency does not wait for the batch"
    alert = alerts.open_alert(key)
    assert alert["level"] == "critical" and "urgent" in alert["message"] and "Smoke" not in alert["message"]
    dashboard = ws["client"].get("/?lang=en").text
    assert "Urgent: a guest at Vinohrady flat may need help" in dashboard
    listing = ws["client"].get(_url(ws) + "?lang=en").text
    assert listing.index("Smoke in the kitchen") < listing.index("Where is the iron?"), "urgent rows first"
    assert "Urgent" in listing
    page = ws["client"].get(_url(ws, qid) + "?lang=en").text
    assert "read this as an emergency" in page
    guest_handoff.answer(ws["home"], qid, "I am on my way.")
    assert alerts.open_alert(key)["level"] == "warning", "back to amber once the urgent row is handled"


def test_an_unread_question_shows_the_guests_words_per_line(ws):
    words = "Where is the iron?\nAlso the hair dryer does not work."
    qid, _ = _ask(ws["home"], text="Where is the iron?", summary=words, triaged=False)
    listing = ws["client"].get(_url(ws) + "?lang=en").text
    assert "Not read by Leon (AI)" in listing
    page = ws["client"].get(_url(ws, qid) + "?lang=en").text
    assert "Not read by Leon (AI)" in page and "<p>Also the hair dryer does not work.</p>" in page
    assert "In short:" in page


def test_the_hook_fires_for_an_emergency_from_leon_reply(ws):
    cards = {r["kind"]: r for r in guest_guide.items(ws["home"])}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(ws["home"], cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    ai.set_client_for_tests(FakeClient([reply({"kind": "emergency", "reply": "", "sources": [],
                                               "host_summary": "Someone smells gas."})]))
    chat = leon.stay_chat(ws["home"], _stay(ws["home"]), "en")
    got = leon.reply(chat, "I smell gas in the flat", level="booked", property_name="Vinohrady flat",
                     host_name="Jana", address_key="t")
    assert got["kind"] == "emergency" and got["question_id"]
    row = db.query_one("SELECT urgent, triaged FROM guest_question WHERE id = ?", (got["question_id"],))
    assert row["urgent"] == 1 and row["triaged"] == 1
    assert alerts.open_alert(guest_handoff.dedupe_key(ws["home"]))["level"] == "critical"
    assert len(_outbox()) == 1


def test_the_hook_fires_from_leon_reply(ws):
    cards = {r["kind"]: r for r in guest_guide.items(ws["home"])}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(ws["home"], cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    ai.set_client_for_tests(FakeClient([reply({"kind": "ask_host", "reply": "", "sources": [], "host_summary": SUMMARY})]))
    chat = leon.stay_chat(ws["home"], _stay(ws["home"]), "en")
    got = leon.reply(chat, "Where is the iron?", level="booked", property_name="Vinohrady flat", host_name="Jana",
                     address_key="t")
    assert got["kind"] == "ask_host" and got["question_id"]
    assert alerts.open_alert(guest_handoff.dedupe_key(ws["home"]))
    assert len(_outbox()) == 1


def test_no_host_address_means_alert_only_and_no_text_in_logs(ws, caplog):
    db.execute("UPDATE legal_entity SET contact_email = NULL")
    with caplog.at_level(logging.INFO):
        qid, _ = _ask(ws["home"])
        guest_handoff.answer(ws["home"], qid, "In the wardrobe, top shelf.")
    assert alerts.open_alert(guest_handoff.dedupe_key(ws["home"])) is None
    assert _outbox() == []
    assert "iron" not in caplog.text and "wardrobe" not in caplog.text and "anna@" not in caplog.text


# --- ownership -------------------------------------------------------------------

def test_another_hosts_questions_are_not_found(ws):
    qid, _ = _ask(ws["foreign"])
    client = ws["client"]
    assert client.get(f"/apartments/{ws['foreign']}/guide/questions").status_code == 404
    assert client.get(f"/apartments/{ws['foreign']}/guide/questions/{qid}").status_code == 404
    assert client.post(f"/apartments/{ws['foreign']}/guide/questions/{qid}", data={"answer": "x"}).status_code == 404
    # A real question id under the host's own property path is still another property's row.
    assert client.get(_url(ws, qid)).status_code == 404
    assert client.post(_url(ws, qid), data={"answer": "x"}).status_code == 404
    assert client.post(_url(ws, qid) + "/card", data={"topic": "rules"}).status_code == 404
    assert db.query_one("SELECT status FROM guest_question WHERE id = ?", (qid,))["status"] == "open"


# --- the pages -------------------------------------------------------------------

def test_the_list_shows_the_redacted_question_and_the_guide_page_links_it(ws):
    _ask(ws["home"])
    page = ws["client"].get(_url(ws) + "?lang=en").text
    assert "Where is the iron?" in page and "[email]" in page and "anna@" not in page
    assert "Waiting" in page and "1 waiting for your answer" in page
    guide = ws["client"].get(f"/apartments/{ws['home']}/guide?lang=en").text
    assert "Guest questions (1)" in guide and _url(ws) in guide


def test_an_empty_list_has_an_empty_state(ws):
    page = ws["client"].get(_url(ws) + "?lang=cs").text
    assert "Zatím žádné dotazy" in page and "data-empty-state" in page


def test_the_host_answer_reaches_the_guest_conversation_as_written(ws):
    qid, chat = _ask(ws["home"])
    answer = "It's in the wardrobe, top shelf.\nThe board is behind the door."
    response = ws["client"].post(_url(ws, qid), data={"answer": answer}, follow_redirects=False)
    assert response.status_code == 303 and _url(ws, qid) in response.headers["location"]
    turns = leon.messages(chat["id"])
    assert turns[-1]["role"] == "host" and turns[-1]["text"] == answer
    row = db.query_one("SELECT status, answer, answered_at FROM guest_question WHERE id = ?", (qid,))
    assert row["status"] == "answered" and row["answer"] == answer and row["answered_at"]
    # The stay door's GET (0300) returns the host turn for the page.
    page = ws["client"].get(_url(ws, qid) + "?lang=en").text
    assert "top shelf." in page and "Add to guide" in page and "Send to guest" not in page


def test_the_answer_is_capped_plain_text_and_escaped(ws):
    qid, _ = _ask(ws["home"])
    client = ws["client"]
    assert client.post(_url(ws, qid), data={"answer": "   "}).status_code == 422
    assert client.post(_url(ws, qid), data={"answer": "x" * 1001}).status_code == 422
    assert db.query_one("SELECT status FROM guest_question WHERE id = ?", (qid,))["status"] == "open"
    html = '<b onclick="x()">bold</b> & <script>alert(1)</script>'
    assert client.post(_url(ws, qid), data={"answer": html}, follow_redirects=False).status_code == 303
    page = client.get(_url(ws, qid)).text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    stored = db.query_one("SELECT text FROM guest_chat_message WHERE role = 'host'")["text"]
    assert stored == html, "stored as typed; escaping happens where it is rendered"


def test_dismiss_closes_the_question_without_a_guest_message(ws):
    qid, chat = _ask(ws["home"])
    response = ws["client"].post(_url(ws, qid) + "/dismiss", follow_redirects=False)
    assert response.status_code == 303
    assert db.query_one("SELECT status FROM guest_question WHERE id = ?", (qid,))["status"] == "dismissed"
    assert all(m["role"] != "host" for m in leon.messages(chat["id"]))
    assert alerts.open_alert(guest_handoff.dedupe_key(ws["home"])) is None


# --- Add to guide ----------------------------------------------------------------

def test_add_to_guide_makes_a_host_saved_card_the_host_can_edit(ws):
    qid, _ = _ask(ws["home"], door="qr")
    client = ws["client"]
    assert client.post(_url(ws, qid) + "/card", data={"topic": "rooms"}).status_code == 422, "answer first"
    client.post(_url(ws, qid), data={"answer": "In the wardrobe, top shelf."})
    response = client.post(_url(ws, qid) + "/card", data={"topic": "rooms"}, follow_redirects=False)
    assert response.status_code == 303
    item_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    card = guest_guide.get(ws["home"], item_id)
    assert card["kind"] == "custom" and card["topic"] == "rooms" and card["title"] == SUMMARY
    assert card["steps"] == "In the wardrobe, top shelf." and card["state"] == "done" and card["source"] == "host"
    assert card["visibility"] == "everyone", "a QR question becomes an everyone card"
    # A second tap opens the same card instead of making a twin.
    again = client.post(_url(ws, qid) + "/card", data={"topic": "kitchen"}, follow_redirects=False)
    assert again.headers["location"].split("?")[0].endswith(f"/{item_id}")
    assert db.query_one("SELECT COUNT(*) AS n FROM guide_item WHERE kind = 'custom' AND apartment_id = ?", (ws["home"],))["n"] == 1
    page = client.get(_url(ws, qid) + "?lang=en").text
    assert "This answer is in your guide." in page and f"/guide/{item_id}" in page
    assert client.get(f"/apartments/{ws['home']}/guide/{item_id}").status_code == 200


def test_a_stay_question_becomes_a_booked_card_and_a_bad_topic_is_refused(ws):
    qid, _ = _ask(ws["home"], door="stay", summary="")
    client = ws["client"]
    client.post(_url(ws, qid), data={"answer": "Behind the door."})
    assert client.post(_url(ws, qid) + "/card", data={"topic": "nope"}).status_code == 422
    response = client.post(_url(ws, qid) + "/card", data={"topic": "rooms"}, follow_redirects=False)
    item_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    card = guest_guide.get(ws["home"], item_id)
    assert card["visibility"] == "booked" and card["title"] == "Where is the iron? My mail is [email]"
