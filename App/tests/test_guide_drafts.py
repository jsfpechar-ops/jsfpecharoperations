"""0349: reviewing drafted cards on the card editor."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, guest_guide
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "drafts.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("draft-owner@example.test", "Draft owner", username="draft-owner", role="host")
    other = auth.create_account("draft-other@example.test", "Other owner", username="draft-other", role="host")
    now = db.utcnow()

    def home(name, user):
        apt_id = db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        return apt_id
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "draft-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def _draft(apt_id, kind="wifi", source="airbnb"):
    item = {r["kind"]: r for r in guest_guide.items(apt_id)}[kind]
    db.execute(
        "UPDATE guide_item SET steps = 'Network Vivus, password on the router', state = 'check', source = ? "
        "WHERE id = ?", (source, item["id"]),
    )
    return item["id"]


def test_draft_shows_where_it_came_from_and_can_be_discarded(ws):
    item_id = _draft(ws["home"])
    client = ws["client"]
    page = client.get(f"/apartments/{ws['home']}/guide/{item_id}").text
    assert "From your Airbnb listing." in page and "Discard this draft" in page
    response = client.post(f"/apartments/{ws['home']}/guide/{item_id}/discard", follow_redirects=False)
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    item = guest_guide.get(ws["home"], item_id)
    assert (item["state"], item["steps"], item["source"]) == ("missing", "", "host")


def test_saving_a_draft_confirms_it(ws):
    item_id = _draft(ws["home"], source="booking")
    ws["client"].post(
        f"/apartments/{ws['home']}/guide/{item_id}",
        data={"steps": "Network Vivus, password on the router", "visibility": "booked"},
    )
    item = guest_guide.get(ws["home"], item_id)
    assert (item["state"], item["source"]) == ("done", "host")


def test_only_drafts_can_be_discarded(ws):
    client = ws["client"]
    wifi = {r["kind"]: r for r in guest_guide.items(ws["home"])}["wifi"]
    guest_guide.save(ws["home"], wifi["id"], {"steps": "Host wrote this"})
    assert client.post(f"/apartments/{ws['home']}/guide/{wifi['id']}/discard").status_code == 404
    assert guest_guide.get(ws["home"], wifi["id"])["steps"] == "Host wrote this"
    assert "Discard this draft" not in client.get(f"/apartments/{ws['home']}/guide/{wifi['id']}").text


def test_another_hosts_draft_is_out_of_reach(ws):
    theirs = _draft(ws["foreign"])
    client = ws["client"]
    assert client.post(f"/apartments/{ws['foreign']}/guide/{theirs}/discard").status_code == 404
    assert client.post(f"/apartments/{ws['home']}/guide/{theirs}/discard").status_code == 404
    assert guest_guide.get(ws["foreign"], theirs)["state"] == "check"


def test_czech_draft_line(ws):
    item_id = _draft(ws["home"], source="legacy")
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{item_id}?lang=cs").text
    assert "Z vašich starších poznámek k příjezdu v UbyHost." in page and "Zahodit tento návrh" in page
