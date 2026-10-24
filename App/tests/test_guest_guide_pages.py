"""0342: the host's guest guide pages."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, guest_guide
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "guide.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("guide-owner@example.test", "Guide owner", username="guide-owner", role="host")
    other = auth.create_account("guide-other@example.test", "Other owner", username="guide-other", role="host")
    now = db.utcnow()

    def home(name, user, **extra):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", **extra,
        })
    mine = home("Vivus / 3", owner, checkout_info="Leave the keys on the table.")
    foreign = home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "guide-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def _cards(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def test_guide_page_lists_default_cards_in_topics(ws):
    response = ws["client"].get(f"/apartments/{ws['home']}/guide")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.text
    for text in ("Guest guide", "Heating and hot water", "Hot water", "Must-have", "Check this"):
        assert text in body
    assert "Guests cannot see the guide yet" in body
    assert "guest_guide." not in body  # every key has copy
    assert len(_cards(ws["home"])) == len(guest_guide.DEFAULT_KINDS)


def test_foreign_property_is_not_found(ws):
    client = ws["client"]
    assert client.get(f"/apartments/{ws['foreign']}/guide").status_code == 404
    response = client.post(f"/apartments/{ws['foreign']}/guide/cards", data={"topic": "kitchen", "title": "Hob"})
    assert response.status_code == 404
    assert guest_guide.items(ws["foreign"]) == []


def test_card_from_another_property_is_not_found(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (ws["foreign"],)))
    foreign_wifi = _cards(ws["foreign"])["wifi"]["id"]
    assert client.get(f"/apartments/{ws['home']}/guide/{foreign_wifi}").status_code == 404
    response = client.post(f"/apartments/{ws['home']}/guide/{foreign_wifi}", data={"steps": "x"})
    assert response.status_code == 404
    assert _cards(ws["foreign"])["wifi"]["steps"] == ""


def test_save_and_next_walks_to_the_next_open_card(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    cards = _cards(ws["home"])
    response = client.post(
        f"/apartments/{ws['home']}/guide/{cards['checkin']['id']}",
        data={"location": "Main door, 2nd floor", "steps": "Ring 3\nTake the lift", "watch_out": "",
              "video_url": "", "visibility": "everyone", "then": "next"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide/{cards['keys']['id']}")
    assert _cards(ws["home"])["checkin"]["state"] == "done"


def test_plain_save_returns_to_the_list(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    wifi = _cards(ws["home"])["wifi"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/{wifi['id']}",
        data={"steps": "Network Vivus", "visibility": "booked"}, follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide?msg=")
    assert _cards(ws["home"])["wifi"]["visibility"] == "booked"


def test_bad_input_re_renders_with_the_error(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    wifi = _cards(ws["home"])["wifi"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/{wifi['id']}",
        data={"steps": "Network Vivus", "video_url": "http://example.test/v", "visibility": "everyone"},
    )
    assert response.status_code == 422
    assert "must start with https://" in response.text
    assert "Network Vivus" in response.text  # the host's text is kept
    assert _cards(ws["home"])["wifi"]["state"] == "missing"


def test_old_checkout_text_shows_as_a_draft(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    checkout = _cards(ws["home"])["checkout"]
    page = client.get(f"/apartments/{ws['home']}/guide/{checkout['id']}").text
    assert "This card was filled in for you" in page
    assert "Leave the keys on the table." in page


def test_skip_and_bring_back(ws):
    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")
    trash = _cards(ws["home"])["trash"]
    client.post(f"/apartments/{ws['home']}/guide/{trash['id']}/skip", data={"skip": "1"})
    assert _cards(ws["home"])["trash"]["state"] == "skipped"
    client.post(f"/apartments/{ws['home']}/guide/{trash['id']}/skip", data={"skip": "0"})
    assert _cards(ws["home"])["trash"]["state"] == "missing"


def test_custom_card_add_and_delete(ws):
    client = ws["client"]
    response = client.post(
        f"/apartments/{ws['home']}/guide/cards", data={"topic": "kitchen", "title": "Induction hob"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    custom = [r for r in guest_guide.items(ws["home"]) if r["kind"] == "custom"]
    assert len(custom) == 1 and custom[0]["title"] == "Induction hob"
    assert response.headers["location"].startswith(f"/apartments/{ws['home']}/guide/{custom[0]['id']}")
    assert "Delete card" in client.get(f"/apartments/{ws['home']}/guide/{custom[0]['id']}").text
    client.post(f"/apartments/{ws['home']}/guide/{custom[0]['id']}/delete")
    assert [r for r in guest_guide.items(ws["home"]) if r["kind"] == "custom"] == []
    wifi = _cards(ws["home"])["wifi"]
    assert client.post(f"/apartments/{ws['home']}/guide/{wifi['id']}/delete").status_code == 404


def test_czech_page(ws):
    client = ws["client"]
    client.cookies.set("ubyhost_lang", "cs")
    body = client.get(f"/apartments/{ws['home']}/guide?lang=cs").text
    assert "Průvodce pro hosty" in body
    assert "Topení a teplá voda" in body


def test_property_page_links_to_the_guide(ws):
    body = ws["client"].get(f"/apartments/{ws['home']}").text
    assert f'href="/apartments/{ws["home"]}/guide"' in body
