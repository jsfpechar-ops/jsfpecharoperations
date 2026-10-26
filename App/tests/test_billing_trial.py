"""Brief 0414: the trial. Start, reminders, end, banner, sign-up hook."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from app import billing, billing_trial, config, db, signup

TODAY = date.today()


def _user(**extra) -> int:
    return db.insert(
        "user_account",
        {"username": f"trial-{secrets.token_hex(4)}", "password_hash": "x",
         "created_at": db.utcnow(), **extra},
    )


@pytest.fixture
def owner():
    db.init_db()
    owner_id = _user(email=f"trial-{secrets.token_hex(4)}@example.cz")
    yield owner_id
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)


def _trialing(owner_id: int, ends: date, **fields) -> None:
    billing.ensure_account(owner_id)
    values = {"status": "trialing", "trial_started_at": (ends - timedelta(days=30)).isoformat(),
              "trial_ends_at": ends.isoformat()}
    values.update(fields)
    sets = ", ".join(f"{name} = ?" for name in values)
    db.execute(f"UPDATE billing_account SET {sets} WHERE owner_user_id = ?", (*values.values(), owner_id))


@pytest.mark.parametrize("start, interval, end", [
    (date(2026, 11, 1), "month", date(2026, 11, 30)),
    (date(2026, 1, 31), "month", date(2026, 2, 28)),
    (date(2026, 12, 15), "month", date(2027, 1, 14)),
    (date(2026, 11, 1), "year", date(2027, 10, 31)),
    (date(2028, 2, 29), "year", date(2029, 2, 28)),
])
def test_period_end(start, interval, end):
    assert billing_trial.period_end(start, interval) == end


def test_nothing_happens_while_billing_is_off(owner):
    billing.ensure_account(owner)
    assert billing_trial.run(TODAY) == {"started": 0, "reminded": 0, "active": 0, "paused": 0}
    assert billing_trial.start(owner) is False
    assert billing_trial.banner(owner) is None


def test_a_passed_connection_test_starts_the_trial(owner, billing_on):
    billing.ensure_account(owner)
    apartment_id = db.insert("apartment", {"internal_name": "Trial test", "owner_user_id": owner,
                                                 "created_at": TODAY.isoformat()})
    billing_trial.mark_verified(apartment_id, owner)
    acc = billing.account(owner)
    assert acc["status"] == "trialing"
    assert acc["trial_ends_at"] == (TODAY + timedelta(days=30)).isoformat()
    assert db.query_one("SELECT ubyport_verified_at FROM apartment WHERE id = ?", (apartment_id,))[0]
    assert billing_trial.start(owner) is False  # already running


def test_the_trial_starts_by_itself_after_seven_days(owner, billing_on):
    billing.ensure_account(owner)
    db.execute("UPDATE user_account SET email_verified_at = ? WHERE id = ?",
               ((TODAY - timedelta(days=6)).isoformat(), owner))
    billing_trial.run(TODAY)
    assert billing.account(owner)["status"] == "trial_pending"
    db.execute("UPDATE user_account SET email_verified_at = ? WHERE id = ?",
               ((TODAY - timedelta(days=7)).isoformat(), owner))
    billing_trial.run(TODAY)
    assert billing.account(owner)["status"] == "trialing"


def test_og_hosts_without_a_row_are_never_touched(owner, billing_on):
    billing_trial.run(TODAY)
    assert billing.account(owner) is None
    assert billing_trial.banner(owner) is None


def test_reminder_once_per_stage_and_none_after_ordering(owner, billing_on, monkeypatch):
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    _trialing(owner, TODAY + timedelta(days=7))
    billing_trial.run(TODAY)
    billing_trial.run(TODAY)
    rows = db.query("SELECT kind, subject FROM email_outbox WHERE owner_user_id = ?", (owner,))
    assert [r["kind"] for r in rows] == ["billing_trial"]
    assert "7" in rows[0]["subject"]
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
    _trialing(owner, TODAY + timedelta(days=3), plan="standard", billing_interval="month")
    billing_trial.run(TODAY)
    assert db.query("SELECT 1 FROM email_outbox WHERE owner_user_id = ?", (owner,)) == []


def test_trial_end_with_a_plan_starts_the_first_period(owner, billing_on):
    _trialing(owner, TODAY - timedelta(days=1), plan="max", billing_interval="month")
    assert billing_trial.run(TODAY)["active"] == 1
    acc = billing.account(owner)
    assert acc["status"] == "active"
    assert acc["period_start"] == TODAY.isoformat()
    assert acc["period_end"] == billing_trial.period_end(TODAY, "month").isoformat()
    assert billing.entitlements(owner).ai_multiplier == 3


def test_trial_end_without_a_plan_pauses_but_keeps_reporting(owner, billing_on):
    _trialing(owner, TODAY - timedelta(days=1))
    assert billing_trial.run(TODAY)["paused"] == 1
    ent = billing.entitlements(owner)
    assert ent.read_only and ent.ubyport_submit


def test_banner_lines(owner, billing_on):
    _trialing(owner, TODAY + timedelta(days=2))
    line = billing_trial.banner(owner)
    assert line["kind"] == "trial" and line["warning"] is True
    _trialing(owner, TODAY + timedelta(days=20))
    assert billing_trial.banner(owner)["warning"] is False
    db.execute("UPDATE billing_account SET status = 'paused' WHERE owner_user_id = ?", (owner,))
    assert billing_trial.banner(owner)["kind"] == "paused"
    db.execute("UPDATE billing_account SET status = 'active', plan = 'standard' WHERE owner_user_id = ?",
               (owner,))
    assert billing_trial.banner(owner) is None


def test_confirming_the_sign_up_opens_a_billing_row(owner, billing_on):
    db.execute("UPDATE user_account SET signup_verify_nonce = 'n-0414', active = 0 WHERE id = ?", (owner,))
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner,))
    assert signup.activate(account) is True
    assert billing.account(owner)["status"] == "trial_pending"
