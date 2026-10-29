"""UbyHost's own invoices to hosts (brief 0413): numbering, PDF, storno, mail.

Phase 1 is a bank transfer on an invoice; no payment gateway. An issued invoice
never changes: its PDF and ``snapshot_json`` are stored once. A mistake is
undone with a storno, which also frees the period to be invoiced again.
Invoices are printed in Czech: the buyers are Czech hosts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import billing, config, db, invoice_pdf, invoices, operator, validation

DUE_DAYS = 14
KINDS = ("invoice", "supplementary", "storno")
PAID_VIA = ("bank_auto", "bank_manual")
PLAN_NAMES = {"standard": "Standard", "max": "Max"}


def apartments_cs(n: int) -> str:
    if n == 1:
        return "1 apartmán"
    if 2 <= n <= 4:
        return f"{n} apartmány"
    return f"{n} apartmánů"


def number_for(year: int, seq: int) -> Tuple[str, str]:
    """``UBY-2026-0042`` and its variable symbol ``20260042`` (never repeats)."""
    return f"UBY-{year}-{seq:04d}", f"{year}{seq:04d}"


def period_items(acc: Dict[str, Any]) -> List[Tuple[str, int]]:
    """``(description, whole Kč)`` lines for one period of the ordered plan."""
    n = int(acc["apartments_billed"])
    plan = acc["plan"]
    interval = acc["billing_interval"]
    founder = bool(acc["founder"]) and interval == "year"
    q = billing.quote(
        n, plan, interval,
        ttlock=bool(acc["addon_ttlock"]),
        whitelabel=bool(acc["addon_whitelabel"]),
        founder=founder,
        discount_percent=int(acc["discount_percent"] or 0),
    )
    label = f"Předplatné UbyHost {PLAN_NAMES[plan]}, {apartments_cs(n)}"
    if founder:
        label += ", zakladatelská cena"
    items = [(label, q["base"] + q["max"])]
    if q["ttlock"]:
        items.append((f"Doplněk TTLock, {apartments_cs(n)}", q["ttlock"]))
    if q["whitelabel"]:
        items.append(("Doplněk vlastní značka", q["whitelabel"]))
    if q["discount"]:
        items.append((
            f"Sleva {int(acc['discount_percent'])} %" + (
                f" ({acc['discount_reason']})" if acc.get("discount_reason") else ""),
            -q["discount"],
        ))
    if int(acc["carry_czk"] or 0):
        items.append(("Doplatek za změny v minulém období", int(acc["carry_czk"])))
    return items


def _seller() -> Dict[str, Any]:
    op = operator.details()
    return {
        "seller_name": op["name"],
        "seller_seat": op["address"],
        "seller_ico": op["ico"],
        "seller_dic": op["dic"],
        "seller_email": op["email"],
        "seller_iban": config.BILLING_IBAN,
        "seller_bank_account": config.BILLING_BANK_ACCOUNT,
        "vat_status": config.BILLING_VAT_STATUS,
    }


def _buyer(acc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if acc is None or not (acc.get("buyer_name") or "").strip():
        raise ValueError("buyer_missing")
    return {
        "buyer_name": acc["buyer_name"],
        "buyer_street": acc["buyer_street"] or "",
        "buyer_city": acc["buyer_city"] or "",
        "buyer_zip": acc["buyer_zip"] or "",
        "buyer_ico": acc["buyer_ico"] or "",
        "buyer_dic": acc["buyer_dic"] or "",
    }


def issue(
    owner_user_id: int,
    *,
    kind: str,
    period_from: str,
    period_to: str,
    items: Sequence[Tuple[str, int]],
    issue_date: date,
    corrects_id: Optional[int] = None,
    reason: str = "",
    clear_carry: bool = False,
) -> int:
    """Number, render and store one document; its id. Runs in one transaction."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    buyer = _buyer(billing.account(owner_user_id))
    total = sum(int(czk) for _, czk in items) * 100
    due = issue_date if kind == "storno" else issue_date + timedelta(days=DUE_DAYS)
    year = issue_date.year
    rows = [{"description": d, "quantity": 1, "gross_haler": int(czk) * 100} for d, czk in items]
    with db.immediate() as cur:
        cur.execute(
            "INSERT INTO platform_invoice_sequence (year, last_no) VALUES (?, 1) "
            "ON CONFLICT(year) DO UPDATE SET last_no = platform_invoice_sequence.last_no + 1",
            (year,),
        )
        cur.execute("SELECT last_no FROM platform_invoice_sequence WHERE year = ?", (year,))
        seq = int(cur.fetchone()["last_no"])
        number, vs = number_for(year, seq)
        corrects_number = ""
        if corrects_id is not None:
            cur.execute("SELECT number FROM platform_invoice WHERE id = ?", (corrects_id,))
            corrects_number = cur.fetchone()["number"]
        inv = {
            **_seller(),
            **buyer,
            # The renderer knows invoice / storno / corrective; a supplementary
            # invoice is an ordinary invoice on paper.
            "kind": "storno" if kind == "storno" else "invoice",
            "number": number,
            "vs": vs,
            "issue_date": issue_date.isoformat(),
            "due_date": due.isoformat(),
            "total_haler": total,
            "note": f"Období: {validation.fmt_date_range(period_from, period_to)}",
            "corrects_number": corrects_number,
            "correction_reason": reason,
        }
        pdf = invoice_pdf.render(inv, rows, lang="cs")
        now = db.utcnow()
        cur.execute(
            "INSERT INTO platform_invoice (owner_user_id, kind, corrects_id, seq_year, seq_no, "
            "number, vs, issue_date, due_date, period_from, period_to, total_haler, "
            "snapshot_json, pdf_blob, pdf_sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id, kind, corrects_id, year, seq, number, vs,
                inv["issue_date"], inv["due_date"], period_from, period_to, total,
                json.dumps({"invoice": inv, "items": rows}, ensure_ascii=False, sort_keys=True),
                pdf, hashlib.sha256(pdf).hexdigest(), now,
            ),
        )
        cur.execute("SELECT id FROM platform_invoice WHERE number = ?", (number,))
        new_id = int(cur.fetchone()["id"])
        if kind == "storno":
            cur.execute("UPDATE platform_invoice SET voided = 1 WHERE id = ?", (corrects_id,))
        if clear_carry:
            cur.execute(
                "UPDATE billing_account SET carry_czk = 0, updated_at = ? WHERE owner_user_id = ?",
                (now, owner_user_id),
            )
    db.audit("platform_invoice_issued", f"{number} {kind}", actor="system", owner_user_id=owner_user_id)
    return new_id


def issue_for_period(owner_user_id: int, period_from: str, period_to: str, *, today: date) -> int:
    """The period's invoice, issued once; asking again returns the same id."""
    existing = db.query_one(
        "SELECT id FROM platform_invoice WHERE owner_user_id = ? AND period_from = ? "
        "AND period_to = ? AND kind = 'invoice' AND voided = 0",
        (owner_user_id, period_from, period_to),
    )
    if existing:
        return int(existing["id"])
    acc = billing.account(owner_user_id)
    if acc is None or acc["plan"] is None or acc["billing_interval"] is None:
        raise ValueError("no_plan")
    return issue(
        owner_user_id, kind="invoice", period_from=period_from, period_to=period_to,
        items=period_items(acc), issue_date=today, clear_carry=True,
    )


def issue_supplementary(
    owner_user_id: int, *, amount_czk: int, description: str,
    period_from: str, period_to: str, today: date,
) -> int:
    """The difference for a rise during an annual period (``billing.apply_change``)."""
    if amount_czk < billing.SUPPLEMENTARY_MIN_CZK:
        raise ValueError("below_minimum")
    return issue(
        owner_user_id, kind="supplementary", period_from=period_from, period_to=period_to,
        items=[(description, amount_czk)], issue_date=today,
    )


def storno(invoice_id: int, *, reason: str, today: date) -> int:
    """Cancel an unpaid invoice with a storno; its period can then be invoiced again.

    A paid invoice is not cancelled here: a refund is the operator's manual step.
    """
    row = get(invoice_id)
    if row is None or row["kind"] == "storno":
        raise ValueError("not_an_invoice")
    if row["voided"]:
        raise ValueError("already_voided")
    if row["paid_on"]:
        raise ValueError("paid")
    if row["owner_user_id"] is None:
        raise ValueError("workspace_deleted")
    items = json.loads(row["snapshot_json"])["items"]
    return issue(
        int(row["owner_user_id"]), kind="storno",
        period_from=row["period_from"], period_to=row["period_to"],
        items=[(it["description"], -(it["gross_haler"] // 100)) for it in items],
        issue_date=today, corrects_id=invoice_id, reason=reason,
    )


def mark_paid(invoice_id: int, *, paid_on: str, via: str, actor: str = "system") -> bool:
    """Record the payment once; False when it was already paid or voided."""
    if via not in PAID_VIA:
        raise ValueError(f"unknown paid_via: {via}")
    changed = db.execute_rowcount(
        "UPDATE platform_invoice SET paid_on = ?, paid_via = ? "
        "WHERE id = ? AND paid_on IS NULL AND voided = 0 AND kind != 'storno'",
        (paid_on, via, invoice_id),
    )
    if changed:
        row = get(invoice_id)
        db.audit("platform_invoice_paid", f"{row['number']} {via}", actor=actor,
                 owner_user_id=row["owner_user_id"])
    return bool(changed)


def get(invoice_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one("SELECT * FROM platform_invoice WHERE id = ?", (invoice_id,))
    return dict(row) if row else None


def for_owner(owner_user_id: int) -> List[Dict[str, Any]]:
    """The host's documents, newest first, without the PDF bytes."""
    return [
        dict(r) for r in db.query(
            "SELECT id, kind, number, vs, issue_date, due_date, period_from, period_to, "
            "total_haler, voided, paid_on, corrects_id FROM platform_invoice "
            "WHERE owner_user_id = ? ORDER BY id DESC",
            (owner_user_id,),
        )
    ]


def pdf_bytes(invoice_id: int) -> bytes:
    """Always the stored bytes, checked against their hash; never re-rendered."""
    row = db.query_one("SELECT pdf_blob, pdf_sha256 FROM platform_invoice WHERE id = ?", (invoice_id,))
    if not row or not row["pdf_blob"]:
        raise ValueError("platform_invoice_pdf_missing")
    blob = row["pdf_blob"]
    if isinstance(blob, str):
        blob = blob.encode("latin-1")
    blob = bytes(blob)
    if hashlib.sha256(blob).hexdigest() != row["pdf_sha256"]:
        raise ValueError("platform_invoice_pdf_changed")
    return blob


def recipient(owner_user_id: int) -> str:
    """The billing e-mail from the order, else the account's login address."""
    acc = billing.account(owner_user_id) or {}
    if (acc.get("buyer_email") or "").strip():
        return acc["buyer_email"].strip()
    row = db.query_one("SELECT email FROM user_account WHERE id = ?", (owner_user_id,))
    return (row["email"] or "").strip() if row else ""


def send(invoice_id: int) -> Optional[int]:
    """Mail the invoice with its PDF attached (mail kind ``billing_invoice``)."""
    from . import mail_notify

    row = get(invoice_id)
    if row is None or row["owner_user_id"] is None:
        return None
    return mail_notify.billing_invoice(
        invoice_id=invoice_id,
        to_email=recipient(int(row["owner_user_id"])),
        owner_user_id=int(row["owner_user_id"]),
        number=row["number"],
        vs=row["vs"],
        amount_czk=int(row["total_haler"]) // 100,
        due=row["due_date"],
        period=validation.fmt_date_range(row["period_from"], row["period_to"]),
    )


def expired_ids(today: date) -> List[int]:
    """Documents past the 10-year rule, stornos first; an original whose storno
    is still inside its ten years stays."""
    cutoff = invoices.retention_cutoff(today).isoformat()
    return [
        int(r["id"])
        for r in db.query(
            "SELECT id FROM platform_invoice WHERE issue_date < ? "
            "AND NOT EXISTS (SELECT 1 FROM platform_invoice c "
            "                WHERE c.corrects_id = platform_invoice.id AND c.issue_date >= ?) "
            "ORDER BY CASE WHEN corrects_id IS NULL THEN 1 ELSE 0 END, id",
            (cutoff, cutoff),
        )
    ]


def purge_expired(today: date) -> int:
    """Delete UbyHost's invoices and bank payments past the 10-year rule."""
    cutoff = invoices.retention_cutoff(today).isoformat()
    ids = expired_ids(today)
    for invoice_id in ids:
        db.execute("DELETE FROM bank_payment WHERE matched_invoice_id = ?", (invoice_id,))
        db.execute("DELETE FROM platform_invoice WHERE id = ?", (invoice_id,))
    payments = db.execute_rowcount(
        "DELETE FROM bank_payment WHERE matched_invoice_id IS NULL AND received_on < ?", (cutoff,)
    )
    if ids or payments:
        db.audit("platform_invoice_purge", f"invoices={len(ids)} payments={payments}", actor="system")
    return len(ids) + payments
