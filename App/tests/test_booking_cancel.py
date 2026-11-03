"""Brief 0821: guest self-cancel and refunds for a paid booking site reservation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_cancel, booking_manage, booking_site, booking_webhook
from app import config, db, host_i18n, mail, property_page, stripe_connect
from app.main import app

OWNER = "cancelbookhost"
PRAGUE = ZoneInfo("Europe/Prague")
_SEQ = [0]


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


@pytest.fixture
def site(monkeypatch):
    db.init_db()
    _cleanup()
    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(mail, "enqueue", lambda **kw: sent.append(kw) or 1)
    auth.create_account(f"{OWNER}@example.test", "Cancel Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = db.insert("legal_entity", {"owner_user_id": oid, "name": "Cancel Host",
                                        "seat": "Praha 1", "ico": "04656679",
                                        "registry_entry": "ŽR", "vat_status": "non_payer",
                                        "contact_email": "host@example.test",
                                        "created_at": db.utcnow()})
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Cancel Flat",
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_cancel", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    try:
        yield {"aid": aid, "oid": oid, "entity": entity, "sent": sent}
    finally:
        _cleanup()


def _paid(site, policy, lang="en", date_from="2027-06-10", date_to="2027-06-13") -> int:
    """Save the policy, take a booking through the paid webhook, return its id."""
    _SEQ[0] += 1
    n = _SEQ[0]
    booking_site.save_settings(site["aid"], {"cancellation_policy": policy})
    q = booking_site.quote(site["aid"], date_from, date_to, 2)
    hold = booking_checkout.hold_dates(site["aid"], date_from, date_to)
    row = booking_site.create_pending(site["aid"], site["oid"], q, guest_name="Petr Svoboda",
                                      guest_email="petr@example.test", lang=lang, hold_id=hold)
    booking_site.attach_session(row["id"], f"cs_cancel_{n}")
    booking_webhook.handle({"id": f"evt_cancel_{n}", "type": "checkout.session.completed",
                            "data": {"object": {
                                "id": f"cs_cancel_{n}", "payment_status": "paid",
                                "payment_intent": f"pi_cancel_{n}",
                                "metadata": {"site_booking_id": str(row["id"])}}}})
    return int(row["id"])


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def test_guest_cancel_full_refund_frees_the_dates(site, refunds):
    bid = _paid(site, "moderate")
    site["sent"].clear()  # drop the paid-time host notice; keep only the cancel mails
    total = int(booking_site.get(bid)["total_czk"])
    assert booking_cancel.cancel(bid, by_host=False) == {"error": None, "refund_czk": total}
    assert len(refunds.created) == 1
    assert refunds.created[0]["amount"] == total * 100
    assert refunds.options[0]["stripe_account"] == "acct_cancel"
    assert refunds.options[0]["idempotency_key"] == f"site_booking_cancel_refund_{bid}"
    after = booking_site.get(bid)
    assert after["status"] == "refunded" and int(after["refunded_czk"]) == total
    res = db.query_one("SELECT status FROM reservation WHERE id = ?", (after["reservation_id"],))
    assert res["status"] == "cancelled"
    assert property_page.dates_available(site["aid"], "2027-06-10", "2027-06-13")
    mails = [kw for kw in site["sent"] if kw["kind"] in ("site_booking_refunded", "site_booking_host")]
    assert sorted(kw["kind"] for kw in mails) == ["site_booking_host", "site_booking_refunded"]
    assert all(str(total) in _digits(kw["payload"]["text"]) for kw in mails)
    again = booking_cancel.cancel(bid, by_host=False)
    assert again["error"] == "not_cancellable"
    assert len(refunds.created) == 1


def test_non_refundable_cancels_without_a_refund(site, refunds):
    bid = _paid(site, "non_refundable")
    result = booking_cancel.cancel(bid, by_host=False)
    assert result["error"] is None and result["refund_czk"] == 0
    after = booking_site.get(bid)
    assert after["status"] == "cancelled" and int(after["refunded_czk"] or 0) == 0
    assert refunds.created == []
    guest = [kw for kw in site["sent"] if kw["kind"] == "site_booking_refunded"]
    assert len(guest) == 1 and "refund" in guest[0]["payload"]["text"].lower()
    assert property_page.dates_available(site["aid"], "2027-06-10", "2027-06-13")


def test_partial_refund_moderate_late(site, refunds):
    bid = _paid(site, "moderate")
    now = datetime(2027, 6, 8, 12, 0, tzinfo=PRAGUE)
    booking = booking_site.get(bid)
    expected = booking_site.refund_czk(
        booking, checkin_hour=booking_site.settings(site["aid"])["checkin_hour"], now=now)
    assert 0 < expected < int(booking["total_czk"])
    assert booking_cancel.cancel(bid, by_host=False, now=now) == {"error": None, "refund_czk": expected}
    after = booking_site.get(bid)
    assert after["status"] == "refunded" and int(after["refunded_czk"]) == expected
    assert refunds.created[0]["amount"] == expected * 100
    assert db.query_one("SELECT id FROM audit WHERE action = ? AND owner_user_id = ?",
                        ("site_invoice_needs_correction", site["oid"])) is not None


def test_host_cancel_is_always_full(site, refunds):
    bid = _paid(site, "non_refundable")
    assert booking_cancel.cancel(bid, by_host=True)["error"] is None
    booking = booking_site.get(bid)
    total = int(booking["total_czk"])
    assert refunds.created[0]["amount"] == total * 100
    facts = booking_webhook._facts(booking, booking_webhook._apartment(booking), "cs")
    facts["refund"] = total
    host = [kw for kw in site["sent"] if kw["kind"] == "site_booking_host"]
    assert host[-1]["payload"]["text"] == host_i18n.translate(
        "cs", "site_booking.mail.cancel_host_by_host", **facts)


def test_failed_refund_keeps_cancelled_and_retry_refunds_once(site, refunds):
    bid = _paid(site, "moderate")
    total = int(booking_site.get(bid)["total_czk"])
    refunds.fail = True
    assert booking_cancel.cancel(bid, by_host=False) == {"error": "refund_failed", "refund_czk": total}
    after = booking_site.get(bid)
    assert after["status"] == "cancelled" and int(after["refunded_czk"] or 0) == 0
    assert refunds.created == []
    assert any(kw["kind"] == "site_booking_host"
               and kw["idempotency_key"] == f"site_booking:{bid}:refund_failed"
               for kw in site["sent"])
    refunds.fail = False
    assert booking_cancel.cancel(bid, by_host=True) == {"error": None, "refund_czk": total}
    assert len(refunds.created) == 1
    assert refunds.created[0]["amount"] == total * 100
    assert refunds.options[0]["idempotency_key"] == f"site_booking_cancel_refund_{bid}"
    assert booking_site.get(bid)["status"] == "refunded"
    assert booking_cancel.cancel(bid, by_host=True)["error"] == "not_cancellable"
    assert len(refunds.created) == 1


def test_guest_cannot_cancel_after_check_in_starts(site, refunds):
    bid = _paid(site, "flexible")
    late = datetime(2027, 6, 11, 12, 0, tzinfo=PRAGUE)
    assert booking_cancel.cancel(bid, by_host=False, now=late) == {"error": "started"}
    assert booking_site.get(bid)["status"] == "paid"
    assert booking_cancel.cancel(bid, by_host=True, now=late)["error"] is None
    assert booking_site.get(bid)["status"] == "refunded"


def test_full_refund_issues_the_invoice_storno(site, refunds):
    bid = _paid(site, "moderate")
    assert len(db.query("SELECT id FROM invoice WHERE legal_entity_id = ?", (site["entity"],))) == 1
    assert booking_cancel.cancel(bid, by_host=False)["error"] is None
    rows = db.query("SELECT * FROM invoice WHERE legal_entity_id = ?", (site["entity"],))
    assert len(rows) == 2
    assert any(r["kind"] in ("storno", "corrective") for r in rows)


def test_guest_page_routes(site, refunds):
    bid = _paid(site, "moderate")
    view = booking_manage.view(booking_site.get(bid), "en")
    slug = property_page.ensure_slug(site["aid"])["slug"]
    token = booking_site.manage_token(bid)
    base = f"/p/{slug}/b/{bid}/{token}"
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    page = client.get(base)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "noindex" in page.headers["x-robots-tag"]
    assert view["name"] in page.text
    assert booking_manage.mask_email("petr@example.test") in page.text
    assert "petr@example.test" not in page.text
    assert "Cancel the booking" in page.text
    assert client.get(f"/p/{slug}/b/{bid}/{'0' * len(token)}").status_code == 404
    assert client.get(f"/p/{slug}/b/{bid + 1}/{token}").status_code == 404
    pending = booking_site.create_pending(
        site["aid"], site["oid"],
        booking_site.quote(site["aid"], "2027-07-01", "2027-07-03", 2),
        guest_name="Pavel Test", guest_email="pavel@example.test", lang="en",
        hold_id=booking_checkout.hold_dates(site["aid"], "2027-07-01", "2027-07-03"))
    ptoken = booking_site.manage_token(pending["id"])
    assert client.get(f"/p/{slug}/b/{pending['id']}/{ptoken}").status_code == 404
    assert "Zrušit rezervaci" in client.get(base + "?lang=cs").text
    ics = client.get(base + "/calendar.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "DTSTART;VALUE=DATE:20270610" in ics.text
    posted = client.post(base + "/cancel", follow_redirects=False)
    assert posted.status_code == 303
    assert "Booking cancelled" in client.get(base).text
