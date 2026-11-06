"""0954: TTLock setup. eAdmin step first, times required, one door-code state for every surface."""
from __future__ import annotations

import re

import pytest

from app import config, db, ttlock
from app.routes import admin
from app import property_health
from tests.test_smart_locks_page import USERS, _cleanup, _client, _connect, flats, hosts  # noqa: F401

LOCK = {"lock_id": "101", "alias": "Door A", "battery": 80, "tz_offset_ms": 0}


def _set_apartment(apartment_id, **fields):
    db.update("apartment", apartment_id, fields)


def _state_page(client, flat, state, hosts_ids):
    """Set the apartment and account for one state, return the lock tab HTML."""
    if state == "on":
        _connect(hosts_ids[0], "hjhfa_uhaaaa", locks=[LOCK])
        _set_apartment(flat, lock_provider="ttlock", lock_id="101", checkin_hour=15, checkout_hour=11)
    elif state == "off":
        _connect(hosts_ids[0], "hjhfa_uhaaaa", locks=[LOCK])
        _set_apartment(flat, lock_provider=None, lock_id="101", checkin_hour=15, checkout_hour=11)
    elif state == "offline":
        _connect(hosts_ids[0], "hjhfa_uhaaaa", locks=[LOCK])
        db.execute("UPDATE lock_account SET status = 'reauth_needed' WHERE owner_user_id = ?", (hosts_ids[0],))
        _set_apartment(flat, lock_provider="ttlock", lock_id="101", checkin_hour=15, checkout_hour=11)
    elif state == "times":
        _connect(hosts_ids[0], "hjhfa_uhaaaa", locks=[LOCK])
        _set_apartment(flat, lock_provider="ttlock", lock_id="101", checkin_hour=None, checkout_hour=11)
    return client.get(f"/apartments/{flat}?view=settings&section=lock&lang=en").text


@pytest.fixture
def ttl(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "enabled", lambda: True)
    yield


def _strip_state(page):
    return re.search(r'data-strip="door" data-state="([^"]+)"', page).group(1)


def _block(page):
    m = re.search(r'<div class="lock-state"(?: id="[^"]+")? data-state="([^"]+)" role="status">(.*?)</form>', page, re.S)
    return m


@pytest.mark.parametrize("state", ["on", "off", "offline", "times"])
def test_state_block_matches_the_state(ttl, hosts, flats, state):
    client = _client(USERS[0])
    page = _state_page(client, flats[0], state, hosts)
    block = _block(page)
    assert block and block.group(1) == state
    assert 'id="door_codes"' not in page
    if state != "off":  # 0987 run 2: off with a connected lock shows the setup row (no form)
        assert f'action="/apartments/{flats[0]}/door-codes"' in block.group(2)
    else:
        assert 'href="#door-code"' in page
    if state == "on":
        assert "Automatic door codes: On" in block.group(2)
        assert "Lock online" in block.group(2)
        assert 'value="off"' in block.group(2) and "Turn off" in block.group(2)
    if state == "off":
        assert "Automatic door codes: Turned off" in block.group(2)
        assert 'href="#door-code"' in page  # 0987 run 2: off shows the setup row, no Turn on form
        assert "ui-btn-primary" in block.group(2)
    if state == "offline":
        assert "Automatic door codes: lock offline" in block.group(2)
        assert "TTLock no longer accepts this connection" in block.group(2)
        assert 'value="off"' in block.group(2)
        assert "Automatic door codes: On" not in block.group(2)
    if state == "times":
        assert "Automatic door codes: waiting for check-in and check-out times" in block.group(2)
        assert "Set check-in and check-out times first" in block.group(2)
        assert 'value="off"' in block.group(2)
        assert "Automatic door codes: On" not in block.group(2)


def test_warning_line_only_when_off_and_a_time_is_missing(ttl, hosts, flats):
    client = _client(USERS[0])
    page = _state_page(client, flats[0], "off", hosts)
    assert 'id="lock-times-required"' not in page  # times are set here
    _set_apartment(flats[0], checkout_hour=None, lock_provider=None)
    page = client.get(f"/apartments/{flats[0]}?view=settings&section=lock&lang=en").text
    assert 'id="lock-times-required"' in page


@pytest.mark.parametrize("state", ["on", "off", "offline", "times"])
def test_strip_card_and_health_agree(ttl, hosts, flats, state):
    client = _client(USERS[0])
    page = _state_page(client, flats[0], state, hosts)
    strip = _strip_state(page)
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (flats[0],))
    door_code = admin._door_code_context(apartment, flats[0])
    rows = property_health.checks(apartment, [], None, door_code, open_kinds=set(), guest_used=False, link_due=False)
    door = next(r for r in rows if r["key"] == "door")
    expected = {"on": "ok", "off": "off"}.get(state, "bad")
    assert strip == expected == door["state"]


@pytest.mark.parametrize("lang,first", [
    ("en", "eAdmin"), ("cs", "eAdmin"), ("vi", "eAdmin"),
])
def test_first_guide_step_names_ubyhost_as_eadmin(ttl, hosts, flats, lang, first):
    _connect(hosts[0], "hjhfa_uhaaaa")
    page = _client(USERS[0]).get(f"/apartments/{flats[0]}?view=settings&section=lock&lang={lang}").text
    ol = re.search(r'<ol class="guide-steps">(.*?)</ol>', page, re.S)
    assert ol
    first_li = re.search(r"<li>(.*?)</li>", ol.group(1), re.S).group(1)
    assert first in first_li and "UbyHost" in first_li
    assert 'href="/guide#door-codes-share"' in page


def test_turn_off_keeps_lock_and_issued_codes(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    _set_apartment(flats[0], lock_provider="ttlock", lock_id="101", checkin_hour=15, checkout_hour=11)
    before = db.query_one("SELECT COUNT(*) AS n FROM door_code WHERE apartment_id = ?", (flats[0],))["n"]
    r = _client(USERS[0]).post(f"/apartments/{flats[0]}/door-codes", data={"mode": "off", "return_to": "x"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    row = db.query_one("SELECT lock_provider, lock_id FROM apartment WHERE id = ?", (flats[0],))
    assert row["lock_provider"] is None and row["lock_id"] == "101"
    after = db.query_one("SELECT COUNT(*) AS n FROM door_code WHERE apartment_id = ?", (flats[0],))["n"]
    assert before == after


def test_turn_on_needs_both_times(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    _set_apartment(flats[0], lock_provider=None, lock_id="101", checkin_hour=None, checkout_hour=11)
    r = _client(USERS[0]).post(f"/apartments/{flats[0]}/door-codes", data={"mode": "on"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] is None


def test_turn_on_with_both_times_sets_ttlock(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    _set_apartment(flats[0], lock_provider=None, lock_id="101", checkin_hour=15, checkout_hour=11)
    _client(USERS[0]).post(f"/apartments/{flats[0]}/door-codes", data={"mode": "on"}, follow_redirects=False)
    row = db.query_one("SELECT lock_provider, lock_id FROM apartment WHERE id = ?", (flats[0],))
    assert row["lock_provider"] == "ttlock" and row["lock_id"] == "101"


def test_unknown_mode_leaves_door_codes_unchanged(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    _set_apartment(flats[0], lock_provider="ttlock", lock_id="101", checkin_hour=15, checkout_hour=11)
    response = _client(USERS[0]).post(
        f"/apartments/{flats[0]}/door-codes", data={"mode": "toggle"}, follow_redirects=False
    )
    assert response.status_code in (302, 303)
    assert response.headers["location"].endswith("#sec-lock")
    row = db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))
    assert row["lock_provider"] == "ttlock"


def test_turn_on_refuses_a_lock_used_by_another_property(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    other = db.insert("apartment", {
        "internal_name": "Other flat", "owner_user_id": hosts[0], "permalink_token": "smartother0954",
        "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(), "lock_provider": "ttlock",
        "lock_id": "101", "checkin_hour": 15, "checkout_hour": 11,
    })
    try:
        _set_apartment(flats[0], lock_provider=None, lock_id="101", checkin_hour=15, checkout_hour=11)
        _client(USERS[0]).post(f"/apartments/{flats[0]}/door-codes", data={"mode": "on"}, follow_redirects=False)
        assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] is None
    finally:
        db.execute("DELETE FROM apartment WHERE id = ?", (other,))


def test_first_connection_turns_on_the_one_ready_property(ttl, hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    _set_apartment(flats[0], lock_provider=None, lock_id=None, checkin_hour=15, checkout_hour=11)
    monkeypatch.setattr(ttlock, "check_locks", lambda account_id: ([LOCK], 0))
    _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"})
    row = db.query_one("SELECT lock_provider, lock_id FROM apartment WHERE id = ?", (flats[0],))
    assert row["lock_provider"] == "ttlock" and row["lock_id"] == "101"


def test_first_connection_does_not_guess_between_properties(ttl, hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    _set_apartment(flats[0], lock_provider=None, lock_id=None, checkin_hour=15, checkout_hour=11)
    second = db.insert("apartment", {
        "internal_name": "Second flat", "owner_user_id": hosts[0], "permalink_token": "smartsecond0954",
        "permalink_pin": "123456", "active": 1, "created_at": db.utcnow(),
        "checkin_hour": 15, "checkout_hour": 11,
    })
    try:
        monkeypatch.setattr(ttlock, "check_locks", lambda account_id: ([LOCK], 0))
        _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"})
        assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] is None
    finally:
        db.execute("DELETE FROM apartment WHERE id = ?", (second,))


def test_first_connection_skips_a_property_with_a_time_missing(ttl, hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    _set_apartment(flats[0], lock_provider=None, lock_id=None, checkin_hour=None, checkout_hour=11)
    monkeypatch.setattr(ttlock, "check_locks", lambda account_id: ([LOCK], 0))
    _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"})
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] is None


def test_saved_lock_choice_stays_off_on_first_connection(ttl, hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")
    _set_apartment(flats[0], lock_provider=None, lock_id="101", checkin_hour=15, checkout_hour=11)
    monkeypatch.setattr(ttlock, "check_locks", lambda account_id: ([LOCK], 0))
    _client(USERS[0]).post("/smart-locks/refresh", data={"return_to": f"/apartments/{flats[0]}"})
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] is None


def test_main_save_without_lock_fields_keeps_the_provider(ttl, hosts, flats):
    _connect(hosts[0], "hjhfa_uhaaaa", locks=[LOCK])
    _set_apartment(flats[0], lock_provider="ttlock", lock_id="101", checkin_hour=15, checkout_hour=11)
    _client(USERS[0]).post(f"/apartments/{flats[0]}", data={"internal_name": "Lock tab flat 0 renamed"})
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (flats[0],))["lock_provider"] == "ttlock"
