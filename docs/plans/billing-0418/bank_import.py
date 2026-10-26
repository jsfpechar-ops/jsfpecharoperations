"""ČSOB statement import (brief 0418): read the bank's export, match payments to invoices.

The operator downloads a statement from ČSOB internet banking (GPC/ABO or CSV)
and uploads it on /admin/fakturace. Nothing here calls the bank: there is no
outbound request. A payment whose variable symbol and amount fit an unpaid
invoice marks it paid; everything else waits for the operator.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional

from . import billing_invoices, billing_jobs, db

STATUSES = ("matched", "unmatched", "partial", "overpaid")


class StatementError(ValueError):
    """The file is not a statement this importer can read."""


def _text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise StatementError("encoding")


def _fold(value: str) -> str:
    """Header text without accents, case or spaces: 'Variabilní symbol' -> 'variabilnisymbol'."""
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def _vs(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits.lstrip("0")


def _row_id(*parts: str) -> str:
    return "h" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _gpc_date(value: str) -> Optional[str]:
    if not re.fullmatch(r"\d{6}", value or ""):
        return None
    day, month, year = int(value[:2]), int(value[2:4]), 2000 + int(value[4:6])
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_gpc(text: str) -> List[Dict[str, Any]]:
    """GPC/ABO: one ``075`` line per transaction, fixed columns. Credits only."""
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("075") or len(line) < 97:
            continue
        line = line.ljust(128)
        code = line[60]
        if code != "2":  # 1 debit, 2 credit, 4/5 storno
            continue
        received = _gpc_date(line[122:128]) or _gpc_date(line[91:97])
        if not received:
            continue
        tx = line[35:48].strip().lstrip("0")
        rows.append({
            "bank_tx_id": f"gpc-{tx}" if tx else _row_id(line),
            "received_on": received,
            "amount_haler": int(line[48:60]),
            "vs": _vs(line[61:71]),
            "counter_account": line[19:35].strip().lstrip("0"),
            "message": line[97:117].strip(),
        })
    return rows


# Folded header names -> field. The first matching column wins.
_CSV_FIELDS = {
    "id": ("idpohybu", "idtransakce", "cislotransakce", "identifikacetransakce", "reference", "id"),
    "date": ("datumzauctovani", "datumprovedeni", "datum", "date"),
    "amount": ("castka", "objem", "amount"),
    "vs": ("variabilnisymbol", "vs"),
    "account": ("protiucet", "cisloprotiuctu", "protiucetabanka", "counteraccount"),
    "message": ("zpravaproprijemce", "poznamka", "popis", "zprava", "message"),
}


def _csv_amount(value: str) -> Optional[int]:
    text = (value or "").replace(" ", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "")
    text = text.replace(",", ".")
    try:
        return int(round(float(text) * 100))
    except ValueError:
        return None


def _csv_date(value: str) -> Optional[str]:
    text = (value or "").strip()
    for pattern, order in ((r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", "dmy"), (r"(\d{4})-(\d{2})-(\d{2})", "ymd")):
        m = re.match(pattern, text)
        if m:
            a, b, c = (int(x) for x in m.groups())
            try:
                return (date(c, b, a) if order == "dmy" else date(a, b, c)).isoformat()
            except ValueError:
                return None
    return None


def parse_csv(text: str) -> List[Dict[str, Any]]:
    """A CSV export with a header row; columns are found by their Czech or English names."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if any(k in _fold(line) for k in ("castka", "amount"))), None)
    if start is None:
        raise StatementError("no_header")
    body = "\n".join(lines[start:])
    delimiter = ";" if body.count(";") >= body.count(",") else ","
    reader = csv.reader(io.StringIO(body), delimiter=delimiter)
    header = [_fold(h) for h in next(reader)]
    cols: Dict[str, int] = {}
    for field, names in _CSV_FIELDS.items():
        for name in names:
            if name in header:
                cols[field] = header.index(name)
                break
    if "amount" not in cols or "date" not in cols:
        raise StatementError("no_columns")
    rows: List[Dict[str, Any]] = []
    for record in reader:
        if not any(cell.strip() for cell in record):
            continue
        cell = lambda field: record[cols[field]].strip() if field in cols and cols[field] < len(record) else ""  # noqa: E731
        amount = _csv_amount(cell("amount"))
        received = _csv_date(cell("date"))
        if amount is None or received is None or amount <= 0:
            continue
        tx = cell("id")
        rows.append({
            "bank_tx_id": f"csv-{tx}" if tx else _row_id(received, str(amount), cell("vs"), cell("account"), cell("message")),
            "received_on": received,
            "amount_haler": amount,
            "vs": _vs(cell("vs")),
            "counter_account": cell("account"),
            "message": cell("message")[:140],
        })
    return rows


def parse(data: bytes) -> List[Dict[str, Any]]:
    text = _text(data)
    if text.lstrip().startswith("074"):
        return parse_gpc(text)
    return parse_csv(text)


def _invoice_for(vs: str) -> Optional[Dict[str, Any]]:
    if not vs:
        return None
    row = db.query_one(
        "SELECT * FROM platform_invoice WHERE vs = ? AND kind IN ('invoice', 'supplementary') AND voided = 0",
        (vs,),
    )
    return dict(row) if row else None


def record(row: Dict[str, Any], *, actor: str = "admin") -> Optional[str]:
    """Store one payment and match it; its status, or None when it was imported before."""
    invoice = _invoice_for(row["vs"])
    status = "unmatched"
    if invoice and not invoice["paid_on"]:
        if row["amount_haler"] == invoice["total_haler"]:
            status = "matched"
        elif row["amount_haler"] > invoice["total_haler"]:
            status = "overpaid"
        else:
            status = "partial"
    inserted = db.execute(
        "INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, counter_account, message, "
        "matched_invoice_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(bank_tx_id) DO NOTHING",
        (row["bank_tx_id"], row["received_on"], row["amount_haler"], row["vs"] or None,
         row["counter_account"] or None, row["message"] or None,
         invoice["id"] if invoice and status != "unmatched" else None, status),
    )
    if not inserted:
        return None
    if status in ("matched", "overpaid"):
        billing_invoices.mark_paid(int(invoice["id"]), paid_on=row["received_on"], via="bank_auto", actor=actor)
        if invoice["owner_user_id"] is not None:
            billing_jobs.settle(int(invoice["owner_user_id"]))
    return status


def import_statement(data: bytes, *, actor: str = "admin") -> Dict[str, int]:
    """Read and record every credit in the file; counts per status, plus ``seen`` for repeats."""
    counts = {status: 0 for status in STATUSES}
    counts["seen"] = 0
    for row in parse(data):
        status = record(row, actor=actor)
        counts[status or "seen"] += 1
    db.audit("bank_statement_import", " ".join(f"{k}={v}" for k, v in counts.items()), actor=actor)
    return counts


def mark_paid_manually(invoice_id: int, *, paid_on: str, actor: str) -> bool:
    """The operator's "Označit jako zaplaceno": paid, then the account settles."""
    if not billing_invoices.mark_paid(invoice_id, paid_on=paid_on, via="bank_manual", actor=actor):
        return False
    row = billing_invoices.get(invoice_id)
    if row and row["owner_user_id"] is not None:
        billing_jobs.settle(int(row["owner_user_id"]))
    return True


def unmatched() -> List[Dict[str, Any]]:
    return [dict(r) for r in db.query(
        "SELECT * FROM bank_payment WHERE status != 'matched' ORDER BY received_on DESC LIMIT 200"
    )]
