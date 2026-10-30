"""Brief 0444: the read-only metrics extraction (current values only)."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from app import auth, billing, billing_analytics, billing_invoices, config, db, metrics_extract

TODAY = date.today()


@pytest.fixture
def setup(monkeypatch):
    """An admin, and a host on a monthly plan with this period's invoice issued."""
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    suffix = secrets.token_hex(4)
    auth.create_account(f"adm{suffix}@example.test", "Admin", role="admin", username=f"adm{suffix}")
    host = auth.create_account(f"hst{suffix}@example.test", "Host", username=f"hst{suffix}")
    db.insert("apartment", {"internal_name": "Extract 1", "owner_user_id": host, "created_at": db.utcnow()})
    billing.ensure_account(host)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, period_start = ?, period_end = ?, buyer_name = 'Penzion Ú\u010detní', "
        "buyer_street = 'Hlavní 3', buyer_city = 'Brno', buyer_zip = '60200', buyer_ico = '27074358' "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), host),
    )
    invoice_id = billing_invoices.issue_for_period(host, TODAY.isoformat(),
                                                   (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    yield {"host_id": host, "invoice": dict(billing_invoices.get(invoice_id))}
    db.execute("DELETE FROM bank_payment WHERE matched_invoice_id IN "
               "(SELECT id FROM platform_invoice WHERE owner_user_id = ?)", (host,))
    db.execute("DELETE FROM bank_payment WHERE vs LIKE ?", (f"{TODAY:%Y}%{suffix}%",))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_month_snapshot WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))


def _set_status(host_id: int, status: str) -> None:
    db.execute("UPDATE billing_account SET status = ? WHERE owner_user_id = ?", (status, host_id))


def test_mrr_counts_paying_states_excludes_trial(setup):
    data = metrics_extract.current_metrics(TODAY)
    quote = billing.quote(1, "standard", "month")
    assert data["mrr_czk"] == quote["total"]
    _set_status(setup["host_id"], "trialing")
    db.execute("UPDATE billing_account SET trial_started_at = ?, trial_ends_at = ? WHERE owner_user_id = ?",
               (TODAY.isoformat(), (TODAY + timedelta(days=10)).isoformat(), setup["host_id"]))
    data = metrics_extract.current_metrics(TODAY)
    assert data["mrr_czk"] == 0
    assert data["by_status"].get("trialing") == 1


def test_discount_and_annual_normalization(setup):
    db.execute("UPDATE billing_account SET discount_percent = 20, billing_interval = 'year', "
               "period_start = ?, period_end = ? WHERE owner_user_id = ?",
               (TODAY.isoformat(), (TODAY + timedelta(days=365)).isoformat(), setup["host_id"]))
    data = metrics_extract.current_metrics(TODAY)
    net = billing.quote(1, "standard", "year", discount_percent=20)["total"]
    assert data["mrr_czk"] == round(net / 12)


def test_cancellation_request_is_not_churn(setup):
    db.execute("UPDATE billing_account SET cancel_at_period_end = 1 WHERE owner_user_id = ?",
               (setup["host_id"],))
    data = metrics_extract.current_metrics(TODAY)
    assert data["mrr_czk"] > 0
    assert "cancel_at_period_end" not in data["by_status"]
    _set_status(setup["host_id"], "canceling")
    data = metrics_extract.current_metrics(TODAY)
    assert data["mrr_czk"] > 0  # canceling is still a paying MRR state
    assert data["by_status"].get("canceling") == 1


def test_issue_and_paid_aggregates_with_void_and_storno(setup):
    data = metrics_extract.current_metrics(TODAY)
    assert data["issued_invoices"]["count"] == 1
    assert data["issued_invoices"]["total_haler"] == setup["invoice"]["total_haler"]
    assert data["issued_invoices"]["total_czk_truncated"] == setup["invoice"]["total_haler"] // 100
    assert data["invoice_paid"]["count"] == 0

    billing_invoices.mark_paid(setup["invoice"]["id"], paid_on=TODAY.isoformat(),
                               via="bank_manual", actor="test")
    data = metrics_extract.current_metrics(TODAY)
    assert data["invoice_paid"]["count"] == 1
    assert data["invoice_paid"]["total_haler"] == setup["invoice"]["total_haler"]

    # storno() refuses a paid invoice (verified contract), so void-and-reissue
    # semantics are tested on an unpaid invoice instead.
    db.execute("UPDATE platform_invoice SET paid_on = NULL, paid_via = NULL WHERE id = ?",
               (setup["invoice"]["id"],))
    storno_id = billing_invoices.storno(setup["invoice"]["id"], reason="test", today=TODAY)
    storno = billing_invoices.get(storno_id)
    data = metrics_extract.current_metrics(TODAY)
    assert data["storno_in_month"] == 1
    # The storno voided the original: it leaves issue and paid aggregates...
    assert data["issued_invoices"]["count"] == 1  # only the storno document itself
    assert data["invoice_paid"]["count"] == 0
    assert storno["total_haler"] == -setup["invoice"]["total_haler"]


def test_bank_allocation_counts_only_matched(setup):
    db.execute(
        "INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, "
        "matched_invoice_id, status) VALUES (?, ?, ?, ?, ?, ?)",
        (f"T-{secrets.token_hex(6)}", TODAY.isoformat(), setup["invoice"]["total_haler"],
         setup["invoice"]["vs"], setup["invoice"]["id"], "matched"),
    )
    db.execute(
        "INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"U-{secrets.token_hex(6)}", TODAY.isoformat(), 99900, "9999999999", "unmatched"),
    )
    data = metrics_extract.current_metrics(TODAY)
    assert data["bank_allocated_haler_month"] == setup["invoice"]["total_haler"]


def test_month_boundary(setup):
    first = TODAY.replace(day=1)
    last_previous = first - timedelta(days=1)
    db.execute("UPDATE platform_invoice SET issue_date = ?, paid_on = NULL WHERE id = ?",
               (last_previous.isoformat(), setup["invoice"]["id"]))
    data = metrics_extract.current_metrics(TODAY)
    assert data["issued_invoices"]["count"] == 0
    db.execute("UPDATE platform_invoice SET issue_date = ? WHERE id = ?",
               (first.isoformat(), setup["invoice"]["id"]))
    data = metrics_extract.current_metrics(first)
    assert data["issued_invoices"]["count"] == 1


def test_missing_history_is_unavailable_not_zero(setup):
    db.execute("DELETE FROM billing_month_snapshot")
    data = metrics_extract.current_metrics(TODAY)
    assert data["movement"] == {"available": False}
    assert data["account_churn"] == {"available": False}
    assert "movement_czk" not in data and "churned_accounts" not in data


def test_repeated_extraction_is_idempotent_and_write_free(setup):
    before = dict(db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice"))
    billing_analytics.write_month_snapshot(TODAY.strftime("%Y-%m"), today=TODAY)
    first = metrics_extract.current_metrics(TODAY)
    second = metrics_extract.current_metrics(TODAY)
    after = dict(db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice"))
    assert first == second
    assert before == after


def test_output_has_no_personal_data_fields(setup):
    data = metrics_extract.current_metrics(TODAY)
    blob = repr(data)
    for forbidden in ("display_name", "email", "username", "buyer_"):
        assert forbidden not in blob
