"""Activation trial boundaries and retirement of founder offers for new orders."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from app import billing, billing_order, billing_trial, config, db, signup


@pytest.fixture
def owner(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    user_id = db.insert(
        "user_account",
        {"username": f"self-service-{secrets.token_hex(5)}", "password_hash": "",
         "email": f"{secrets.token_hex(5)}@example.test", "created_at": db.utcnow(),
         "signup_at": db.utcnow(), "signup_verify_nonce": "self-service-test", "active": 0},
    )
    yield user_id
    for table in ("email_outbox", "founder_slot", "billing_account", "audit"):
        db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _pending(owner):
    return db.query_one("SELECT * FROM user_account WHERE id = ?", (owner,))


def _order():
    return {
        "plan": "standard", "billing_interval": "year", "addon_ttlock": False,
        "addon_whitelabel": False, "buyer_name": "Test", "buyer_street": "Test 1",
        "buyer_city": "Praha", "buyer_zip": "11000", "buyer_ico": "",
        "buyer_dic": "", "buyer_email": "billing@example.test",
    }


def test_calendar_trial_has_thirty_days_across_prague_dst(monkeypatch):
    monkeypatch.setattr(config, "TIMEZONE", "Europe/Prague")
    first, last = billing_trial.activation_dates("2026-10-24T23:30:00+00:00")
    assert first == date(2026, 10, 25)
    assert last == date(2026, 11, 23)
    assert (last - first).days + 1 == 30


def test_activation_retry_cannot_restart_trial(owner):
    account = _pending(owner)
    assert signup.activate(account)
    before = billing.account(owner)
    assert before["status"] == "trialing"
    assert not signup.activate(account)
    assert not billing_trial.start(owner, today=date.today() + timedelta(days=10))
    assert billing.account(owner)["trial_started_at"] == before["trial_started_at"]
    assert billing.account(owner)["trial_ends_at"] == before["trial_ends_at"]


def test_failure_to_create_trial_rolls_back_activation(owner, monkeypatch):
    account = _pending(owner)

    def fail(_stamp):
        raise RuntimeError("trial provisioning failed")

    with monkeypatch.context() as patch:
        patch.setattr(billing_trial, "activation_dates", fail)
        with pytest.raises(RuntimeError, match="trial provisioning failed"):
            signup.activate(account)
    assert _pending(owner)["email_verified_at"] is None
    assert _pending(owner)["active"] == 0
    assert billing.account(owner) is None
    assert signup.activate(account)


def test_existing_trial_dates_are_never_reset(owner):
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = 'trialing', trial_started_at = ?, trial_ends_at = ? "
        "WHERE owner_user_id = ?", ("2026-10-01", "2026-10-31", owner),
    )
    assert signup.activate(_pending(owner))
    assert billing.account(owner)["trial_started_at"] == "2026-10-01"
    assert billing.account(owner)["trial_ends_at"] == "2026-10-31"


def test_legacy_verified_host_stays_free(owner):
    db.execute(
        "UPDATE user_account SET active = 1, email_verified_at = ?, signup_at = NULL, "
        "signup_verify_nonce = NULL WHERE id = ?", (db.utcnow(), owner),
    )
    assert not billing_trial.start(owner)
    billing_trial.run()
    assert billing.account(owner) is None
    assert billing.entitlements(owner) == billing.UNBILLED


def test_new_annual_order_never_claims_a_founder_slot(owner, monkeypatch):
    assert signup.activate(_pending(owner))
    monkeypatch.setattr(config, "FOUNDER_SLOTS", 10000)

    def forbidden(_owner):
        raise AssertionError("new orders must not claim founder slots")

    monkeypatch.setattr(billing, "claim_founder_slot", forbidden)
    values = _order()
    assert not billing_order.founder_offer(owner)
    assert billing_order.quote(owner, values)["base"] == billing.BASE["year"][0]
    result = billing_order.place(owner, values)
    assert result["invoice_id"] is None
    assert billing.account(owner)["founder"] == 0
    assert db.query_one("SELECT 1 FROM founder_slot WHERE owner_user_id = ?", (owner,)) is None


def test_existing_founder_agreement_is_preserved(owner):
    assert signup.activate(_pending(owner))
    db.execute("UPDATE billing_account SET founder = 1 WHERE owner_user_id = ?", (owner,))
    values = _order()
    assert billing_order.founder_offer(owner)
    assert billing_order.quote(owner, values)["base"] == billing.FOUNDER_YEAR
    billing_order.place(owner, values)
    assert billing.account(owner)["founder"] == 1


def test_trial_boundary_without_order_pauses_without_invoice(owner):
    assert signup.activate(_pending(owner))
    last = date.fromisoformat(billing.account(owner)["trial_ends_at"])
    billing_trial.run(last)
    assert billing.account(owner)["status"] == "trialing"
    billing_trial.run(last + timedelta(days=1))
    assert billing.account(owner)["status"] == "paused"
    assert billing.entitlements(owner).ubyport_submit
    assert db.query_one(
        "SELECT 1 FROM platform_invoice WHERE owner_user_id = ?", (owner,),
    ) is None


def test_cancellation_state_is_not_restarted_by_trial_recovery(owner):
    assert signup.activate(_pending(owner))
    db.execute(
        "UPDATE billing_account SET status = 'canceling', plan = 'standard', "
        "billing_interval = 'month', cancel_at_period_end = 1 WHERE owner_user_id = ?", (owner,),
    )
    before = billing.account(owner)
    assert not billing_trial.start(owner)
    after = billing.account(owner)
    assert after["status"] == "canceling"
    assert after["cancel_at_period_end"] == 1
    assert after["trial_started_at"] == before["trial_started_at"]
    assert after["trial_ends_at"] == before["trial_ends_at"]
