"""The operator's billing page /admin/fakturace (brief 0419): what is owed, and the accountant's export.

Read-only queries plus the monthly ZIP (CSV + every PDF). Marking paid, storno
and the statement upload live in ``bank_import`` and ``billing_invoices``; the
route only calls them.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import date
from typing import Any, Dict, List, Optional

from . import billing_invoices, db

MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
CSV_HEADER = (
    "Číslo", "Druh", "Opravuje", "Vystaveno", "Splatnost", "Období od", "Období do",
    "Odběratel", "IČO", "DIČ", "Částka Kč", "VS", "Zaplaceno", "Způsob úhrady", "Stornováno",
)
KIND_CS = {"invoice": "faktura", "supplementary": "doplatek", "storno": "storno"}
VIA_CS = {"bank_auto": "výpis", "bank_manual": "ručně"}


def month_or_current(value: Optional[str], today: Optional[date] = None) -> str:
    text = (value or "").strip()
    return text if MONTH.fullmatch(text) else (today or date.today()).strftime("%Y-%m")


def _buyer(snapshot_json: str) -> Dict[str, str]:
    inv = json.loads(snapshot_json or "{}").get("invoice", {})
    return {"name": inv.get("buyer_name", ""), "ico": inv.get("buyer_ico", ""), "dic": inv.get("buyer_dic", "")}


def invoices(month: str) -> List[Dict[str, Any]]:
    """The month's documents by issue date, oldest first, with the buyer as printed."""
    rows = db.query(
        "SELECT i.id, i.owner_user_id, i.kind, i.corrects_id, i.number, i.vs, i.issue_date, i.due_date, "
        "i.period_from, i.period_to, i.total_haler, i.voided, i.paid_on, i.paid_via, i.snapshot_json, "
        "c.number AS corrects_number FROM platform_invoice i "
        "LEFT JOIN platform_invoice c ON c.id = i.corrects_id "
        "WHERE i.issue_date >= ? AND i.issue_date < ? ORDER BY i.issue_date, i.id",
        (f"{month}-01", _next_month(month)),
    )
    out = []
    for r in rows:
        row = dict(r)
        row["buyer"] = _buyer(row.pop("snapshot_json"))
        out.append(row)
    return out


def _next_month(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    return f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"


def unpaid(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Every unpaid invoice of any month, the overdue ones first."""
    day = (today or date.today()).isoformat()
    rows = db.query(
        "SELECT id, owner_user_id, kind, number, vs, issue_date, due_date, total_haler, snapshot_json "
        "FROM platform_invoice WHERE kind IN ('invoice', 'supplementary') AND voided = 0 AND paid_on IS NULL "
        "ORDER BY due_date, id",
    )
    out = []
    for r in rows:
        row = dict(r)
        row["buyer"] = _buyer(row.pop("snapshot_json"))
        row["overdue"] = row["due_date"][:10] < day
        out.append(row)
    return out


def accounts_by_status() -> Dict[str, int]:
    return {r["status"]: int(r["n"]) for r in db.query(
        "SELECT status, COUNT(*) AS n FROM billing_account GROUP BY status")}


def _kc(haler: int) -> str:
    return f"{haler / 100:.2f}".replace(".", ",")


def export_csv(month: str) -> bytes:
    """Semicolons and a BOM, so Czech Excel opens it straight away."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for row in invoices(month):
        writer.writerow((
            row["number"], KIND_CS[row["kind"]], row["corrects_number"] or "", row["issue_date"][:10],
            row["due_date"][:10], row["period_from"][:10], row["period_to"][:10], row["buyer"]["name"],
            row["buyer"]["ico"], row["buyer"]["dic"], _kc(int(row["total_haler"])), row["vs"],
            (row["paid_on"] or "")[:10], VIA_CS.get(row["paid_via"] or "", ""), "ano" if row["voided"] else "",
        ))
    return ("﻿" + buf.getvalue()).encode("utf-8")


def export_zip(month: str) -> bytes:
    """``faktury-YYYY-MM.csv`` and one PDF per document, exactly as stored."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"faktury-{month}.csv", export_csv(month))
        for row in invoices(month):
            zf.writestr(f"pdf/{row['number']}.pdf", billing_invoices.pdf_bytes(int(row["id"])))
    return out.getvalue()
