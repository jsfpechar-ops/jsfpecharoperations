"""Brief 0822: the host lists and cancels site bookings (full refund) on the booking-site page."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_site, booking_webhook
from app import config, db, mail, property_page, stripe_connect
from app.main import app
from tests.conftest import login_as

OWNER = "bookhostcancel"
OTHER = "bookhostother"
_SEQ = [0]


def _cleanup(username: str) -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM settings WHERE key = ?", ("invoice_purge_unlock",))
    db.insert("settings", {"key": "invoice_purge_unlock", "value": "1"})
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    for e in db.query("SELECT id FROM legal_entity WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM invoice_item WHERE invoice_id IN "
                   "(SELECT id FROM invoice WHERE legal_entity_id = ?)", (e["id"],))
        db.execute("DELETE FROM invoice WHERE legal_entity_id = ?", (e["id"],))
        db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id = ?", (e["id"],))
    db.execute("DELETE FROM settings WHERE key = ?", ("invoice_purge_unlock",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeRefunds:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []
        self.fail = False

    def create(self, params=None, options=None):
        if self.fail:
            raise RuntimeError("stripe unavailable")
        assert options and options.get("stripe_account") == "acct_cancel"
        self.created.append(params)
        self.options.append(options)
        return {"id": "re_cancel_test"}


@pytest.fixture
def refunds(monkeypatch):
    fake = _FakeRefunds()

    class _V1:
        pass

    v1 = _V1()
    v1.refunds = fake

    class _Client:
        pass

    client = _Client()
    client.v1 = v1
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    monkeypatch.setattr(stripe_connect, "_client", lambda: client)
    monkeypatch.setattr(stripe_connect, "_api", lambda: client)
    return fake


def _legal_entity(oid: int) -> int:
    return int(db.insert("legal_entity", {"owner_user_id": oid, "name": "Host Cancel",
                                          "seat": "Praha 1", "ico": "04656679",
                                          "registry_entry": "ZR", "vat_status": "non_payer",
                                          "contact_email": "host@example.test",
                                          "created_at": db.utcnow()}))


def _new_apartment(oid: int, entity: int, name: str) -> int:
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": name,
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    return aid


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup(OWNER)
    _cleanup(OTHER)
    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(mail, "enqueue", lambda **kw: sent.append(kw) or 1)
    auth.create_account(f"{OWNER}@example.test", "Host Cancel", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = _legal_entity(oid)
    aid = _new_apartment(oid, entity, "Host Flat")
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_cancel", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    try:
        yield {"aid": aid, "oid": oid, "entity": entity, "sent": sent}
    finally:
        _cleanup(OWNER)
        _cleanup(OTHER)


@pytest.fixture
def client(host):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


def _paid(site, policy, guest="Jana Novak", date_from="2027-06-10", date_to="2027-06-13") -> int:
    """Save the policy, take a booking through the paid webhook, return its id."""
    _SEQ[0] += 1
    n = _SEQ[0]
    booking_site.save_settings(site["aid"], {"cancellation_policy": policy})
    q = booking_site.quote(site["aid"], date_from, date_to, 2)
    hold = booking_checkout.hold_dates(site["aid"], date_from, date_to)
    row = booking_site.create_pending(site["aid"], site["oid"], q, guest_name=guest,
                                      guest_email="jana@example.test", lang="en", hold_id=hold)
    booking_site.attach_session(row["id"], f"cs_host_{n}")
    booking_webhook.handle({"id": f"evt_host_{n}", "type": "checkout.session.completed",
                            "data": {"object": {
                                "id": f"cs_host_{n}", "payment_status": "paid",
                                "payment_intent": f"pi_host_{n}",
                                "metadata": {"site_booking_id": str(row["id"])}}}})
    return int(row["id"])


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def test_page_lists_the_booking(host, client, refunds):
    page = client.get(f"/apartments/{host['aid']}/booking-site?lang=en")
    assert page.status_code == 200
    assert "No bookings from the site yet." in page.text
    bid = _paid(host, "moderate")
    total = int(booking_site.get(bid)["total_czk"])
    page = client.get(f"/apartments/{host['aid']}/booking-site?lang=en")
    assert "Bookings from the site" in page.text
    assert "Jana N." in page.text
    assert str(total) in _digits(page.text)
    assert "Cancel and refund" in page.text
    assert "No bookings from the site yet." not in page.text


def test_host_cancel_refunds_in_full(host, client, refunds):
    bid = _paid(host, "moderate")
    total = int(booking_site.get(bid)["total_czk"])
    response = client.post(f"/apartments/{host['aid']}/booking-site/cancel",
                           data={"booking_id": str(bid)}, follow_redirects=False)
    assert response.status_code == 303
    after = booking_site.get(bid)
    assert after["status"] == "refunded" and int(after["refunded_czk"]) == total
    assert len(refunds.created) == 1
    assert refunds.created[0]["amount"] == total * 100
    assert refunds.options[0]["idempotency_key"] == f"site_booking_cancel_refund_{bid}"
    res = db.query_one("SELECT status FROM reservation WHERE id = ?", (after["reservation_id"],))
    assert res["status"] == "cancelled"
    assert property_page.dates_available(host["aid"], "2027-06-10", "2027-06-13")
    page = client.get(response.headers["location"])
    assert "The booking is cancelled and the guest is refunded." in page.text


def test_other_owner_and_other_apartment_are_404(host, client, refunds):
    other = int(db.insert("user_account", {"username": OTHER, "password_hash": "x",
                                            "created_at": db.utcnow()}))
    other_entity = _legal_entity(other)
    other_aid = _new_apartment(other, other_entity, "Not Yours")
    foreign_bid = _paid({"aid": other_aid, "oid": other}, "moderate")
    own_aid2 = _new_apartment(host["oid"], host["entity"], "Second Flat")
    second_bid = _paid({"aid": own_aid2, "oid": host["oid"]}, "moderate")
    url = f"/apartments/{host['aid']}/booking-site/cancel"
    assert client.post(url, data={"booking_id": str(foreign_bid)}).status_code == 404
    assert client.post(url, data={"booking_id": str(second_bid)}).status_code == 404
    assert client.post(url, data={"booking_id": "abc"}).status_code == 404
    assert booking_site.get(foreign_bid)["status"] == "paid"
    assert booking_site.get(second_bid)["status"] == "paid"
    assert refunds.created == []


def test_failed_refund_shows_retry_and_retry_works(host, client, refunds):
    bid = _paid(host, "moderate")
    total = int(booking_site.get(bid)["total_czk"])
    url = f"/apartments/{host['aid']}/booking-site/cancel"
    refunds.fail = True
    response = client.post(url, data={"booking_id": str(bid)}, follow_redirects=False)
    assert response.status_code == 303
    page = client.get(response.headers["location"])
    assert "The refund did not go through." in page.text
    assert "Repeat the refund" in page.text
    assert refunds.created == []
    refunds.fail = False
    response = client.post(url, data={"booking_id": str(bid)}, follow_redirects=False)
    assert response.status_code == 303
    after = booking_site.get(bid)
    assert after["status"] == "refunded" and int(after["refunded_czk"]) == total
    assert len(refunds.created) == 1
    assert refunds.options[0]["idempotency_key"] == f"site_booking_cancel_refund_{bid}"


def test_paid_and_cancelled_rows_have_the_right_button(host, client, refunds):
    bid = _paid(host, "moderate")
    page = client.get(f"/apartments/{host['aid']}/booking-site?lang=en")
    assert "Cancel and refund" in page.text
    client.post(f"/apartments/{host['aid']}/booking-site/cancel",
                data={"booking_id": str(bid)}, follow_redirects=False)
    page = client.get(f"/apartments/{host['aid']}/booking-site?lang=en")
    assert booking_site.get(bid)["status"] == "refunded"
    assert "Cancel and refund" not in page.text
    assert "Repeat the refund" not in page.text
