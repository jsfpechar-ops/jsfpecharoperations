"""Brief 0816: booking site webhook (confirm, double-booking refund, expiry)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app import auth, booking_checkout, booking_site, booking_webhook, config, db, mail, stripe_connect

OWNER = "webhookhost"
FROM, TO = "2027-04-10", "2027-04-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeRefunds:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []

    def create(self, params=None, options=None):
        assert options and options.get("stripe_account") == "acct_hook"
        assert options.get("idempotency_key")
        self.created.append(params)
        self.options.append(options)
        return {"id": "re_test_1"}


@pytest.fixture
def refunds(monkeypatch):
    fake = _FakeRefunds()

    class _V1:
        pass

    _V1.refunds = fake

    class _Client:
        v1 = _V1()

    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return fake


@pytest.fixture
def booking(monkeypatch):
    db.init_db()
    _cleanup()
    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(mail, "enqueue", lambda **kw: sent.append(kw) or 1)
    auth.create_account(f"{OWNER}@example.test", "Hook Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = db.insert("legal_entity", {"owner_user_id": oid, "name": "Hook Host",
                                        "contact_email": "host@example.test",
                                        "created_at": db.utcnow()})
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Hook Flat",
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_hook", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    q = booking_site.quote(aid, FROM, TO, 2)
    hold = booking_checkout.hold_dates(aid, FROM, TO)
    row = booking_site.create_pending(aid, oid, q, guest_name="Jana Nová",
                                      guest_email="jana@example.test", lang="cs", hold_id=hold)
    booking_site.attach_session(row["id"], "cs_hook_1")
    row = booking_site.get(row["id"])
    row["sent"] = sent
    try:
        yield row
    finally:
        _cleanup()


def _event(etype: str, status: str = "paid", eid: str = "evt_1") -> Dict[str, Any]:
    return {"id": eid, "type": etype, "data": {"object": {
        "id": "cs_hook_1", "payment_status": status, "payment_intent": "pi_hook_1",
        "metadata": {"site_booking_id": "1"},
    }}}


def test_paid_creates_reservation_and_mails(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed"))
    row = booking_site.get(booking["id"])
    assert row["status"] == "paid" and row["stripe_payment_intent_id"] == "pi_hook_1"
    res = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    assert res["source"] == "site" and res["date_from"] == FROM and res["guest_email"] == "jana@example.test"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None
    kinds = sorted(m["kind"] for m in booking["sent"])
    assert kinds == ["site_booking_confirmed", "site_booking_host"]
    guest = next(m for m in booking["sent"] if m["kind"] == "site_booking_confirmed")
    assert "Rezervace potvrzena" in guest["subject"] and guest["payload"]["reply_to"] == "host@example.test"
    assert refunds.created == []


def test_paid_twice_is_idempotent(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed"))
    booking_webhook.handle(_event("checkout.session.async_payment_succeeded"))
    n = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?",
                     (booking["apartment_id"],))["n"]
    assert n == 1


def test_stale_pending_confirm_does_not_refund_own_reservation(booking, refunds):
    """Two paid events can both snapshot pending before the date lock.

    The second _confirm must not treat this booking's own reservation as a
    clash and refund the guest.
    """
    booking_webhook._confirm(booking, "pi_hook_1")
    booking_webhook._confirm(booking, "pi_hook_1")
    row = booking_site.get(booking["id"])
    assert row["status"] == "paid" and refunds.created == []
    n = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?",
                     (booking["apartment_id"],))["n"]
    assert n == 1


def test_unpaid_async_waits(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed", status="unpaid"))
    assert booking_site.get(booking["id"])["status"] == "pending"


def test_clash_refunds_in_full(booking, refunds):
    db.insert("reservation", {
        "apartment_id": booking["apartment_id"], "source": "ical", "uid": "airbnb-1",
        "date_from": "2027-04-12", "date_to": "2027-04-15", "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    booking_webhook.handle(_event("checkout.session.completed"))
    row = booking_site.get(booking["id"])
    assert row["status"] == "clash_refunded" and row["refunded_czk"] == 6500
    assert refunds.created[0]["payment_intent"] == "pi_hook_1"
    kinds = sorted(m["kind"] for m in booking["sent"])
    assert kinds == ["site_booking_host", "site_booking_refunded"]
    n = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE source = 'site' AND apartment_id = ?",
                     (booking["apartment_id"],))["n"]
    assert n == 0


def test_expired_releases_hold(booking, refunds):
    booking_webhook.handle(_event("checkout.session.expired", status="unpaid"))
    assert booking_site.get(booking["id"])["status"] == "expired"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None


def test_process_event_routes_booking_sessions(booking, refunds, monkeypatch):
    called = []
    from app import payment_links

    monkeypatch.setattr(payment_links, "on_paid", lambda e: called.append(e))
    stripe_connect.process_event(_event("checkout.session.completed", eid="evt_route_1"))
    assert called == []
    assert booking_site.get(booking["id"])["status"] == "paid"
    db.execute("DELETE FROM stripe_webhook_event WHERE event_id = ?", ("evt_route_1",))
