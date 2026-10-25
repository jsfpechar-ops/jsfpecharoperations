"""0376: Leon (AI) only where the host said yes, and the AI test list for production."""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import ai, auth, config, db, guest_guide, guide_token, guide_translate, mail
from app.main import app
from tests.ai_fake import FakeClient, reply
from tests.conftest import login_as

ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.", "sources": ["guide.stays.body"],
          "links": [], "action": None, "support_summary": None}


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "gates.sqlite3")
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon", "havel", "guide_translate"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset())
    db.init_db()
    owner = auth.create_account("Gate-Owner@example.test", "Gate owner", username="gate-owner", role="host")
    other = auth.create_account("gate-other@example.test", "Other owner", username="gate-other", role="host")
    now = db.utcnow()
    home = db.insert("apartment", {
        "owner_user_id": owner, "internal_name": "Gate flat", "active": 1, "created_at": now,
        "automation_mode": "manual",
    })
    foreign = db.insert("apartment", {
        "owner_user_id": other, "internal_name": "Other flat", "active": 1, "created_at": now,
        "automation_mode": "manual",
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (home,)))
    cards = {r["kind"]: r for r in guest_guide.items(home)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(home, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    assert guest_guide.progress(home)["live"]
    host = TestClient(app)
    assert login_as(host, "gate-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": home, "foreign": foreign, "host": host, "guest": TestClient(app), "token": guide_token.ensure(home)}
    ai.set_client_for_tests(None)


def _csrf(page: str) -> str:
    return re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


def _host_post(client, url, data):
    page = client.get("/apartments?lang=en").text
    return client.post(url, data={"_csrf": _csrf(page), **data}, follow_redirects=False)


def _leon_flag(apt_id):
    return db.query_one("SELECT leon_enabled FROM apartment WHERE id = ?", (apt_id,))["leon_enabled"]


def _guest_sees_leon(ws) -> bool:
    page = ws["guest"].get(f"/g/{ws['token']}?lang=en").text
    status = ws["guest"].get(f"/g/{ws['token']}/leon").status_code
    assert status in (200, 404)
    assert ("data-leon" in page) == (status == 200), "the card and the endpoints must agree"
    return status == 200


def test_leon_stays_off_until_the_host_says_yes(ws):
    assert _leon_flag(ws["home"]) == 0
    assert not _guest_sees_leon(ws)
    assert ws["guest"].post(f"/g/{ws['token']}/leon", data={"message": "Hi"}).status_code == 404
    db.execute("UPDATE apartment SET leon_enabled = 1 WHERE id = ?", (ws["home"],))
    assert _guest_sees_leon(ws)


def test_host_switches_leon_on_and_off_on_the_guide_page(ws):
    client, url = ws["host"], f"/apartments/{ws['home']}/guide"
    page = client.get(url + "?lang=en").text
    assert 'id="leon"' in page and "Let Leon answer my guests" in page and 'name="on"' in page
    assert 'checked' not in re.search(r'id="guide-leon-on"[^>]*>', page).group(0)
    assert _host_post(client, url + "/leon", {"on": "1"}).status_code == 303
    assert _leon_flag(ws["home"]) == 1
    assert 'checked' in re.search(r'id="guide-leon-on"[^>]*>', client.get(url).text).group(0)
    assert _host_post(client, url + "/leon", {}).status_code == 303
    assert _leon_flag(ws["home"]) == 0


def test_host_cannot_switch_leon_on_for_another_hosts_property(ws):
    response = _host_post(ws["host"], f"/apartments/{ws['foreign']}/guide/leon", {"on": "1"})
    assert response.status_code == 404
    assert _leon_flag(ws["foreign"]) == 0


def test_no_leon_section_while_leon_is_off(ws, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    assert 'id="leon"' not in ws["host"].get(f"/apartments/{ws['home']}/guide").text
    _host_post(ws["host"], f"/apartments/{ws['home']}/guide/leon", {"on": "1"})
    assert _leon_flag(ws["home"]) == 0


def test_test_list_keeps_other_owners_out(ws, monkeypatch):
    db.execute("UPDATE apartment SET leon_enabled = 1 WHERE id = ?", (ws["home"],))
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset({"josef@example.test"}))
    assert not _guest_sees_leon(ws)
    assert not guide_translate.can_fill(ws["home"])
    assert 'id="leon"' not in ws["host"].get(f"/apartments/{ws['home']}/guide").text
    db.execute("UPDATE apartment SET leon_enabled = 0 WHERE id = ?", (ws["home"],))
    _host_post(ws["host"], f"/apartments/{ws['home']}/guide/leon", {"on": "1"})
    assert _leon_flag(ws["home"]) == 0


def test_test_list_lets_a_listed_owner_in_whatever_the_case(ws, monkeypatch):
    db.execute("UPDATE apartment SET leon_enabled = 1 WHERE id = ?", (ws["home"],))
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset({"gate-owner@example.test"}))
    assert _guest_sees_leon(ws)
    assert guide_translate.can_fill(ws["home"])
    assert 'id="leon"' in ws["host"].get(f"/apartments/{ws['home']}/guide").text


def test_test_list_env_is_parsed_lower_case(monkeypatch):
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset(
        p.strip().lower() for p in " Josef@Example.test, ,b@x.test".split(",") if p.strip()))
    assert ai.on_test_list("josef@example.test") and ai.on_test_list(" JOSEF@example.TEST ")
    assert not ai.on_test_list("") and not ai.on_test_list(None) and not ai.on_test_list("c@x.test")


def _havel(client, message):
    page = client.get("/havel?lang=en").text
    form = {"_csrf": _csrf(page), "history": "", "history_sig": "", "page": "dashboard", "device": "phone",
            "topic": "", "message": message}
    return html.unescape(client.post("/havel?lang=en", data=form).text)


def test_havel_follows_the_test_list(ws, monkeypatch):
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
    fake = FakeClient([reply(ANSWER)])
    ai.set_client_for_tests(fake)
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset({"josef@example.test"}))
    assert "Chat is paused right now" in _havel(ws["host"], "How do I add a stay?")
    assert fake.calls == []
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset({"gate-owner@example.test"}))
    assert "Tap Add stay." in _havel(ws["host"], "How do I add a stay?")
    assert len(fake.calls) == 1
