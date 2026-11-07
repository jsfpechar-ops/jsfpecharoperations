"""Brief 0998: host confirm / decline for direct booking requests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_cancel, booking_checkout, booking_direct, booking_manage, booking_site, config, db
from app.main import app
from tests.conftest import login_as

OWNER = "directhost0998"
OTHER = "directother0998"


def _cleanup():
    for name in (OWNER, OTHER):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        oid = row["id"]
        for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            aid = a["id"]
            db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (aid,))
            db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (aid,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (aid,))
            db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
            db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{aid}",))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Direct Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "DH", "created_at": db.utcnow(),
                                        "stay_fee_guest_rails": "cash"}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000})
    from app import property_page
    property_page.page_for(aid)
    client = TestClient(app)
    login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    try:
        yield {"aid": aid, "oid": oid, "client": client}
    finally:
        _cleanup()


def _quote(aid: int):
    from app.booking_site import PRAGUE
    from datetime import datetime
    now = datetime(2026, 11, 2, 12, 0, tzinfo=PRAGUE)
    return booking_site.quote(aid, "2026-12-01", "2026-12-04", 2, now=now)


def _requested(owner_ctx) -> dict:
    aid, oid = owner_ctx["aid"], owner_ctx["oid"]
    q = _quote(aid)
    hold = db.insert("booking_hold", {
        "apartment_id": aid, "date_from": q["date_from"], "date_to": q["date_to"],
        "expires_at": "2099-01-01T00:00:00Z", "created_at": db.utcnow(),
    })
    return booking_site.create_pending(
        aid, oid, q, guest_name="Jan Novak", guest_email="jan@example.test", lang="en",
        hold_id=int(hold), status="requested", pay_method="direct",
        request_expires_at="2099-01-01T00:00:00Z",
    )


def test_confirm_creates_reservation(owner, monkeypatch):
    booking = _requested(owner)
    from app import stripe_connect
    monkeypatch.setattr(stripe_connect, "_api", lambda: (_ for _ in ()).throw(RuntimeError("stripe")))
    result = booking_direct.confirm(int(booking["id"]), owner["oid"])
    assert result["error"] is None
    row = db.query_one("SELECT status, reservation_id FROM site_booking WHERE id = ?", (booking["id"],))
    assert row["status"] == "paid" and row["reservation_id"]
    res = db.query_one("SELECT source, uid, status FROM reservation WHERE id = ?", (row["reservation_id"],))
    assert dict(res) == {"source": "site", "uid": f"site-{booking['id']}", "status": "active"}
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None
    kinds = {r["kind"] for r in db.query("SELECT kind FROM email_outbox")}
    assert "site_booking_confirmed" in kinds


def test_confirm_twice(owner):
    booking = _requested(owner)
    booking_direct.confirm(int(booking["id"]), owner["oid"])
    second = booking_direct.confirm(int(booking["id"]), owner["oid"])
    assert second["error"] == "not_confirmable"
    assert len(db.query("SELECT id FROM reservation WHERE apartment_id = ?", (owner["aid"],))) == 1


def test_confirm_expired_if_free(owner):
    booking = _requested(owner)
    booking_site.set_status(int(booking["id"]), "expired")
    assert booking_direct.confirm(int(booking["id"]), owner["oid"])["error"] is None
    from datetime import datetime
    q2 = booking_site.quote(owner["aid"], "2026-12-10", "2026-12-13", 2,
                            now=datetime(2026, 11, 2, 12, 0, tzinfo=booking_site.PRAGUE))
    hold2 = db.insert("booking_hold", {
        "apartment_id": owner["aid"], "date_from": q2["date_from"], "date_to": q2["date_to"],
        "expires_at": "2099-01-01T00:00:00Z", "created_at": db.utcnow(),
    })
    booking2 = booking_site.create_pending(
        owner["aid"], owner["oid"], q2, guest_name="Eva", guest_email="e@ex.test", lang="en",
        hold_id=int(hold2), status="requested", pay_method="direct",
        request_expires_at="2099-01-01T00:00:00Z",
    )
    booking_site.set_status(int(booking2["id"]), "expired")
    db.insert("reservation", {
        "apartment_id": owner["aid"], "source": "manual", "uid": "x",
        "date_from": booking2["date_from"], "date_to": booking2["date_to"], "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert booking_direct.confirm(int(booking2["id"]), owner["oid"])["error"] == "taken"


def test_confirm_other_owner_404(owner):
    booking = _requested(owner)
    auth.create_account(f"{OTHER}@example.test", "Other", username=OTHER)
    other = TestClient(app)
    login_as(other, OTHER, url="/login?lang=en", follow_redirects=False)
    r = other.post(f"/apartments/{owner['aid']}/booking-site/confirm",
                   data={"booking_id": booking["id"]}, follow_redirects=False)
    assert r.status_code == 404
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (booking["id"],))["status"] == "requested"


def test_decline_frees_dates(owner):
    booking = _requested(owner)
    assert booking_direct.decline(int(booking["id"]), owner["oid"])["error"] is None
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (booking["id"],))["status"] == "cancelled"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None
    from app import booking_checkout as bc
    q = _quote(owner["aid"])
    assert bc.hold_dates(owner["aid"], q["date_from"], q["date_to"], minutes=60) is not None


def test_host_cancel_direct_no_refund(owner, monkeypatch):
    booking = _requested(owner)
    booking_direct.confirm(int(booking["id"]), owner["oid"])
    from app import stripe_connect
    monkeypatch.setattr(stripe_connect, "_api", lambda: (_ for _ in ()).throw(RuntimeError("stripe")))
    out = booking_cancel.cancel(int(booking["id"]), by_host=True)
    assert out["error"] is None and out["refund_czk"] == 0
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (booking["id"],))["status"] == "cancelled"
    assert booking_cancel.cancel(int(booking["id"]), by_host=False)["error"] == "not_cancellable"


def test_request_mail_to_host(owner):
    eid = int(db.insert("legal_entity", {
        "owner_user_id": owner["oid"], "name": "Host", "contact_email": "host-bill@example.test",
        "created_at": db.utcnow(),
    }))
    db.update("apartment", owner["aid"], {"legal_entity_id": eid})
    q = _quote(owner["aid"])
    sent = booking_checkout.start_direct(owner["aid"], q, guest_name="Eva", guest_email="e@ex.test", lang="en")
    kinds = [r["kind"] for r in db.query("SELECT kind FROM email_outbox")]
    assert kinds.count("site_booking_request_host") == 1
    assert sent["booking"]["id"]


def test_host_rows_actions(owner):
    booking = _requested(owner)
    rows = booking_manage.host_rows(owner["aid"])
    req = next(r for r in rows if r["id"] == int(booking["id"]))
    assert req["can_confirm"] and req["can_decline"]
    db.insert("site_booking", {
        "apartment_id": owner["aid"], "owner_user_id": owner["oid"], "status": "expired",
        "pay_method": "stripe", "date_from": "2026-10-01", "date_to": "2026-10-05",
        "guests": 2, "nights": 4, "nightly_czk": 100, "cleaning_fee_czk": 0, "total_czk": 400,
        "cancellation_policy": "moderate", "terms_version": booking_site.TERMS_VERSION,
        "terms_accepted_at": db.utcnow(), "cancel_token_hash": "x", "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    })
    ids = {r["id"] for r in booking_manage.host_rows(owner["aid"])}
    assert int(booking["id"]) in ids
    stripe_exp = db.query_one("SELECT id FROM site_booking WHERE pay_method = 'stripe' AND status = 'expired'")
    assert stripe_exp["id"] not in ids


def test_setup_page_buttons(owner):
    _requested(owner)
    page = owner["client"].get(f"/apartments/{owner['aid']}/booking-site?lang=en")
    assert page.status_code == 200
    assert "Mark paid" in page.text


def test_decline_expired_direct_row(owner):
    booking = _requested(owner)
    db.execute("UPDATE site_booking SET status = ?, request_expires_at = ? WHERE id = ?",
               ("expired", "2000-01-01T00:00:00Z", int(booking["id"])))
    assert booking_direct.decline(int(booking["id"]), owner["oid"])["error"] is None
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (booking["id"],))["status"] == "cancelled"


def test_expire_requests_skips_paid_row(owner):
    booking = _requested(owner)
    db.execute(
        "UPDATE site_booking SET request_expires_at = ? WHERE id = ?",
        ("2000-01-01T00:00:00Z", int(booking["id"])),
    )
    booking_direct.confirm(int(booking["id"]), owner["oid"])
    assert booking_checkout.expire_requests() == 0
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (booking["id"],))["status"] == "paid"


def test_host_cancel_direct_mail_has_no_card_refund(owner, monkeypatch):
    booking = _requested(owner)
    booking_direct.confirm(int(booking["id"]), owner["oid"])
    captured: list[dict] = []

    def _enqueue(**kwargs):
        captured.append(kwargs)

    from app import mail
    monkeypatch.setattr(mail, "enqueue", _enqueue)
    booking_cancel.cancel(int(booking["id"]), by_host=True)
    texts = [m["payload"].get("text", "") for m in captured]
    blob = "\n".join(texts).lower()
    assert "card" not in blob and "kartu" not in blob
    assert "refunded to the guest" not in blob and "vráceno hostovi" not in blob


def test_direct_confirm_mail_says_confirmed_not_paid(owner):
    booking = _requested(owner)
    booking_direct.confirm(int(booking["id"]), owner["oid"])
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = ? ORDER BY id DESC",
        ("site_booking_confirmed",),
    )
    import json
    payload = json.loads(row["payload"])
    text = payload.get("text", "")
    assert "Paid:" not in text and "Zaplaceno:" not in text
