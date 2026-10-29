"""Brief 0429: payments dashboard — connect state, request form, draft rows.

No network: the Stripe module is only read through the mirror, never called.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, payment_request
from app.main import app
from tests.conftest import login_as

OWNER = "paydashboard"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Pay Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _set_state(oid: int, state: str):
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    if state == "none":
        return
    now = db.utcnow()
    db.insert(
        "stripe_account",
        {
            "owner_user_id": oid,
            "stripe_account_id": f"acct_{state}",
            "mode": config.STRIPE_MODE,
            "onboarding_state": state,
            "charges_enabled": 1 if state == "complete" else 0,
            "payouts_enabled": 1 if state == "complete" else 0,
            "created_at": now,
            "updated_at": now,
        },
    )


# --- connect card ------------------------------------------------------------


def test_off_mode_shows_off_copy(client, owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    response = client.get("/payments")
    assert response.status_code == 200
    assert "Card payments are off" in response.text


def test_every_state_renders_its_copy(client, owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    copy_for = {
        "none": "Connect your Stripe account",
        "pending": "Stripe is preparing your account",
        "action_required": "Stripe needs one more thing",
        "complete": "Payments are on",
        "rejected": "Stripe could not approve",
        "disabled": "Stripe has paused",
    }
    for state, copy in copy_for.items():
        _set_state(owner, state)
        response = client.get("/payments")
        assert response.status_code == 200
        assert copy in response.text, state


def test_button_only_in_pending_or_action_required(client, owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    for state, has_button in (
        ("none", True),
        ("pending", True),
        ("action_required", True),
        ("complete", False),
        ("rejected", False),
        ("disabled", False),
    ):
        _set_state(owner, state)
        response = client.get("/payments")
        assert ("Open Stripe" in response.text) == has_button, state


# --- request form ------------------------------------------------------------


def test_draft_created_from_valid_post(client, owner):
    before = len(payment_request.for_owner(owner))
    response = client.post(
        "/payments/requests/new",
        data={"reason": "repair", "amount_czk": "1500"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = payment_request.for_owner(owner)
    assert len(rows) == before + 1
    assert rows[0]["reason"] == "repair"
    assert rows[0]["amount_czk"] == 1500
    assert rows[0]["status"] == "draft"
    assert "msg=" in response.headers["location"]


def test_invalid_reason_refused(client, owner):
    response = client.post(
        "/payments/requests/new",
        data={"reason": "bribe", "amount_czk": "100"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert payment_request.for_owner(owner) == []


def test_bad_amount_refused(client, owner):
    response = client.post(
        "/payments/requests/new",
        data={"reason": "cleaning", "amount_czk": "12.50"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "err=" in response.headers["location"]


def test_foreign_stay_refused(client, owner):
    response = client.post(
        "/payments/requests/new",
        data={"reason": "cleaning", "amount_czk": "100", "reservation_id": "999999"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "err=" in response.headers["location"]


# --- list ----------------------------------------------------------------------


def test_list_shows_drafts_and_empty_state(client, owner):
    response = client.get("/payments")
    assert "No payment requests yet" in response.text
    payment_request.create(
        owner, reason="damage", amount_czk=2500, rail="card", expires_at="2026-11-27"
    )
    response = client.get("/payments")
    assert "No payment requests yet" not in response.text
    assert "2,500" in response.text or "2500" in response.text


def test_popovers_present_without_js(client, owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    _set_state(owner, "complete")
    response = client.get("/payments")
    assert "data-help-tip" in response.text
    assert "UbyHost never touches the money" in response.text


def test_anonymous_redirected_to_login(owner):
    anonymous = TestClient(app)
    response = anonymous.get("/payments", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_connect_button_is_a_plain_link(client, monkeypatch):
    """0442: the Open Stripe button is an anchor to the GET route (plain link
    navigation — the path that works with the PWA layer), never a form POST
    (which hangs on the skeleton loader)."""
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_x")
    response = client.get("/payments")
    html = response.text
    assert 'href="/payments/connect/start"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert '<form method="post" action="/payments/connect/start"' not in html
