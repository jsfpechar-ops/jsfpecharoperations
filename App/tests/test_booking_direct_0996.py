"""Brief 0996: booking site direct payment model and setup step."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_rails, booking_setup, booking_site, db, property_page
from app.main import app
from tests.conftest import login_as

OWNER = "bookingdirect0996"
PRAGUE = booking_site.PRAGUE


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        db.execute("DELETE FROM user_account WHERE username = ?", ("bsite-pay-other",))
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        aid = a["id"]
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM settings WHERE key IN (?, ?)",
                   (f"booking_site:{aid}", f"booking_site_ical_done:{aid}"))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM login_token", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))
    other = db.query_one("SELECT id FROM user_account WHERE username = ?", ("bsite-pay-other",))
    if other:
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (other["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (other["id"],))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Direct Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield int(oid)
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    c = TestClient(app)
    assert login_as(c, OWNER, url="/login?lang=en", follow_redirects=False).status_code == 303
    return c


def _apartment(oid: int, **extra) -> int:
    values = {
        "owner_user_id": oid, "internal_name": "Direct Flat", "created_at": db.utcnow(),
        "stay_fee_rate_czk": 50, "checkin_hour": 15,
    }
    values.update(extra)
    return int(db.insert("apartment", values))


def _entity(oid: int, iban: str = "") -> int:
    return int(db.insert("legal_entity", {
        "owner_user_id": oid, "name": "Host s.r.o.", "iban": iban, "created_at": db.utcnow(),
    }))


def _quote(aid: int):
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    from datetime import datetime
    now = datetime(2026, 11, 2, 12, 0, tzinfo=PRAGUE)
    return booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=now)


def test_pending_default(owner):
    aid = _apartment(owner)
    q = _quote(aid)
    row = booking_site.create_pending(aid, owner, q, guest_name="Jan", guest_email="j@ex.test",
                                      lang="en", hold_id=None)
    assert row["status"] == "pending"
    stored = db.query_one("SELECT pay_method, request_expires_at FROM site_booking WHERE id = ?",
                          (row["id"],))
    assert stored["pay_method"] == "stripe"
    assert stored["request_expires_at"] is None


def test_requested_row(owner):
    aid = _apartment(owner)
    q = _quote(aid)
    row = booking_site.create_pending(
        aid, owner, q, guest_name="Jan", guest_email="j@ex.test", lang="en", hold_id=None,
        status="requested", pay_method="direct", request_expires_at="2026-11-08T10:00:00Z",
    )
    assert row["status"] == "requested" and row["pay_method"] == "direct"
    with pytest.raises(ValueError):
        booking_site.set_status(row["id"], "refunded")
    booking_site.set_status(row["id"], "paid", paid_at=db.utcnow())


def test_ready_needs_working_rail(owner):
    aid = _apartment(owner)
    assert booking_rails.ready(aid) is False
    db.update("apartment", aid, {"stay_fee_guest_rails": "cash"})
    assert booking_rails.ready(aid) is True
    db.update("apartment", aid, {"stay_fee_guest_rails": "revolut"})
    assert booking_rails.ready(aid) is False
    eid = _entity(owner, iban="")
    db.update("apartment", aid, {"legal_entity_id": eid, "stay_fee_guest_rails": "iban"})
    assert booking_rails.ready(aid) is False
    db.update("legal_entity", eid, {"iban": "CZ6508000000192000145399"})
    assert booking_rails.ready(aid) is True


def test_can_publish_without_stripe(owner):
    aid = _apartment(owner)
    db.update("apartment", aid, {"stay_fee_guest_rails": "cash"})
    booking_site.save_settings(aid, {"nightly_price_czk": 1800})
    rows = booking_setup.steps(aid, owner)
    assert booking_setup.can_publish(rows) is False  # photos and description still missing
    property_page.page_for(aid)
    db.execute("UPDATE property_page SET photos_json = ?, description = ? WHERE apartment_id = ?",
               ('["/p/a.jpg"]', "A quiet flat.", aid))
    rows = booking_setup.steps(aid, owner)
    assert booking_setup.can_publish(rows) is True
    db.update("apartment", aid, {"stay_fee_guest_rails": ""})
    rows = booking_setup.steps(aid, owner)
    assert booking_setup.can_publish(rows) is False


def test_pay_route(owner, client):
    aid = _apartment(owner)
    path = f"/apartments/{aid}/booking-site/pay"
    before = db.query_one("SELECT stay_fee_guest_rails FROM apartment WHERE id = ?", (aid,))
    r = client.post(path, data={"rails": "cash"}, follow_redirects=False)
    assert r.status_code == 303
    after = db.query_one("SELECT stay_fee_guest_rails FROM apartment WHERE id = ?", (aid,))
    assert after["stay_fee_guest_rails"] == "cash"
    r2 = client.post(path, data={}, follow_redirects=False)
    assert r2.status_code == 303
    assert db.query_one("SELECT stay_fee_guest_rails FROM apartment WHERE id = ?", (aid,))["stay_fee_guest_rails"] == "cash"
    assert before["stay_fee_guest_rails"] is None or after["stay_fee_guest_rails"] == "cash"

    auth.create_account("bsite-pay-other@example.test", "Other Host", username="bsite-pay-other")
    other_id = db.query_one("SELECT id FROM user_account WHERE username = ?", ("bsite-pay-other",))["id"]
    try:
        foreign = _apartment(int(other_id))
        assert client.post(f"/apartments/{foreign}/booking-site/pay", data={"rails": "cash"},
                           follow_redirects=False).status_code == 404
    finally:
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (other_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (other_id,))
