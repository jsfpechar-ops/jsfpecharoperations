"""0352: the Leon (AI) chat on both guide doors, rendered server side (the browser test is test_guest_leon_browser.py)."""
from __future__ import annotations

import pathlib
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, guest_guide, guide_token, i18n, mail
from app.main import app

TOKEN = "leonchattok0352"
ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"
JS = ROOT / "static" / "guest-leon.js"
KEYS = ("leon_ask", "leon_intro", "leon_label", "leon_placeholder", "leon_send", "leon_sending", "leon_you",
        "leon_needs_js", "leon_waiting", "leon_error", "leon_error_reload", "guide_qr_contact")


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "chat.sqlite3")
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    db.init_db()
    owner = auth.create_account("chat-owner@example.test", "Chat owner", username="chat-owner", role="host")
    now = db.utcnow()
    entity = db.insert("legal_entity", {
        "name": "Jana Fiktivni", "owner_user_id": owner, "contact_email": "jana@example.test",
        "contact_phone": "+420 600 000 000", "created_at": now,
    })
    home = db.insert("apartment", {
        "owner_user_id": owner, "legal_entity_id": entity, "internal_name": "Chat flat", "active": 1,
        "created_at": now, "automation_mode": "manual", "permalink_token": TOKEN, "permalink_window_days": 14,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (home,)))
    yield {"home": home, "client": TestClient(app)}


def _go_live(apt_id):
    cards = {r["kind"]: r for r in guest_guide.items(apt_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apt_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    assert guest_guide.progress(apt_id)["live"]


def _stay(apt_id):
    start = claim.prague_today()
    return db.insert("reservation", {
        "apartment_id": apt_id, "uid": "chat-0302", "source": "airbnb", "status": "active",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def _qr_page(ws, lang="en"):
    token = guide_token.ensure(ws["home"])
    return token, ws["client"].get(f"/g/{token}?lang={lang}")


def test_the_qr_page_has_the_chat_and_its_script(ws):
    _go_live(ws["home"])
    token, page = _qr_page(ws)
    body = page.text
    assert page.status_code == 200
    assert f'data-leon-url="/g/{token}/leon"' in body
    assert 'action="/g/' + token + '/leon"' in body
    assert re.search(r'<form class="g-leon-form"[^>]*\shidden>', body), "the form must be hidden until the script runs"
    assert "<noscript>" in body and "turn on JavaScript" in body
    assert '/static/guest-leon.js?v=' in body
    assert 'maxlength="500"' in body
    assert 'data-label-host="Jana, your host, answered:"' in body
    assert "Leon (AI)" in body


def test_the_stay_door_has_the_chat_on_its_own_url(ws):
    _go_live(ws["home"])
    rid = _stay(ws["home"])
    body = ws["client"].get(f"/l/{TOKEN}/{rid}/guide?lang=cs").text
    assert f'data-leon-url="/l/{TOKEN}/{rid}/guide/leon"' in body
    assert "Zeptejte se Leona (AI)" in body
    assert 'data-label-host="Jana, váš hostitel, odpovídá:"' in body


def test_no_chat_while_leon_is_off_or_the_guide_is_not_live(ws, monkeypatch):
    token, page = _qr_page(ws)
    assert "data-guide-not-ready" in page.text and "data-leon" not in page.text
    _go_live(ws["home"])
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    _, page = _qr_page(ws)
    assert "data-guide-card" in page.text
    assert "data-leon" not in page.text and "guest-leon.js" not in page.text


def test_the_qr_contact_block_points_to_the_booking_messages(ws):
    _go_live(ws["home"])
    for lang in i18n.LANGUAGES:
        body = _qr_page(ws, lang)[1].text
        assert "data-qr-contact" in body, lang
        assert i18n.translator(lang)("host_details_missing") not in body, lang
        assert "jana@example.test" not in body and "600 000 000" not in body
    rid = _stay(ws["home"])
    stay = ws["client"].get(f"/l/{TOKEN}/{rid}/guide?lang=en").text
    assert "data-qr-contact" not in stay and "jana@example.test" in stay


def test_every_chat_key_is_filled_in_every_guest_language():
    for lang in i18n.LANGUAGES:
        t = i18n.translator(lang)
        for key in KEYS:
            assert t(key) and t(key) != key, (lang, key)
    assert i18n.translator("de")("leon_send") != i18n.translator("en")("leon_send")


def test_the_script_is_safe_and_local():
    js = JS.read_text(encoding="utf-8")
    assert "innerHTML" not in js and "eval(" not in js
    assert "localStorage" not in js and "document.cookie" not in js
    assert "http://" not in js and "https://" not in js
    template = (ROOT / "templates" / "guest" / "_leon.html").read_text(encoding="utf-8")
    assert "<script" not in template
