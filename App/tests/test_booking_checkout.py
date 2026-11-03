"""Brief 0815: booking site checkout (hold, pending booking, Stripe session)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_site, config, db, host_i18n, property_page, stripe_connect
from app.main import app

OWNER = "checkouthost"
FROM, TO = "2027-03-10", "2027-03-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeSessions:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []
        self.fail = False

    def create(self, params=None, options=None):
        assert params is not None
        assert "stripe_account" not in params, "stripe_account belongs in options="
        assert options and options.get("stripe_account") == "acct_site"
        if self.fail:
            raise RuntimeError("stripe down")
        self.created.append(params)
        self.options.append(options)
        return {"id": f"cs_test_{len(self.created)}", "url": "https://checkout.stripe.com/c/pay/cs_test"}


@pytest.fixture
def fake_sessions(monkeypatch):
    sessions = _FakeSessions()

    class _Checkout:
        pass

    _Checkout.sessions = sessions

    class _V1:
        checkout = _Checkout

    class _Client:
        v1 = _V1()

    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return sessions


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Checkout Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Site Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    property_page.publish_page(aid, published=True)
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_site", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
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


def _form(**extra) -> Dict[str, str]:
    data = {"date_from": FROM, "date_to": TO, "guests": "2", "guest_name": "Jana Nová",
            "guest_email": "jana@example.test", "terms": "1", "lang": "cs"}
    data.update(extra)
    return data


def test_book_shows_price_lines(apartment, fake_sessions):
    response = _client().post(f"/p/{_slug(apartment)}/book",
                              data={"date_from": FROM, "date_to": TO, "guests": "2"})
    assert response.status_code == 200
    assert "6500" in response.text and "Cleaning fee" in response.text
    assert f'action="/p/{_slug(apartment)}/checkout"' in response.text


def test_checkout_creates_hold_booking_and_session(apartment, fake_sessions):
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form())
    assert response.status_code == 200
    assert "https://checkout.stripe.com/c/pay/cs_test" in response.text
    assert response.headers["Cache-Control"] == "no-store"
    params = fake_sessions.created[0]
    assert params["mode"] == "payment" and params["locale"] == "cs"
    assert params["line_items"][0]["price_data"]["unit_amount"] == 650000
    assert params["line_items"][0]["price_data"]["product_data"]["name"].startswith("Ubytování Site Flat")
    booking = booking_site.by_session("cs_test_1")
    assert booking["status"] == "pending" and booking["total_czk"] == 6500
    assert params["metadata"] == {"site_booking_id": str(booking["id"])}
    assert not property_page.dates_available(apartment, FROM, TO)


def test_second_guest_cannot_take_held_dates(apartment, fake_sessions):
    client = _client()
    client.post(f"/p/{_slug(apartment)}/checkout", data=_form())
    response = client.post(f"/p/{_slug(apartment)}/checkout", data=_form(), follow_redirects=False)
    assert response.status_code == 303
    assert "book=taken" in response.headers["location"]
    assert len(fake_sessions.created) == 1


@pytest.mark.parametrize("extra,code", [
    ({"terms": ""}, "terms"),
    ({"guest_email": "nope"}, "bad_email"),
    ({"guest_name": "J"}, "bad_name"),
    ({"guests": "0"}, "guests"),
])
def test_checkout_validation(apartment, fake_sessions, extra, code):
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form(**extra),
                              follow_redirects=False)
    assert response.status_code == 303
    assert f"book={code}" in response.headers["location"]
    assert fake_sessions.created == []


def test_stripe_failure_frees_the_dates(apartment, fake_sessions):
    fake_sessions.fail = True
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form(),
                              follow_redirects=False)
    assert "book=unavailable" in response.headers["location"]
    assert property_page.dates_available(apartment, FROM, TO)
    row = db.query_one("SELECT status FROM site_booking WHERE apartment_id = ?", (apartment,))
    assert row["status"] == "expired"


def test_error_is_shown_on_the_page(apartment, fake_sessions):
    response = _client().get(f"/p/{_slug(apartment)}?book=taken")
    assert "These dates are already taken." in response.text
    response = _client().get(f"/p/{_slug(apartment)}?book=<script>")
    assert "<script>" not in response.text


def test_thanks_page(apartment):
    response = _client().get(f"/p/{_slug(apartment)}/thanks")
    assert response.status_code == 200 and "Thank you" in response.text


def test_hold_dates_rejects_overlap(apartment):
    assert booking_checkout.hold_dates(apartment, FROM, TO) is not None
    assert booking_checkout.hold_dates(apartment, "2027-03-12", "2027-03-14") is None
    assert booking_checkout.hold_dates(apartment, TO, "2027-03-15") is not None
