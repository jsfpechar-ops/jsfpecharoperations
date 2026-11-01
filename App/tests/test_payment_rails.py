"""Briefs 0435/0436: card rail (Payment Links) and QR rail (SPAYD page, mail).

The Stripe client is faked (no network); the SPAYD/QR helpers are the real
local code. The mail kind is real, enqueued into email_outbox.
"""
from __future__ import annotations

from datetime import date
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
    """Strict SDK-16 shape: params dict, connected account in options (0622)."""

    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []
        self.retrieved: List[str] = []
        self.active = True

    def create(self, params=None, options=None):
        assert params is not None, "payment_links.create must pass params="
        assert "stripe_account" not in params, "stripe_account belongs in options="
        assert options and options.get("stripe_account"), "connected account missing"
        self.created.append(params)
        self.options.append(options)
        return {"id": "plink_test_1", "url": "https://buy.stripe.com/test_1"}

    def retrieve(self, link_id, options=None):
        assert options and options.get("stripe_account"), "connected account missing"
        self.retrieved.append(link_id)
        return {"id": link_id, "url": "https://buy.stripe.com/test_1", "active": self.active}


@pytest.fixture
def fake_link(monkeypatch, stripe_env):
    link = _FakePaymentLink()

    class _V1:
        payment_links = link

    class _Client:
        v1 = _V1()

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
    assert fake_link.options[0] == {"stripe_account": "acct_rails"}
    assert params["restrictions"] == {"completed_sessions": {"limit": 1}}
    assert params["metadata"] == {"payment_request_id": str(rid)}
    assert params["payment_intent_data"] == {"metadata": {"payment_request_id": str(rid)}}
    assert item["price_data"]["product_data"]["name"] == f"Úklid (žádost č. {rid})"
    row = payment_request.get(rid)
    assert row["stripe_payment_link_id"] == "plink_test_1"


def test_resend_reuses_the_active_link(owner, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    first = payment_links.send(rid)
    second = payment_links.send(rid)
    assert first == second
    assert len(fake_link.created) == 1
    assert fake_link.retrieved == ["plink_test_1"]


def test_resend_creates_new_link_when_old_inactive(owner, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    fake_link.active = False
    payment_links.send(rid)
    assert len(fake_link.created) == 2


def test_send_refused_without_complete_account(owner, stripe_env):
    rid = _draft(owner, rail="card")
    assert payment_links.send(rid) is None


def test_webhook_paid_flips_request(owner, stripe_env, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    event = {
        "id": "evt_rail_1",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "paid"}},
    }
    stripe_connect.process_event(event)
    assert payment_request.get(rid)["status"] == "paid"
    # Replay: dedupe table blocks the second run.
    stripe_connect.process_event(event)
    row = db.query_one("SELECT id FROM stripe_webhook_event WHERE event_id = ?", ("evt_rail_1",))
    assert row is not None


def test_webhook_unpaid_checkout_does_not_flip(owner, stripe_env, fake_link):
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    stripe_connect.process_event({
        "id": "evt_rail_unpaid",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "unpaid"}},
    })
    assert payment_request.get(rid)["status"] == "draft"


def test_webhook_paid_from_sent_skips_draft_intermediate(owner, stripe_env, fake_link):
    """When the row is already sent, on_paid must not walk draft→sent again."""
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    payment_request.set_status(rid, "sent", today=date.fromisoformat("2026-11-01"))
    before = len(db.query(
        "SELECT id FROM audit WHERE action = 'payment_request_status' AND detail LIKE ?",
        (f"id={rid} %",),
    ))
    stripe_connect.process_event({
        "id": "evt_rail_sent",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "paid"}},
    })
    row = payment_request.get(rid)
    assert row["status"] == "paid"
    audits = db.query(
        "SELECT detail FROM audit WHERE action = 'payment_request_status' AND detail LIKE ? ORDER BY id",
        (f"id={rid} %",),
    )
    assert len(audits) == before + 1
    assert audits[-1]["detail"] == f"id={rid} sent->paid"


def test_webhook_does_not_flip_expired_request(owner, stripe_env, fake_link):
    """Until 0623, expired is terminal; a late payment must not throw or flip status."""
    _complete_account(owner)
    rid = _draft(owner, rail="card")
    payment_links.send(rid)
    payment_request.set_status(rid, "sent", today=date.fromisoformat("2026-11-01"))
    payment_request.set_status(rid, "expired", today=date.fromisoformat("2026-11-02"))
    stripe_connect.process_event({
        "id": "evt_rail_expired",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_link": "plink_test_1", "payment_status": "paid"}},
    })
    assert payment_request.get(rid)["status"] == "expired"


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
