"""Brief 0820: the guest invoice for a paid booking site reservation."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_invoice, booking_site, booking_webhook, config, db
from app import invoices, mail, stripe_connect
from app.main import app

OWNER = "invoicebookhost"
FROM, TO = "2027-05-10", "2027-05-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
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

    def create(self, params=None, options=None):
        self.created.append(params)
        return {"id": "re_invoice_1"}


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
    auth.create_account(f"{OWNER}@example.test", "Invoice Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = db.insert("legal_entity", {"owner_user_id": oid, "name": "Invoice Host",
                                        "seat": "Praha 1", "ico": "04656679",
                                        "registry_entry": "ŽR", "vat_status": "non_payer",
                                        "contact_email": "host@example.test",
                                        "created_at": db.utcnow()})
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Invoice Flat",
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_invoice", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    q = booking_site.quote(aid, FROM, TO, 2)
    hold = booking_checkout.hold_dates(aid, FROM, TO)
    row = booking_site.create_pending(aid, oid, q, guest_name="Petr Svoboda",
                                      guest_email="petr@example.test", lang="cs", hold_id=hold)
    booking_site.attach_session(row["id"], "cs_invoice_1")
    row = booking_site.get(row["id"])
    row["sent"] = sent
    row["entity"] = entity
    try:
        yield row
    finally:
        _cleanup()


def _event(eid: str = "evt_invoice_1") -> Dict[str, Any]:
    return {"id": eid, "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_invoice_1", "payment_status": "paid", "payment_intent": "pi_invoice_1",
        "metadata": {"site_booking_id": "0"},
    }}}


def _paid(booking) -> None:
    event = _event()
    event["data"]["object"]["metadata"]["site_booking_id"] = str(booking["id"])
    booking_webhook.handle(event)


def test_paid_booking_gets_a_czech_invoice(booking, refunds):
    _paid(booking)
    row = booking_site.get(booking["id"])
    assert row["status"] == "paid" and row["invoice_id"] is not None
    inv = db.query_one("SELECT * FROM invoice WHERE id = ?", (row["invoice_id"],))
    assert inv["legal_entity_id"] == booking["entity"]
    assert inv["total_haler"] == int(row["total_czk"]) * 100
    assert inv["paid_on"] is not None
    assert invoices.download_pdf(int(row["invoice_id"])).startswith(b"%PDF")


def test_no_entity_details_means_no_invoice_but_booking_stays_paid(booking, refunds):
    db.execute("UPDATE legal_entity SET registry_entry = NULL WHERE id = ?", (booking["entity"],))
    _paid(booking)
    row = booking_site.get(booking["id"])
    assert row["status"] == "paid" and row["invoice_id"] is None
    rows = [dict(r) for r in db.query("SELECT * FROM audit WHERE owner_user_id = "
                                      "(SELECT owner_user_id FROM legal_entity WHERE id = ?)",
                                      (booking["entity"],))]
    skipped = [r for r in rows if "site_invoice_skipped" in " ".join(str(v) for v in r.values())]
    assert len(skipped) == 1


def test_ensure_is_idempotent(booking, refunds):
    _paid(booking)
    first = booking_invoice.ensure(booking["id"])
    second = booking_invoice.ensure(booking["id"])
    assert first is not None and first == second
    n = db.query_one("SELECT COUNT(*) AS n FROM invoice WHERE legal_entity_id = ?",
                     (booking["entity"],))["n"]
    assert n == 1


def test_host_invoice_made_by_hand_is_linked(booking, refunds, monkeypatch):
    _paid(booking)
    real = int(booking_site.get(booking["id"])["invoice_id"])
    db.execute("UPDATE site_booking SET invoice_id = NULL WHERE id = ?", (booking["id"],))

    def _already_invoiced(draft, actor_user_id):
        raise invoices.StayLimit("stay_already_invoiced", invoice_id=real)

    monkeypatch.setattr(invoices, "issue", _already_invoiced)
    assert booking_invoice.ensure(booking["id"]) == real
    assert int(booking_site.get(booking["id"])["invoice_id"]) == real


def test_tokens(booking):
    bid = booking["id"]
    token = booking_site.manage_token(bid)
    assert booking_site.token_ok(bid, token)
    assert not booking_site.token_ok(bid, "0" * len(token))
    assert not booking_site.token_ok(bid + 1, token)
    assert booking_site.manage_url(booking).endswith(f"/b/{bid}/{token}")


def test_pdf_route(booking, refunds):
    _paid(booking)
    bid = booking["id"]
    slug = "invoice-flat"  # the route does not read the slug; the token alone selects the booking
    token = booking_site.manage_token(bid)
    client = TestClient(app)
    ok = client.get(f"/p/{slug}/b/{bid}/{token}/invoice.pdf")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("application/pdf")
    assert ok.headers["cache-control"] == "no-store"
    assert ok.content.startswith(b"%PDF")
    bad = client.get(f"/p/{slug}/b/{bid}/{'0' * len(token)}/invoice.pdf")
    assert bad.status_code == 404


def test_pdf_route_is_404_while_pending(booking):
    slug = "invoice-flat"  # the route does not read the slug; the token alone selects the booking
    token = booking_site.manage_token(booking["id"])
    resp = TestClient(app).get(f"/p/{slug}/b/{booking['id']}/{token}/invoice.pdf")
    assert resp.status_code == 404


def test_confirmation_mail_carries_the_manage_link(booking, refunds):
    _paid(booking)
    link = booking_site.manage_url(booking_site.get(booking["id"]))
    assert any(link in str(m.get("payload", "")) or link in str(m.get("text", ""))
               for m in booking["sent"])
