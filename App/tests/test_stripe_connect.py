"""Brief 0428: Stripe Connect module, onboarding routes and webhook.

The Stripe client is faked (no network, per the test rules); only webhook
signature verification uses the real SDK, which is a pure local HMAC.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, stripe_connect
from app.main import app
from tests.conftest import login_as

OWNER = "stripeconnect"
SECRET = "whsec_test_secret"


# --- fixtures ---------------------------------------------------------------


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_webhook_event", ())
    db.execute("DELETE FROM lock_api_usage WHERE provider = 'stripe'", ())
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Connect Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"name": "Ubytovani s.r.o.", "seat": "Praha 1",
                               "owner_user_id": oid, "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)


class _FakeAccount:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.retrieved: List[str] = []
        self.state = _account_dict(charges=False, payouts=False, due=[])

    def create(self, **params):
        self.created.append(params)
        self.state["id"] = "acct_test_123"
        return dict(self.state)

    def retrieve(self, account_id, **kwargs):
        self.retrieved.append(account_id)
        return dict(self.state)


class _FakeAccountLink:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []

    def create(self, **params):
        self.created.append(params)
        return {"url": "https://connect.stripe.com/setup/e/test_123"}


def _account_dict(*, charges: bool, payouts: bool, due: list, errors: list = None,
                  disabled: bool = False) -> Dict[str, Any]:
    return {
        "id": "acct_test_123",
        "disabled": disabled,
        "charges_enabled": charges,
        "payouts_enabled": payouts,
        "requirements": {
            "currently_due": due,
            "past_due": [],
            "eventually_due": [],
            "disabled_reason": None,
            "errors": errors or [],
            "alternative": {"booleans": ["individual.verification.document"]},
        },
    }


@pytest.fixture
def fake_stripe(monkeypatch, owner, stripe_env):
    account, link = _FakeAccount(), _FakeAccountLink()
    monkeypatch.setattr(stripe_connect.stripe, "Account", account)
    monkeypatch.setattr(stripe_connect.stripe, "AccountLink", link)
    return SimpleNamespace(account=account, link=link)


# --- account creation ------------------------------------------------------


def test_off_by_default(monkeypatch, owner):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    assert not stripe_connect.enabled()


def test_create_uses_controller_api_not_deprecated_type(fake_stripe):
    stripe_connect.create_or_get_account(_owner_id())
    params = fake_stripe.account.created[0]
    assert "type" not in params
    assert params["controller"] == {
        "fees": {"payer": "account"},
        "losses": {"payments": "stripe"},
        "requirement_collection": "stripe",
        "stripe_dashboard": {"type": "express"},
    }
    assert params["country"] == "CZ"
    profile = params["business_profile"]
    assert profile["name"] == "Ubytovani s.r.o."
    assert profile["url"]
    assert "accommodation" in profile["product_description"]


def test_create_is_idempotent_per_owner(fake_stripe):
    stripe_connect.create_or_get_account(_owner_id())
    row = stripe_connect.create_or_get_account(_owner_id())
    assert len(fake_stripe.account.created) == 1
    assert row["stripe_account_id"] == "acct_test_123"
    assert row["mode"] == "test"
    assert row["onboarding_state"] == "pending"


def test_create_without_legal_entity_raises(owner, stripe_env, monkeypatch):
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (_owner_id(),))
    with pytest.raises(ValueError):
        stripe_connect.create_or_get_account(_owner_id())


def test_monthly_cap_blocks_and_counts(fake_stripe, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 1)
    assert stripe_connect.calls_this_month() == 0
    stripe_connect.create_or_get_account(_owner_id())
    assert stripe_connect.calls_this_month() == 1
    with pytest.raises(stripe_connect.StripeOff):
        stripe_connect.onboarding_link(_owner_id(), base_url="https://app.example")


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]


# --- state mirroring -------------------------------------------------------


def test_mirror_states(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    for state, account in (
        ("complete", _account_dict(charges=True, payouts=True, due=[])),
        ("action_required", _account_dict(charges=False, payouts=False, due=["individual.verification.document"])),
        ("rejected", _account_dict(charges=False, payouts=False, due=[], errors=[{"code": "verification_failed_rejected"}])),
        ("disabled", _account_dict(charges=True, payouts=True, due=[], disabled=True)),
    ):
        fake_stripe.account.state = account
        stripe_connect._mirror(oid, account)
        assert stripe_connect.account_for_owner(oid)["onboarding_state"] == state


def test_mirror_stores_requirement_names_only(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    account = _account_dict(charges=False, payouts=False, due=["individual.id_number"])
    stripe_connect._mirror(oid, account)
    row = stripe_connect.account_for_owner(oid)
    stored = json.loads(row["requirements_json"])
    assert set(stored) == {"currently_due"}
    assert stored["currently_due"] == ["individual.id_number"]


def test_mirror_audits_transitions(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    before = _audit_count("stripe_account_state")
    fake_stripe.account.state = _account_dict(charges=True, payouts=True, due=[])
    stripe_connect._mirror(oid, fake_stripe.account.state)
    assert _audit_count("stripe_account_state") == before + 1
    # A second mirror of the same state changes nothing.
    stripe_connect._mirror(oid, fake_stripe.account.state)
    assert _audit_count("stripe_account_state") == before + 1


def _audit_count(action: str) -> int:
    return len(db.query("SELECT id FROM audit WHERE action = ?", (action,)))


# --- onboarding ------------------------------------------------------------


def test_onboarding_link_params(fake_stripe):
    url = stripe_connect.onboarding_link(_owner_id(), base_url="https://app.example")
    assert url == "https://connect.stripe.com/setup/e/test_123"
    params = fake_stripe.link.created[0]
    assert params["type"] == "account_onboarding"
    assert params["refresh_url"] == "https://app.example/payments/connect/start"
    assert params["return_url"] == "https://app.example/payments/connect/return"
    assert params["account"] == "acct_test_123"


def test_handle_return_retrieves_and_mirrors(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    fake_stripe.account.state = _account_dict(charges=True, payouts=True, due=[])
    state = stripe_connect.handle_return(oid)
    assert fake_stripe.account.retrieved == ["acct_test_123"]
    assert state == "complete"


# --- webhook ----------------------------------------------------------------


def _signed_payload(event: Dict[str, Any], secret: str = SECRET) -> Dict[str, bytes]:
    raw = json.dumps(event).encode()
    stamp = str(int(time.time()))
    signed = f"{stamp}.".encode() + raw
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return {"content": raw, "headers": {"Stripe-Signature": f"t={stamp},v1={sig}"}}


def _account_updated_event(account: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": "evt_test_001",
        "type": "account.updated",
        "data": {"object": account},
    }


def test_verify_event_accepts_a_valid_signature(fake_stripe):
    payload = _signed_payload(_account_updated_event(_account_dict(charges=True, payouts=True, due=[])))
    event = stripe_connect.verify_event(payload["content"], payload["headers"]["Stripe-Signature"])
    assert event["id"] == "evt_test_001"


def test_verify_event_rejects_a_bad_signature(fake_stripe):
    payload = _signed_payload(_account_updated_event(_account_dict(charges=True, payouts=True, due=[])))
    with pytest.raises(ValueError):
        stripe_connect.verify_event(payload["content"], "t=1,v1=deadbeef")


def test_process_event_mirrors_account_updated(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    before = _audit_count("stripe_account_state")
    account = _account_dict(charges=True, payouts=True, due=[])
    stripe_connect.process_event(_account_updated_event(account))
    assert stripe_connect.account_for_owner(oid)["onboarding_state"] == "complete"
    assert _audit_count("stripe_account_state") == before + 1


def test_process_event_dedupes_by_event_id(fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    event = _account_updated_event(_account_dict(charges=True, payouts=True, due=[]))
    stripe_connect.process_event(event)
    before = _audit_count("stripe_account_state")
    stripe_connect.process_event(event)  # Stripe retried the same event id
    assert _audit_count("stripe_account_state") == before
    rows = db.query("SELECT id FROM stripe_webhook_event WHERE event_id = ?", ("evt_test_001",))
    assert len(rows) == 1


def test_process_event_records_unknown_types(fake_stripe):
    stripe_connect.process_event({"id": "evt_test_002", "type": "checkout.session.completed", "data": {}})
    rows = db.query("SELECT * FROM stripe_webhook_event WHERE event_id = ?", ("evt_test_002",))
    assert rows and rows[0]["event_type"] == "checkout.session.completed"


# --- routes ------------------------------------------------------------------


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def test_routes_hidden_when_mode_off(client, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    assert client.get("/payments/connect/start", follow_redirects=False).status_code == 404
    assert client.get("/payments/connect/return", follow_redirects=False).status_code == 404


def test_start_requires_signin(owner, stripe_env):
    anonymous = TestClient(app)
    response = anonymous.get("/payments/connect/start", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_start_redirects_to_single_use_link(client, owner, stripe_env, fake_stripe):
    response = client.post("/payments/connect/start", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("https://connect.stripe.com/")
    # The link is only served to a signed-in session; no mail carries it.
    assert db.query_one(
        "SELECT id FROM email_outbox WHERE payload LIKE ?", ("%connect.stripe.com%",)
    ) is None


def test_return_mirrors_state(client, owner, stripe_env, fake_stripe):
    client.post("/payments/connect/start", follow_redirects=False)
    fake_stripe.account.state = _account_dict(charges=True, payouts=True, due=[])
    response = client.get("/payments/connect/return", follow_redirects=False)
    assert response.status_code == 303
    assert stripe_connect.account_for_owner(_owner_id())["onboarding_state"] == "complete"


def test_webhook_route_off_mode_is_logged_and_ignored(client, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "")
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 200
    assert db.query_one("SELECT id FROM stripe_webhook_event") is None


def test_webhook_route_without_secret_fails_loudly(client, owner, monkeypatch, stripe_env):
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "")
    response = client.post("/webhooks/stripe", content=b"{}")
    assert response.status_code == 500


def test_webhook_route_rejects_bad_signature(client, owner, stripe_env):
    response = client.post("/webhooks/stripe", content=b"{}",
                           headers={"Stripe-Signature": "t=1,v1=bad"})
    assert response.status_code == 400


def test_webhook_route_processes_account_updated(client, owner, stripe_env, fake_stripe):
    oid = _owner_id()
    stripe_connect.create_or_get_account(oid)
    event = _account_updated_event(_account_dict(charges=True, payouts=True, due=[]))
    payload = _signed_payload(event)
    response = client.post("/webhooks/stripe", content=payload["content"],
                           headers=payload["headers"])
    assert response.status_code == 200
    assert stripe_connect.account_for_owner(oid)["onboarding_state"] == "complete"
    # A replay gets the same fast 2xx and runs nothing twice.
    replay = client.post("/webhooks/stripe", content=payload["content"],
                         headers=payload["headers"])
    assert replay.status_code == 200
    assert len(db.query("SELECT id FROM stripe_webhook_event")) == 1
