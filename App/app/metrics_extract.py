"""Read-only business-metrics extraction (brief 0444).

Current portfolio values and invoice issue/paid aggregates only. Meanings are
defined in docs/plans/business-metrics-and-database-plan-20261030.md §5a and
verified against billing.py, billing_analytics.py and migrations 0023/0031.
Paid aggregates are invoice-paid status, NOT a cash-allocation ledger. History
that was never snapshotted is unavailable (None), never zero.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from . import billing_analytics, db


def current_metrics(today: Optional[date] = None) -> Dict[str, Any]:
    """Today's verified values. No writes, no history claims."""
    day = today or date.today()
    month_start = f"{day:%Y-%m}-01"
    portfolio = billing_analytics.portfolio(day)

    issued = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND issue_date >= ? AND issue_date < date(?, '+1 month')",
        (month_start, month_start),
    )
    paid = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND paid_on >= ? AND paid_on < date(?, '+1 month')",
        (month_start, month_start),
    )
    storno = db.query_one(
        "SELECT COUNT(*) AS n FROM platform_invoice WHERE voided = 0 AND kind = 'storno' "
        "AND issue_date >= ? AND issue_date < date(?, '+1 month')",
        (month_start, month_start),
    )
    # Invoice-paid status; a cash-allocation ledger does not exist (plan §5a).
    allocated = db.query_one(
        "SELECT COALESCE(SUM(amount_haler), 0) AS h FROM bank_payment "
        "WHERE matched_invoice_id IS NOT NULL AND received_on >= ? "
        "AND received_on < date(?, '+1 month')",
        (month_start, month_start),
    )

    # MRR movement needs snapshot history; current-month-only coverage means
    # movement/churn are unavailable, never zero (plan §5a).
    snapshot_months = db.query_one(
        "SELECT COUNT(DISTINCT month) AS n FROM billing_month_snapshot"
    )
    history_available = int(snapshot_months["n"]) >= 2

    return {
        "as_of": day.isoformat(),
        "mrr_czk": portfolio["mrr_czk"],
        "arr_czk": portfolio["arr_czk"],
        "by_status": portfolio["by_status"],
        "issued_invoices": {
            "count": int(issued["n"]),
            "total_haler": int(issued["h"]),
            "total_czk_truncated": int(issued["h"]) // 100,
        },
        "invoice_paid": {  # invoice-paid status, not reconciled cash
            "count": int(paid["n"]),
            "total_haler": int(paid["h"]),
            "total_czk_truncated": int(paid["h"]) // 100,
        },
        "storno_in_month": int(storno["n"]),
        "bank_allocated_haler_month": int(allocated["h"]),  # matched only
        "movement": {"available": history_available},
        "account_churn": {"available": history_available},
    }
