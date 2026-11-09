"""Brief 0818: public booking page (Czech default, quote card, taken nights, checkout guard)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_site, config, db, host_i18n, property_page, stripe_connect
from app.main import app

OWNER = "pagehost"
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

    def create(self, params=None, options=None):
        assert params is not None
        assert options and options.get("stripe_account") == "acct_site"
        self.created.append(params)
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
def apartment(fake_sessions):
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Page Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Page Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 50 WHERE id = ?", (aid,))
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


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def _form(**extra) -> Dict[str, str]:
    data = {"date_from": FROM, "date_to": TO, "guests": "2", "guest_name": "Jana Nová",
            "guest_email": "jana@example.test", "terms": "1",
            "terms_version": booking_site.TERMS_VERSION, "lang": "cs"}
    data.update(extra)
    return data


def test_default_language_is_czech(apartment):
    client = TestClient(app)
    response = client.get(f"/p/{_slug(apartment)}")
    assert response.status_code == 200
    assert "Vyberte termín" in response.text
    assert '<html lang="cs">' in response.text
    assert host_i18n.LANG_COOKIE not in response.headers.get("set-cookie", "")

    response = client.get(f"/p/{_slug(apartment)}?lang=en")
    assert "Choose your dates" in response.text
    assert '<html lang="en">' in response.text

    fresh = TestClient(app)
    fresh.cookies.set(host_i18n.LANG_COOKIE, "en")
    response = fresh.get(f"/p/{_slug(apartment)}")
    assert '<html lang="en">' in response.text
    assert "Choose your dates" in response.text


def test_quote_card_shows_price_lines(apartment):
    response = TestClient(app).get(
        f"/p/{_slug(apartment)}?lang=cs&date_from={FROM}&date_to={TO}&guests=2")
    assert response.status_code == 200
    text = response.text
    assert "6&nbsp;500" in text
    assert "Úklid" in text
    assert "3 noci" in text
    assert "Zaplatit 6500 Kč kartou" in text
    assert "Městský poplatek 300 Kč" in text
    assert "Storno podmínky: Nevratná" in text
    assert 'name="terms"' in text
    assert 'name="terms_version"' in text
    assert f'action="/p/{_slug(apartment)}/checkout"' in text


def test_taken_nights_are_marked(apartment):
    now = db.utcnow()
    db.insert("reservation", {"apartment_id": apartment, "source": "manual", "uid": "page-1",
                              "date_from": "2027-03-20", "date_to": "2027-03-22",
                              "status": "active", "created_at": now, "updated_at": now})
    client = TestClient(app)
    response = client.get(f"/p/{_slug(apartment)}?month=2027-03&lang=en")
    assert 'data-state="taken"' in response.text
    response = client.get(f"/p/{_slug(apartment)}?lang=en&date_from=2027-03-20&date_to=2027-03-22")
    assert "These dates are already taken." in response.text


def test_no_quote_without_dates(apartment):
    response = TestClient(app).get(f"/p/{_slug(apartment)}?lang=en")
    assert 'name="terms"' not in response.text
    assert "Tap your arrival day." in response.text


def test_old_terms_version_is_refused(apartment, fake_sessions):
    client = TestClient(app)
    response = client.post(f"/p/{_slug(apartment)}/checkout",
                           data=_form(terms_version="1999-01-01"), follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert "book=terms" in location
    assert "lang=cs" in location
    assert not fake_sessions.created

    response = client.post(f"/p/{_slug(apartment)}/checkout", data=_form())
    assert response.status_code == 200


def test_error_redirect_keeps_dates_and_language(apartment, fake_sessions):
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout",
                                    data=_form(guest_email="not-an-email", lang="en"),
                                    follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert "book=bad_email" in location
    assert "lang=en" in location
    assert "date_from=2027-03-10" in location


def test_page_is_light(apartment):
    response = TestClient(app).get(
        f"/p/{_slug(apartment)}?lang=cs&date_from={FROM}&date_to={TO}&guests=2")
    html = response.text
    assert len(response.content) < 60000
    assert 'src="http' not in html
    assert html.count("<script") <= 3


def test_thanks_page_czech_default(apartment):
    response = TestClient(app).get(f"/p/{_slug(apartment)}/thanks")
    assert response.status_code == 200
    assert host_i18n.translate("cs", "pp.book.done") in response.text


def test_name_over_120_chars_is_refused(apartment, fake_sessions):
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout",
                                    data=_form(guest_name="A" * 121), follow_redirects=False)
    assert response.status_code == 303
    assert "book=name_too_long" in response.headers["location"]
    assert not fake_sessions.created


def test_120_char_name_passes_name_check(apartment, fake_sessions):
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout",
                                    data=_form(guest_name="A" * 120), follow_redirects=False)
    assert "book=name_too_long" not in response.headers.get("location", "")


def test_failed_checkout_keeps_name_and_email(apartment, fake_sessions):
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout",
                                    data=_form(guest_email="not-an-email"))
    assert response.status_code == 200
    assert "Jana Nová" in response.text
    assert 'value="not-an-email"' in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not fake_sessions.created


def test_unticked_terms_keeps_name(apartment, fake_sessions):
    data = _form()
    data.pop("terms")
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout", data=data)
    assert response.status_code == 200
    assert "Jana Nová" in response.text


def test_typed_name_is_escaped(apartment, fake_sessions):
    response = TestClient(app).post(f"/p/{_slug(apartment)}/checkout",
                                    data=_form(guest_name='"><b>x', guest_email="bad"))
    assert "<b>x" not in response.text
    assert "&gt;" in response.text
