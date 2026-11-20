"""Brief 1859: UBYHOST_PAYMENTS_HIDDEN hides host payments and booking-site UI."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.conftest import login_as

OWNER = "payhidden"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (oid,))
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM apartment WHERE id = ?", (a["id"],))
    db.execute("DELETE FROM login_token WHERE user_account_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def client(monkeypatch):
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Hidden Pay", username=OWNER)
    monkeypatch.setattr(config, "PAYMENTS_HIDDEN", True)
    client = TestClient(app)
    assert login_as(client, OWNER, url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield client
    finally:
        _cleanup()


def test_hidden_routes_404_when_signed_in(client):
    for path in (
        "/payments",
        "/booking-sites",
        "/payments/new",
        "/payments/consent",
        "/payments/qr/42.png",
    ):
        assert client.get(path, follow_redirects=False).status_code == 404


def test_payments_host_path_blocked_includes_qr_png(monkeypatch):
    monkeypatch.setattr(config, "PAYMENTS_HIDDEN", False)
    assert config.payments_host_path_blocked("/payments/qr/42.png") is False
    monkeypatch.setattr(config, "PAYMENTS_HIDDEN", True)
    assert config.payments_host_path_blocked("/payments/qr/42.png") is True


def test_webhook_still_200_when_hidden(client):
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 200
    assert response.text == "ignored"


def test_nav_omits_payments_and_booking_sites(client):
    html = client.get("/?lang=en").text
    assert 'href="/payments"' not in html
    assert 'href="/booking-sites"' not in html


def test_nav_omits_payments_when_hidden_off(monkeypatch):
    """Nav never shows Payments or Booking site (product dormant); flag only gates routes and row actions."""
    monkeypatch.setattr(config, "PAYMENTS_HIDDEN", False)
    db.init_db()
    _cleanup()
    auth.create_account("payshown@example.test", "Shown Pay", username="payshown")
    client = TestClient(app)
    assert login_as(client, "payshown", url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        html = client.get("/?lang=en").text
        assert 'href="/payments"' not in html
        assert 'href="/booking-sites"' not in html
    finally:
        _cleanup()


def test_guide_still_lists_payments_section(client):
    html = client.get("/guide?lang=en").text
    assert "Payments" in html


def test_mail_job_skips_expire_requests_when_hidden(monkeypatch):
    from app import scheduler

    monkeypatch.setattr(config, "PAYMENTS_HIDDEN", True)
    with patch("app.booking_checkout.expire_requests") as expire:
        scheduler._job_mail()
    expire.assert_not_called()

