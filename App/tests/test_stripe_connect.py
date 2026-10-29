"""Brief 0426: Stripe Connect module (config gating, account mirror, webhooks)."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest

from app import config, db, payment_request, stripe_connect

OWNER = "stripetest"
TODAY = date(2026, 10, 28)


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM settings WHERE key LIKE 'stripe_event:%'")
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 0)
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "Stripe", "created_at": db.utcnow()})
    db.insert("legal_entity", {"name": "Testovaci s.r.o.", "seat": "Praha",
                               "contact_email": "host@example.com",
                               "owner_user_id": oid, "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


def _acct(**kw):
    base = {"id": "acct_test123", "charges_enabled": False, "payouts_enabled": False,
            "details_submitted": False,
            "requirements": {"currently_due": ["external_account"], "past_due": [],
                             "disabled_reason": None}}
    base.update(kw)
    return SimpleNamespace(**base)


def test_disabled_when_mode_off(owner, monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "off")
    assert not config.stripe_enabled()
    with pytest.raises(stripe_connect.StripeDisabledError):
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")


def test_ensure_account_creates_mirror_row(owner):
    created = _acct()
    with mock.patch.object(stripe_connect, "_client") as client:
        client.return_value.v2.core.accounts.create.return_value = created
        row = stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
    assert row["stripe_account_id"] == "acct_test123"
    assert row["onboarding_state"] == "pending"
    assert row["mode"] == "test"
    client.return_value.v2.core.accounts.create.assert_called_once()
    kwargs = client.return_value.v2.core.accounts.create.call_args.kwargs
    resp = kwargs["defaults"]["responsibilities"]
    assert resp["fees_collector"] == "stripe"
    assert resp["losses_collector"] == "stripe"
    assert kwargs["dashboard"] == "express"
    assert kwargs["identity"]["country"] == "CZ"
    assert kwargs["configuration"]["merchant"]["capabilities"]["card_payments"]["requested"] is True
    # Prefill sends name/email/url only — never sensitive personal data.
    bd = kwargs["identity"]["business_details"]
    assert set(bd) == {"registered_name", "url", "product_description"}
    assert "dob" not in str(kwargs).lower() and "address" not in str(kwargs).lower()


def test_ensure_account_is_idempotent(owner):
    with mock.patch.object(stripe_connect, "_client") as client:
        client.return_value.v2.core.accounts.create.return_value = _acct()
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
    assert client.return_value.v2.core.accounts.create.call_count == 1


def test_sync_account_maps_states(owner):
    with mock.patch.object(stripe_connect, "_client") as client:
        client.return_value.v2.core.accounts.create.return_value = _acct()
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
        client.return_value.accounts.retrieve.return_value = _acct(
            charges_enabled=True, payouts_enabled=True,
            requirements={"currently_due": [], "past_due": [], "disabled_reason": None},
        )
        row = stripe_connect.sync_account(owner)
    assert row["onboarding_state"] == "complete"
    assert row["charges_enabled"] == 1
    reqs = json.loads(row["requirements_json"])
    assert reqs["currently_due"] == []


def test_sync_account_rejected(owner):
    with mock.patch.object(stripe_connect, "_client") as client:
        client.return_value.v2.core.accounts.create.return_value = _acct()
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
        client.return_value.accounts.retrieve.return_value = _acct(
            requirements={"currently_due": [], "past_due": [],
                          "disabled_reason": "rejected.fraud"},
        )
        row = stripe_connect.sync_account(owner)
    assert row["onboarding_state"] == "rejected"


def _event(evt_id, etype, obj):
    return SimpleNamespace(id=evt_id, type=etype, data=SimpleNamespace(object=obj))


def test_webhook_account_updated(owner):
    with mock.patch.object(stripe_connect, "_client") as client:
        client.return_value.v2.core.accounts.create.return_value = _acct()
        stripe_connect.ensure_account(owner, base_url="https://ubyhost.cz")
        event = _event("evt_1", "account.updated", dict(_acct(
            charges_enabled=True, payouts_enabled=True,
            requirements={"currently_due": [], "past_due": [], "disabled_reason": None},
        ).__dict__))
        stripe_connect.handle_event(event)
        row = stripe_connect.account_row(owner)
    assert row["onboarding_state"] == "complete"


def test_webhook_marks_request_paid_once(owner):
    rid = payment_request.create(owner, reason="repair", amount_czk=1500, rail="card",
                                  expires_at="2026-11-04", today=TODAY)
    db.execute("UPDATE payment_request SET stripe_payment_intent_id = ?, status = 'sent'"
               " WHERE id = ?", ("pi_test9", rid))
    event = _event("evt_2", "payment_intent.succeeded", {"id": "pi_test9"})
    stripe_connect.handle_event(event)
    stripe_connect.handle_event(event)  # duplicate delivery: handled once
    assert payment_request.get(rid)["status"] == "paid"


def test_webhook_unknown_type_is_ignored(owner):
    stripe_connect.handle_event(_event("evt_3", "invoice.created", {"id": "in_x"}))
    row = payment_request.get(999)
    assert row is None  # no crash, nothing processed


def test_verify_and_parse_roundtrip(owner):
    # A real signature made with the test secret verifies; a tampered one fails.
    import stripe as stripe_sdk

    payload = json.dumps({"id": "evt_4", "object": "event"}).encode()
    import time, hmac, hashlib

    ts = int(time.time())
    signed = f"{ts}." + payload.decode()
    sig = hmac.new(
        config.STRIPE_WEBHOOK_SECRET.encode(), signed.encode(), hashlib.sha256
    ).hexdigest()
    header = f"t={ts},v1={sig}"
    event = stripe_connect.verify_and_parse(payload, header)
    assert event["id"] == "evt_4"
    with pytest.raises(Exception):
        stripe_connect.verify_and_parse(payload, "t=1,v1=bad")
