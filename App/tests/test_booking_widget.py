"""Brief 0434: property-page booking widget — no-JS availability + total.

Stripe is faked at the account level (the mirror row makes the widget live);
no network.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n, property_page
from app.main import app

OWNER = "bookhost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Book Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    aid = db.insert("apartment", {"owner_user_id": oid, "internal_name": "Book Flat",
                                  "created_at": db.utcnow()})
    property_page.page_for(aid)
    db.execute("UPDATE property_page SET nightly_price_czk = 1200 WHERE apartment_id = ?", (aid,))
    property_page.publish_page(aid, published=True)
    try:
        yield int(aid)
    finally:
        _cleanup()


def _client() -> TestClient:
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client


def _complete_account(aid: int, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    oid = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (aid,))["owner_user_id"]
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_book",
        "mode": "test", "onboarding_state": "complete",
        "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def test_widget_hidden_without_price_or_stripe(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    client = _client()
    response = client.get(f"/p/{_slug(owner)}")
    assert "Book this place" not in response.text


def test_widget_shown_when_ready(owner, monkeypatch):
    _complete_account(owner, monkeypatch)
    client = _client()
    response = client.get(f"/p/{_slug(owner)}")
    assert "Book this place" in response.text
    assert "<form" in response.text  # no-JS form POST


def test_check_computes_total(owner, monkeypatch):
    _complete_account(owner, monkeypatch)
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/book",
                           data={"date_from": "2026-12-01", "date_to": "2026-12-04"})
    assert response.status_code == 200
    assert "3 nights" in response.text
    assert "1200" in response.text
    assert "3600" in response.text  # itemized total


def test_taken_dates_refused(owner, monkeypatch):
    _complete_account(owner, monkeypatch)
    db.execute(
        "UPDATE reservation SET status = 'active' WHERE id = ?" if False else
        "INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, created_at, updated_at)"
        " VALUES (?, 'uid-book-1', '2026-12-01', '2026-12-10', 'active', ?, ?)",
        (owner, db.utcnow(), db.utcnow()),
    )
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/book",
                           data={"date_from": "2026-12-02", "date_to": "2026-12-05"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert "book=taken" in response.headers["location"]


def test_hold_blocks_and_sweeps(owner):
    assert property_page.dates_available(owner, "2026-12-01", "2026-12-05")
    property_page.create_hold(owner, "2026-12-01", "2026-12-05", minutes=15)
    assert not property_page.dates_available(owner, "2026-12-02", "2026-12-03")
    db.execute("UPDATE booking_hold SET expires_at = '2000-01-01T00:00:00Z' WHERE apartment_id = ?", (owner,))
    assert property_page.release_expired_holds() >= 1
    assert property_page.dates_available(owner, "2026-12-02", "2026-12-03")


def test_request_creates_draft_for_host(owner, monkeypatch):
    _complete_account(owner, monkeypatch)
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/request",
                           data={"date_from": "2026-12-01", "date_to": "2026-12-04",
                                 "guest_email": "guest@example.test"})
    assert response.status_code == 200
    assert "Request sent" in response.text
    rows = db.query(
        "SELECT * FROM payment_request WHERE guest_email = ? AND status = 'draft'",
        ("guest@example.test",),
    )
    assert len(rows) == 1
    assert rows[0]["amount_czk"] == 3600
