"""Brief 0417: the daily billing run. New periods, invoices, apartment counts, dunning, settling."""
from __future__ import annotations

import json
import secrets
from datetime import date, timedelta

import pytest

from app import billing, billing_invoices, billing_jobs, config, db

TODAY = date.today()


def _user() -> int:
    return db.insert("user_account", {"username": f"job-{secrets.token_hex(4)}", "password_hash": "x",
                                      "created_at": db.utcnow(), "email": "job@example.cz"})


def _apartments(owner: int, n: int) -> None:
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    for i in range(n):
        db.insert("apartment", {"internal_name": f"Job {i}", "owner_user_id": owner, "created_at": db.utcnow()})


@pytest.fixture
def owner(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    owner_id = _user()
    _apartments(owner_id, 2)
    billing.ensure_account(owner_id)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 2, buyer_name = 'Penzion Job', buyer_street = 'Hlavní 1', buyer_city = 'Brno', "
        "buyer_zip = '60200', buyer_email = 'job@example.cz' WHERE owner_user_id = ?",
        (owner_id,),
    )
    yield owner_id
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ? AND corrects_id IS NOT NULL", (owner_id,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _period(owner: int, start: date, end: date, **extra) -> None:
    fields = {"period_start": start.isoformat(), "period_end": end.isoformat(), **extra}
    sets = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE billing_account SET {sets} WHERE owner_user_id = ?", (*fields.values(), owner))


def _invoices(owner: int) -> list:
    return [dict(r) for r in db.query(
        "SELECT * FROM platform_invoice WHERE owner_user_id = ? ORDER BY id", (owner,))]


def _kinds(owner: int) -> list:
    return [r["kind"] for r in db.query("SELECT kind FROM email_outbox WHERE owner_user_id = ? ORDER BY id", (owner,))]


def test_nothing_runs_while_billing_is_off(owner, monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    assert billing_jobs.run(TODAY, owner) == {"rolled": 0, "invoiced": 0, "apartments": 0, "errors": 0}


def test_the_current_period_is_invoiced_and_mailed_once(owner):
    _period(owner, TODAY, TODAY + timedelta(days=29))
    assert billing_jobs.run(TODAY, owner)["invoiced"] == 1
    assert billing_jobs.run(TODAY, owner)["invoiced"] == 0
    assert [i["total_haler"] for i in _invoices(owner)] == [2 * 149 * 100]
    assert _kinds(owner) == ["billing_invoice"]


def test_a_new_period_takes_the_waiting_change(owner):
    _period(owner, TODAY - timedelta(days=31), TODAY - timedelta(days=1),
            plan="max", pending_change_json=json.dumps({"plan": "standard"}))
    counts = billing_jobs.run(TODAY, owner)
    assert counts["rolled"] == 1 and counts["invoiced"] == 1
    acc = billing.account(owner)
    assert acc["plan"] == "standard" and acc["pending_change_json"] is None
    assert acc["period_start"] == TODAY.isoformat()


def test_a_cancelled_plan_ends_with_its_period(owner):
    _period(owner, TODAY - timedelta(days=31), TODAY - timedelta(days=1), status="canceling")
    billing_jobs.run(TODAY, owner)
    assert billing.account(owner)["status"] == "paused"
    assert _invoices(owner) == []


def test_an_added_apartment_on_a_yearly_plan_is_billed_from_today(owner):
    _period(owner, TODAY - timedelta(days=30), TODAY + timedelta(days=300), billing_interval="year")
    billing_jobs.run(TODAY, owner)  # the period's own invoice
    _apartments(owner, 3)
    assert billing_jobs.run(TODAY, owner)["apartments"] == 1
    assert billing.account(owner)["apartments_billed"] == 3
    assert [i["kind"] for i in _invoices(owner)] == ["invoice", "supplementary"]
    assert billing_jobs.run(TODAY, owner)["apartments"] == 0


def test_an_archived_apartment_counts_from_the_next_period(owner):
    _period(owner, TODAY - timedelta(days=5), TODAY + timedelta(days=24))
    _apartments(owner, 1)
    billing_jobs.run(TODAY, owner)
    acc = billing.account(owner)
    assert acc["apartments_billed"] == 2
    assert json.loads(acc["pending_change_json"]) == {"apartments": 1}


def test_dunning_reminds_then_pauses_and_payment_reopens(owner):
    _period(owner, TODAY - timedelta(days=20), TODAY + timedelta(days=9))
    invoice_id = billing_invoices.issue_for_period(owner, (TODAY - timedelta(days=20)).isoformat(),
                                                   (TODAY + timedelta(days=9)).isoformat(),
                                                   today=TODAY - timedelta(days=20))
    db.execute("UPDATE platform_invoice SET due_date = ? WHERE id = ?",
               ((TODAY - timedelta(days=1)).isoformat(), invoice_id))
    billing_jobs.dunning(TODAY, owner)
    assert billing.account(owner)["status"] == "overdue"
    db.execute("UPDATE platform_invoice SET due_date = ? WHERE id = ?",
               ((TODAY - timedelta(days=14)).isoformat(), invoice_id))
    billing_jobs.dunning(TODAY, owner)
    billing_jobs.dunning(TODAY, owner)
    assert billing.account(owner)["status"] == "paused"
    assert _kinds(owner).count("billing_overdue") == 2
    assert billing_jobs.settle(owner, today=TODAY) is False
    billing_invoices.mark_paid(invoice_id, paid_on=TODAY.isoformat(), via="bank_manual")
    assert billing_jobs.settle(owner, today=TODAY) is True
    assert billing.account(owner)["status"] == "active"


def test_one_broken_account_does_not_stop_the_run(owner):
    _period(owner, TODAY, TODAY + timedelta(days=29), buyer_name=None)
    counts = billing_jobs.run(TODAY, owner)
    assert counts["errors"] == 1 and counts["invoiced"] == 0
