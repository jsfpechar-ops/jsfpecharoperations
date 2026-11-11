"""1099: one short property editor, first setup included (server side, no JavaScript)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, property_setup, reporting
from app.main import app
from app.ubyport.client import UbyportAuthError, UbyportTransportError
from tests.conftest import login_as, mark_security_prompt_seen
from tests.test_police_letter_flow import _FakeClient

USERNAME = "short-editor-1099"
PASSWORD_TYPED = "Typed-Secret-1099"
OPENER = re.compile(r'<details class="prop-sec" id="(sec-[a-z]+)"( open)?>')
SECTIONS = {"sec-basics", "sec-messages", "sec-police", "sec-fee", "sec-calendars", "sec-lock"}


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (row["id"],)):
            db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apt['id']}",))
            db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _operator_id() -> str:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    row = db.query_one("SELECT id FROM legal_entity WHERE owner_user_id = ? LIMIT 1", (owner["id"],))
    if row:
        return str(row["id"])
    return str(db.insert("legal_entity", {"name": "Short Operator", "owner_user_id": owner["id"], "created_at": db.utcnow()}))


def _basics(**extra):
    data = {
        "internal_name": "Short Flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_street": "Synthetic",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "legal_entity_id": _operator_id(),
    }
    data.update(extra)
    return data


def _police(**extra):
    data = _basics(
        uby_idub="123456789012",
        uby_mark="AAKLI",
        uby_name="Penzion Short",
        uby_contact="host@short.test",
        uby_ws_user="UBY-WS123abc",
        uby_ws_password=PASSWORD_TYPED,
    )
    data.update(extra)
    return data


@pytest.fixture
def fake(monkeypatch):
    state = {"error": None, "made": []}

    def client_for(apartment, env=None):
        client = _FakeClient(state["error"])
        state["made"].append(client)
        return client

    monkeypatch.setattr(reporting, "client_for", client_for)
    return state


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    mark_security_prompt_seen(auth.create_account(f"{USERNAME}@example.test", "Short Host", username=USERNAME))
    client = TestClient(app)
    assert login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False).status_code == 303
    created = client.post("/apartments", data=_basics(), follow_redirects=False)
    assert created.status_code == 303, created.text
    client.created_location = created.headers["location"]
    try:
        yield client
    finally:
        _cleanup()


def _apt():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return db.query_one("SELECT * FROM apartment WHERE owner_user_id = ? ORDER BY id LIMIT 1", (owner["id"],))


def _page(client, query="?view=settings"):
    response = client.get(f"/apartments/{_apt()['id']}{query}")
    assert response.status_code == 200
    return response.text


def _open(text):
    found = dict(OPENER.findall(text))
    assert set(found) == SECTIONS, found
    return {key for key, flag in found.items() if flag}


def _summary(text, sec):
    match = re.search(rf'id="{sec}"[^>]*><summary>(.*?)</summary>', text, re.S)
    assert match, sec
    return match.group(1)


def _test_connection(client, **extra):
    return client.post(f"/apartments/{_apt()['id']}/test-connection", data=_police(return_to=f"/apartments/{_apt()['id']}?view=settings", **extra), follow_redirects=False)


# ---- pure functions --------------------------------------------------------

class _Row(dict):
    def __getitem__(self, key):
        return self.get(key)


def test_open_section_and_section_done_pure():
    empty = _Row(internal_name="", legal_entity_id=None, addr_obec="", addr_house_no="", addr_zip="")
    basics = _Row(internal_name="X", legal_entity_id=1, addr_obec="Praha", addr_house_no="1", addr_zip="12000")
    state = {"steps": {}, "finished": False, "hidden": False, "legacy": False, "tested": False}
    facts = {"report_complete": False, "feeds": 0, "stays": 0}
    assert property_setup.open_section(empty, facts, state) == "basics"
    assert property_setup.open_section(basics, facts, state) == "police"
    filled = {**facts, "report_complete": True}
    assert not property_setup.section_done("police", basics, filled, state)
    assert property_setup.open_section(basics, filled, state) == "police"
    tested = {**state, "tested": True}
    assert property_setup.section_done("police", basics, filled, tested)
    assert property_setup.open_section(basics, filled, tested) is None
    assert property_setup.setup_complete(basics, filled, tested)
    assert property_setup.section_done("police", basics, filled, {**state, "finished": True})


# ---- first setup -------------------------------------------------------------

def test_create_redirects_to_the_wizard(host):
    assert host.created_location.split("?")[0].endswith(f"/apartments/{_apt()['id']}/setup/calendar")


def test_new_property_opens_police_only(host):
    text = _page(host)
    assert _open(text) == {"sec-police"}
    assert "Done" in _summary(text, "sec-basics")
    police = _summary(text, "sec-police")
    assert "about 3 min" in police
    assert re.search(r'<details class="police-letter-find" open>', text)
    assert re.search(r'<details class="police-letter-paste" id="police-letter-paste" open>', text)
    assert 'data-start-section="sec-police"' in text
    assert "data-ready-card" not in text


def test_saved_untested_keeps_police_open(host, fake):
    response = host.post(f"/apartments/{_apt()['id']}", data=_police(), follow_redirects=False)
    assert response.status_code == 303
    text = _page(host)
    assert _open(text) == {"sec-police"}
    assert "Saved, not tested yet" in _summary(text, "sec-police")
    assert "data-ready-card" not in text
    assert property_setup.load(_apt()["id"])["tested"] is False
    assert PASSWORD_TYPED not in text


def test_passing_test_shows_ready_card_once(host, fake):
    response = _test_connection(host)
    assert response.status_code == 303
    assert property_setup.load(_apt()["id"])["tested"] is True
    text = host.get(response.headers["location"]).text
    assert text.count("data-ready-card") == 1
    assert "/l/" in text and 'src="data:image/png;base64,' in text
    pin = _apt()["permalink_pin"]
    assert pin and pin in text
    assert _open(text) == set()
    assert PASSWORD_TYPED not in text
    again = _page(host)
    assert "data-ready-card" not in again
    assert _open(again) == set()
    assert property_setup.load(_apt()["id"])["finished"] is True


@pytest.mark.parametrize("error", [UbyportAuthError("no"), UbyportTransportError("down")])
def test_failed_test_does_not_complete(host, fake, error):
    fake["error"] = error
    response = _test_connection(host)
    assert response.status_code == 303
    assert property_setup.load(_apt()["id"])["tested"] is False
    text = host.get(response.headers["location"]).text
    assert "data-ready-card" not in text
    assert "sec-police" in _open(text)


def test_saving_basics_opens_police(host):
    apt_id = _apt()["id"]
    db.execute("UPDATE apartment SET addr_zip = '' WHERE id = ?", (apt_id,))
    assert _open(_page(host)) == {"sec-basics"}
    response = host.post(f"/apartments/{apt_id}", data=_basics(return_to=f"/apartments/{apt_id}?view=settings"), follow_redirects=False)
    assert response.status_code == 303
    text = host.get(response.headers["location"]).text
    assert _open(text) == {"sec-police"}


def test_save_redirect_section_does_not_override_first_setup(host):
    assert _open(_page(host, "?view=settings&section=property&saved=1")) == {"sec-police"}


def test_save_error_keeps_its_section_open(host):
    apt_id = _apt()["id"]
    response = host.post(f"/apartments/{apt_id}", data=_basics(addr_zip="x"), follow_redirects=False)
    text = response.text if response.status_code != 303 else host.get(response.headers["location"]).text
    assert "sec-basics" in _open(text)


# ---- tested cannot be posted --------------------------------------------------

def test_tested_cannot_be_posted(host, fake):
    apt_id = _apt()["id"]
    host.post(f"/apartments/{apt_id}", data=_police(tested="1"), follow_redirects=False)
    host.post(f"/apartments/{apt_id}", data=_police(setup_step="tested"), follow_redirects=False)
    text = _page(host, "?view=settings&tested=1")
    assert property_setup.load(apt_id)["tested"] is False
    assert "data-ready-card" not in text


def test_letter_saved_untested_does_not_mark(host, fake):
    apt_id = _apt()["id"]
    data = _police(uby_ws_password="", letter_fields="uby_idub", letter_line_uby_idub="5")
    host.post(f"/apartments/{apt_id}", data=data, follow_redirects=False)
    assert property_setup.load(apt_id)["tested"] is False


# ---- auto-finish guard ---------------------------------------------------------

def test_auto_finish_needs_a_passing_test(host, fake):
    apt_id = _apt()["id"]
    host.post(f"/apartments/{apt_id}", data=_police(), follow_redirects=False)
    db.insert("ical_feed", {"apartment_id": apt_id, "url": "https://example.test/c.ics", "active": 1, "created_at": db.utcnow()})
    for step in ("calendar", "guest_link"):
        property_setup.mark(apt_id, step, "done")
    text = _page(host, "")
    text = _page(host)
    assert property_setup.load(apt_id)["finished"] is False
    assert "data-ready-card" not in text
    property_setup.mark_tested(apt_id)
    first = _page(host)
    assert first.count("data-ready-card") == 1
    assert "data-ready-card" not in _page(host)


# ---- later edits ---------------------------------------------------------------

def test_finished_property_all_closed(host):
    apt_id = _apt()["id"]
    property_setup.finish(apt_id)
    text = _page(host)
    assert _open(text) == set()
    assert "data-ready-card" not in text
    for sec in SECTIONS:
        assert 'class="sec-state"' in _summary(text, sec)
    assert 'data-start-section="sec-police"' not in text
    assert _open(_page(host, "?view=settings&section=lock")) == {"sec-lock"}
    assert _open(_page(host, "?view=settings&section=reporting")) == {"sec-police", "sec-fee"}
