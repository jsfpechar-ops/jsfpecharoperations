"""Brief 0900: public guest terms page /terms/booking and the checkout link to it."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_site, config, db, property_page
from app.main import app

OWNER = "termshost"
FROM, TO = "2027-03-10", "2027-03-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture(autouse=True)
def _schema():
    db.init_db()


@pytest.fixture
def published(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Terms Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Terms Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 50 WHERE id = ?", (aid,))
    property_page.publish_page(aid, published=True)
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_terms", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    try:
        yield aid
    finally:
        _cleanup()


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def test_terms_default_is_czech():
    response = TestClient(app).get("/terms/booking")
    assert response.status_code == 200
    assert "Podmínky rezervace" in response.text
    assert 'lang="cs"' in response.text


def test_terms_english_sets_no_cookie():
    response = TestClient(app).get("/terms/booking?lang=en")
    assert response.status_code == 200
    assert "Booking terms" in response.text
    assert 'lang="en"' in response.text


@pytest.mark.parametrize("lang, names", [
    ("cs", ("Nevratná", "Flexibilní", "Střední")),
    ("en", ("Non-refundable", "Flexible", "Moderate")),
])
def test_terms_name_all_three_policies(lang, names):
    response = TestClient(app).get(f"/terms/booking?lang={lang}")
    assert response.status_code == 200
    for name in names:
        assert name in response.text


def test_checkout_page_links_to_terms(published):
    response = TestClient(app).get(
        f"/p/{_slug(published)}?lang=cs&date_from={FROM}&date_to={TO}&guests=2")
    assert response.status_code == 200
    assert 'href="/terms/booking?lang=cs"' in response.text
