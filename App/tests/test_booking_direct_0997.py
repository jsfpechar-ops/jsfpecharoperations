"""Brief 0997: booking site direct-payment guest request flow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_site, config, db, host_i18n, property_page, stripe_connect
from app.main import app

OWNER = "directguest0997"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        aid = a["id"]
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{aid}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Guest Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Direct PP",
                                        "created_at": db.utcnow()}))
    property_page.page_for(aid)
    booking_site.save_settings(aid, {"nightly_price_czk": 1500, "cleaning_fee_czk": 0})
    property_page.publish_page(aid, published=True)
    try:
        yield aid
    finally:
        _cleanup()


def _client() -> TestClient:
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def _checkout_payload(**extra):
    data = {
        "date_from": "2026-12-10", "date_to": "2026-12-13", "guests": "2",
        "guest_name": "Anna Hostova", "guest_email": "anna@example.test",
        "terms": "1", "terms_version": booking_site.TERMS_VERSION,
        "lang": "en", "pay_mode": "direct",
    }
    data.update(extra)
    return data


def test_widget_ready_direct_only(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    assert property_page.widget_ready(owner) is True
    db.update("apartment", owner, {"stay_fee_guest_rails": ""})
    assert property_page.widget_ready(owner) is False


def test_request_holds_24h(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload())
    assert response.status_code == 200
    assert "Request sent" in response.text
    row = db.query_one("SELECT * FROM site_booking WHERE apartment_id = ?", (owner,))
    assert row["status"] == "requested" and row["pay_method"] == "direct"
    hold = db.query_one("SELECT expires_at FROM booking_hold WHERE id = ?", (row["hold_id"],))
    exp = datetime.fromisoformat(hold["expires_at"].replace("Z", "+00:00"))
    delta = exp - datetime.now(timezone.utc)
    assert timedelta(hours=23) <= delta <= timedelta(hours=25)
    assert db.query_one("SELECT id FROM reservation WHERE apartment_id = ?", (owner,)) is None


def test_second_request_same_dates_taken(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    client = _client()
    assert client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload()).status_code == 200
    r2 = client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload(), follow_redirects=False)
    assert r2.status_code == 303
    assert "book=taken" in r2.headers["location"]
    assert len(db.query("SELECT id FROM site_booking WHERE apartment_id = ?", (owner,))) == 1


def test_pay_mode_not_offered(owner, monkeypatch):
    _ = monkeypatch
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    oid = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (owner,))["owner_user_id"]
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_only", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    client = _client()
    r = client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload(pay_mode="direct"),
                    follow_redirects=False)
    assert r.status_code == 303
    assert db.query_one("SELECT id FROM site_booking WHERE apartment_id = ?", (owner,)) is None


def test_expire_requests(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    client = _client()
    client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload())
    row = db.query_one("SELECT id, hold_id FROM site_booking WHERE apartment_id = ?", (owner,))
    db.execute("UPDATE site_booking SET request_expires_at = ? WHERE id = ?",
               ("2000-01-01T00:00:00Z", row["id"]))
    assert booking_checkout.expire_requests() == 1
    assert db.query_one("SELECT status FROM site_booking WHERE id = ?", (row["id"],))["status"] == "expired"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (row["hold_id"],)) is None
    assert property_page.dates_available(owner, "2026-12-10", "2026-12-13")


def test_iban_rail_shows_qr_and_vs(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    oid = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (owner,))["owner_user_id"]
    eid = int(db.insert("legal_entity", {"owner_user_id": oid, "name": "E", "iban": "CZ6508000000192000145399",
                                         "created_at": db.utcnow()}))
    db.update("apartment", owner, {"legal_entity_id": eid, "stay_fee_guest_rails": "iban"})
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload())
    assert response.status_code == 200
    booking_id = db.query_one("SELECT id FROM site_booking WHERE apartment_id = ?", (owner,))["id"]
    assert str(booking_id) in response.text
    assert "6508" in response.text.replace(" ", "")


def test_no_stripe_call(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})

    def boom(*_a, **_k):
        raise RuntimeError("stripe must not run")

    monkeypatch.setattr(stripe_connect, "_api", boom)
    client = _client()
    assert client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload()).status_code == 200


def _page_query():
    return {
        "lang": "en",
        "month": "2026-12",
        "date_from": "2026-12-10",
        "date_to": "2026-12-13",
        "guests": "2",
    }


def test_real_page_offers_direct_only(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    client = _client()
    slug = _slug(owner)
    html = client.get(f"/p/{slug}", params=_page_query()).text
    assert 'name="pay_mode" value="direct"' in html
    assert "Send booking request" in html
    assert "by card" not in html.lower()
    post = {
        "date_from": "2026-12-10",
        "date_to": "2026-12-13",
        "guests": "2",
        "lang": "en",
        "terms_version": booking_site.TERMS_VERSION,
        "guest_name": "Anna Hostova",
        "guest_email": "anna@example.test",
        "terms": "1",
    }
    response = client.post(f"/p/{slug}/checkout", data=post)
    assert response.status_code == 200
    assert "Request sent" in response.text


def test_direct_request_sends_guest_mail(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    captured: list[dict] = []

    def _enqueue(**kwargs):
        captured.append(kwargs)

    from app import mail
    monkeypatch.setattr(mail, "enqueue", _enqueue)
    client = _client()
    slug = _slug(owner)
    assert client.post(f"/p/{slug}/checkout", data=_checkout_payload()).status_code == 200
    guest = [m for m in captured if m.get("kind") == "site_booking_request_guest"]
    assert len(guest) == 1
    assert guest[0]["to_email"] == "anna@example.test"
    assert "cash" in guest[0]["payload"]["text"].lower() or "hotov" in guest[0]["payload"]["text"].lower()


def test_requested_page_uses_booking_card_styles(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    client = _client()
    html = client.post(f"/p/{_slug(owner)}/checkout", data=_checkout_payload()).text
    assert "pp-bk-card" in html
    assert "ui-narrow" not in html


def test_real_page_offers_both_modes(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    db.update("apartment", owner, {"stay_fee_guest_rails": "cash"})
    oid = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (owner,))["owner_user_id"]
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_both", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    client = _client()
    html = client.get(f"/p/{_slug(owner)}", params=_page_query()).text
    assert html.count('type="radio" name="pay_mode"') == 2
