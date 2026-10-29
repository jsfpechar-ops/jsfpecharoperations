"""Briefs 0435/0436: card rail (Payment Links) and QR rail (SPAYD page, mail).

The Stripe client is faked (no network); the SPAYD/QR helpers are the real
local code. The mail kind is real, enqueued into email_outbox.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, payment_links, payment_request, stripe_connect
from app.main import app
from tests.conftest import login_as

OWNER = "railshost"
SECRET_IBAN = "CZ6508000000001932000283"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_webhook_event", ())
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Rails Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Rails s.r.o.",
                               "iban": SECRET_IBAN,
                               "contact_email": f"{OWNER}@example.test",
                               "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


class _FakePaymentLink:
    """Strict SDK-16 shape: params dict only."""

    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []

    def create(self, params=None, options=None):
        assert params is not None, "payment_links.create must pass params="
        self.created.append(params)
        return {"id": "plink_test_1", "url": "https://buy.stripe.com/test_1"}


@pytest.fixture
def fake_link(monkeypatch, stripe_env):
    link = _FakePaymentLink()

    class _Client:
        payment_links = link

    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return link


def _complete_account(oid: int):
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    now = db.utcnow()
    db.insert(
        "stripe_account",
        {
            "owner_user_id": oid,
            "stripe_account_id": "acct_rails",
            "mode": config.STRIPE_MODE,
            "onboarding_state": "complete",
            "charges_enabled": 1,
            "payouts_enabled": 1,
            "created_at": now,
            "updated_at": now,
        },
    )


def _draft(oid: int, *, rail: str, email: str = "guest@example.test") -> int:
    return payment_request.create(
        oid, reason="cleaning", amount_czk=800, rail=rail,
        expires_at="2026-11-27", guest_email=email,
    )


# --- card rail (0435) ----------------------------------------------------------


def test_send_creates_payment_link_on_connected_account(owner, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    url = payment_links.send(rid)
    assert url == "https://buy.stripe.com/test_1"
    params = fake_link.created[0]
    item = params["line_items"][0]
    assert item["price_data"]["currency"] == "czk"
    assert item["price_data"]["unit_amount"] == 80000
    assert params["stripe_account"] == "acct_rails"
    row = payment_request.get(rid)
    assert row["stripe_payment_link_id"] == "plink_test_1"


def test_send_refused_without_complete_account(owner, stripe_env):
    rid = _draft(owner, rail="card")
    assert payment_links.send(rid) is None


def test_webhook_paid_flips_request(owner, stripe_env, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    event = {
        "id": "evt_rail_1",
        "type": "payment_link.paid",
        "data": {"object": {"payment_link": "plink_test_1"}},
    }
    stripe_connect.process_event(event)
    assert payment_request.get(rid)["status"] == "paid"
    # Replay: dedupe table blocks the second run.
    stripe_connect.process_event(event)
    row = db.query_one("SELECT id FROM stripe_webhook_event WHERE event_id = ?", ("evt_rail_1",))
    assert row is not None


def test_route_send_mails_the_link_once(owner, client, stripe_env, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    response = client.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    assert response.status_code == 303
    rows = db.query(
        "SELECT * FROM email_outbox WHERE idempotency_key LIKE ?",
        (f"payment_request:{rid}:sent%",),
    )
    assert len(rows) == 1
    assert "buy.stripe.com" in rows[0]["payload"]
    assert payment_request.get(rid)["status"] == "sent"
    client.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    rows = db.query(
        "SELECT * FROM email_outbox WHERE idempotency_key LIKE ?",
        (f"payment_request:{rid}:sent%",),
    )
    assert len(rows) == 2  # the resend is a new mail, still one link


def test_route_send_refused_without_email(owner, client, stripe_env):
    rid = _draft(owner, rail="card", email="")
    response = client.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert payment_request.get(rid)["status"] == "draft"


def test_route_send_refused_when_not_ready(owner, client, stripe_env):
    rid = _draft(owner, rail="card")
    response = client.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    assert "err=" in response.headers["location"]


# --- QR rail (0436) --------------------------------------------------------------


def test_qr_request_gets_variable_symbol(owner):
    rid = _draft(owner, rail="qr")
    row = payment_request.get(rid)
    assert row["variable_symbol"] == f"{rid:010d}"


def test_qr_page_renders_disclosure_and_png(owner, client):
    rid = _draft(owner, rail="qr")
    response = client.get(f"/payments/qr/{rid}")
    assert response.status_code == 200
    assert "no card protection" in response.text
    png = client.get(f"/payments/qr/{rid}.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"


def test_qr_page_refused_for_card_rail(owner, client):
    rid = _draft(owner, rail="card")
    response = client.get(f"/payments/qr/{rid}", follow_redirects=False)
    assert response.status_code == 303


def test_qr_send_mails_page_link(owner, client):
    rid = _draft(owner, rail="qr")
    response = client.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    assert response.status_code == 303
    rows = db.query(
        "SELECT * FROM email_outbox WHERE idempotency_key LIKE ?",
        (f"payment_request:{rid}:sent%",),
    )
    assert len(rows) == 1
    assert f"/payments/qr/{rid}" in rows[0]["payload"]
    assert payment_request.get(rid)["status"] == "sent"


def test_foreign_owner_cannot_send(owner, client, stripe_env):
    rid = _draft(owner, rail="card")
    other = TestClient(app)
    response = other.post(f"/payments/requests/{rid}/send", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]
