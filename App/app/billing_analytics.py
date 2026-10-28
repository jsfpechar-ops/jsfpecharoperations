"""Brief 0440/0441/0446: read-only revenue analytics for /admin/fakturace.

The operator's cockpit: MRR/ARR, the customer portfolio with net prices,
watchlists (trials ending, overdue, ending subscriptions), receivables aging,
and the bulk full-history CSV export for Excel/Google Sheets. No writes.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from typing import Any, Dict, List, Optional

from . import billing, billing_admin, db

# An account in these states counts as a paying customer for MRR.
MRR_STATES = ("active", "overdue", "canceling")

CUSTOMERS_CSV_HEADER = (
    "Uzivatel", "Email", "Stav", "Plan", "Interval", "Byty", "Zaklad Kc",
    "Max Kc", "TTLock Kc", "Whitelabel Kc", "Zaloha Kc", "Cistea Kc",
    "Mesicni Kc", "Zacatek obdobi", "Konec obdobi", "Zrusit ke konci",
)
INVOICES_CSV_HEADER = (
    "Cislo", "Druh", "Opravuje", "Vystaveno", "Splatnost", "Obdobi od", "Obdobi do",
    "Uzivatel", "Castka Kc", "VS", "Zaplaceno", "Zpusob uhrady", "Stornovana",
)
PAYMENTS_CSV_HEADER = (
    "Nadpis", "Prijato", "Castka Kc", "VS", "Protiucet", "Zprava", "Stav",
)


def _monthly(total_czk: int, interval: str) -> int:
    return total_czk if interval == "month" else round(total_czk / 12)


def portfolio(today: Optional[date] = None) -> Dict[str, Any]:
    """Every billing account that has a plan, with list/net prices via billing.quote.

    One SQL fetch of the raw columns; every amount comes from the pricing engine,
    so the cockpit can never disagree with an issued invoice.
    """
    day = today or date.today()
    rows = [dict(r) for r in db.query(
        "SELECT b.owner_user_id, b.status, b.plan, b.billing_interval, b.apartments_billed, "
        "b.addon_ttlock, b.addon_whitelabel, b.founder, b.carry_czk, b.cancel_at_period_end, "
        "b.trial_ends_at, b.period_start, b.period_end, "
        "u.display_name, u.email, u.username "
        "FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id "
        "WHERE b.plan IS NOT NULL ORDER BY b.owner_user_id"
    )]
    customers: List[Dict[str, Any]] = []
    mrr = arr = 0
    by_status: Dict[str, int] = {}
    for r in rows:
        q = billing.quote(
            r["apartments_billed"], r["plan"], r["billing_interval"],
            ttlock=bool(r["addon_ttlock"]), whitelabel=bool(r["addon_whitelabel"]),
            founder=bool(r["founder"]),
        )
        net = q["total"] + int(r["carry_czk"] or 0)
        monthly = _monthly(net, r["billing_interval"])
        if r["status"] in MRR_STATES:
            mrr += monthly
            arr += net if r["billing_interval"] == "year" else monthly * 12
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        trial_ends = (r["trial_ends_at"] or "")[:10]
        trial_days = None
        if r["status"] == "trialing" and trial_ends:
            trial_days = (date.fromisoformat(trial_ends) - day).days
        customers.append({
            **r,
            "quote": q,
            "net_czk": net,
            "monthly_czk": monthly,
            "trial_ends": trial_ends,
            "trial_days_left": trial_days,
        })
    return {"customers": customers, "mrr_czk": mrr, "arr_czk": arr,
            "by_status": by_status, "today": day}


def revenue_totals(today: Optional[date] = None) -> Dict[str, Any]:
    """Billed vs collected this month (separate figures, never summed)."""
    day = today or date.today()
    month_start = f"{day:%Y-%m}-01"
    billed = db.query_one(
        "SELECT COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND issue_date >= ? AND issue_date < date(?, '+1 month')",
        (month_start, month_start),
    )
    collected = db.query_one(
        "SELECT COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND paid_on >= ? AND paid_on < date(?, '+1 month')",
        (month_start, month_start),
    )
    return {"billed_czk": int(billed["h"]) // 100, "collected_czk": int(collected["h"]) // 100}


def watchlists(today: Optional[date] = None) -> Dict[str, List[Dict[str, Any]]]:
    """The operator's morning list: act before money is lost."""
    day = today or date.today()
    week = date.fromordinal(day.toordinal() + 7).isoformat()
    trials = [dict(r) for r in db.query(
        "SELECT b.owner_user_id, b.trial_ends_at, u.display_name, u.email "
        "FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id "
        "WHERE b.status = 'trialing' AND b.trial_ends_at >= ? AND b.trial_ends_at <= ? "
        "ORDER BY b.trial_ends_at",
        (day.isoformat(), week),
    )]
    overdue = [dict(r) for r in db.query(
        "SELECT i.id, i.number, i.total_haler, i.due_date, i.owner_user_id, u.display_name "
        "FROM platform_invoice i JOIN user_account u ON u.id = i.owner_user_id "
        "WHERE i.voided = 0 AND i.paid_on IS NULL AND i.due_date < ? "
        "ORDER BY i.due_date",
        (day.isoformat(),),
    )]
    ending = [dict(r) for r in db.query(
        "SELECT b.owner_user_id, b.period_end, u.display_name, u.email "
        "FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id "
        "WHERE b.cancel_at_period_end = 1 ORDER BY b.period_end",
    )]
    for row in overdue:
        row["days_late"] = (day - date.fromisoformat(row["due_date"][:10])).days
    return {"trials_ending": trials, "overdue": overdue, "ending": ending}


def aging(today: Optional[date] = None) -> Dict[str, int]:
    """Unpaid, unvoided invoices bucketed by days past due."""
    day = today or date.today()
    buckets = {"0-7": 0, "8-30": 0, "31-90": 0, "90+": 0}
    for r in db.query(
        "SELECT due_date, total_haler FROM platform_invoice "
        "WHERE voided = 0 AND paid_on IS NULL AND due_date < ?",
        (day.isoformat(),),
    ):
        late = (day - date.fromisoformat(r["due_date"][:10])).days
        key = "0-7" if late <= 7 else "8-30" if late <= 30 else "31-90" if late <= 90 else "90+"
        buckets[key] += int(r["total_haler"]) // 100
    return buckets


def _csv_bytes(header, rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _cz(haler) -> str:
    return f"{int(haler or 0) / 100:.2f}".replace(".", ",")


def export_all_zip() -> bytes:
    """The bulk export (brief 0446): full history, no month limit, Excel-ready."""
    data = portfolio()
    kind_cs = billing_admin.KIND_CS
    via_cs = billing_admin.VIA_CS
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        customers_rows = [(
            c["display_name"], c["email"], c["status"], c["plan"], c["billing_interval"],
            c["apartments_billed"], c["quote"]["base"], c["quote"]["max"], c["quote"]["ttlock"],
            c["quote"]["whitelabel"], c["carry_czk"], c["net_czk"], c["monthly_czk"],
            (c["period_start"] or "")[:10], (c["period_end"] or "")[:10],
            "ano" if c["cancel_at_period_end"] else "",
        ) for c in data["customers"]]
        zf.writestr("zakaznici.csv", _csv_bytes(CUSTOMERS_CSV_HEADER, customers_rows))

        invoice_rows = [(
            r["number"], kind_cs.get(r["kind"], r["kind"]), r["corrects_number"] or "",
            r["issue_date"][:10], r["due_date"][:10], r["period_from"][:10], r["period_to"][:10],
            r["owner_user_id"], _cz(r["total_haler"]), r["vs"], (r["paid_on"] or "")[:10],
            via_cs.get(r["paid_via"] or "", ""), "ano" if r["voided"] else "",
        ) for r in db.query(
            "SELECT i.number, i.kind, c.number AS corrects_number, i.issue_date, i.due_date, "
            "i.period_from, i.period_to, i.owner_user_id, i.total_haler, i.voided, i.paid_on, "
            "i.paid_via, i.vs FROM platform_invoice i "
            "LEFT JOIN platform_invoice c ON c.id = i.corrects_id ORDER BY i.id"
        )]
        zf.writestr("faktury.csv", _csv_bytes(INVOICES_CSV_HEADER, invoice_rows))

        payment_rows = [(
            r["bank_tx_id"], r["received_on"][:10], _cz(r["amount_haler"]), r["vs"] or "",
            r["counter_account"] or "", r["message"] or "", r["status"],
        ) for r in db.query(
            "SELECT bank_tx_id, received_on, amount_haler, vs, counter_account, message, status "
            "FROM bank_payment ORDER BY received_on, bank_tx_id"
        )]
        zf.writestr("platby.csv", _csv_bytes(PAYMENTS_CSV_HEADER, payment_rows))
    return out.getvalue()


def forecast(today: Optional[date] = None) -> Dict[str, int]:
    """Expected collections in the next 30 days: open invoices by due date."""
    day = today or date.today()
    horizon = date.fromordinal(day.toordinal() + 30).isoformat()
    row = db.query_one(
        "SELECT COALESCE(SUM(total_haler), 0) AS h FROM platform_invoice "
        "WHERE voided = 0 AND paid_on IS NULL AND due_date >= ? AND due_date <= ?",
        (day.isoformat(), horizon),
    )
    return {"next_30_days_czk": int(row["h"]) // 100}
