"""Invoice building, numbering and issuing (standalone host tool).

The invoice is NOT tied to a stay: the host builds a custom document with any
number of line items, each with a quantity, unit price and VAT rate. Amounts are
integers in haléře. An issued invoice is immutable; a correction is a new paper.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from . import db, invoice_pdf, validation

VAT_RATES = (0, 12, 21)
PAID_VIA_LABELS = {
    "airbnb": "Airbnb",
    "booking": "Booking.com",
    "direct_transfer": "Převodem",
    "cash": "Hotově",
    "other": "Jinak",
}


def _form_str(form, key: str, default: str = "") -> str:
    value = form.get(key)
    if value is None:
        return default
    return str(value).strip()


def _getlist(form, key: str) -> list:
    getter = getattr(form, "getlist", None)
    if callable(getter):
        return list(getter(key))
    value = form.get(key)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _at(values: list, index: int, default: str = "") -> str:
    return str(values[index]) if index < len(values) else default


def _to_decimal(text: str) -> Decimal:
    cleaned = (text or "").replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _to_int(text: str, default: int = 1) -> int:
    value = _to_decimal(text)
    try:
        return int(value.to_integral_value(rounding=ROUND_HALF_UP))
    except (ValueError, InvalidOperation):
        return default


def _to_rate(text: str) -> int:
    value = _to_int(text, default=12)
    return value if value in VAT_RATES else 12


def vat_parts(quantity: int, unit_price: Decimal, rate: int) -> tuple:
    """(base_haler, vat_haler, gross_haler) computed up from the net unit price."""
    base = int((unit_price * quantity * 100).to_integral_value(rounding=ROUND_HALF_UP))
    vat = int((Decimal(base) * rate / 100).to_integral_value(rounding=ROUND_HALF_UP))
    return base, vat, base + vat


def _items_from_form(form, vat_status: str) -> List[Dict[str, Any]]:
    descs = _getlist(form, "item_description")
    qtys = _getlist(form, "item_quantity")
    units = _getlist(form, "item_unit")
    prices = _getlist(form, "item_unit_price")
    rates = _getlist(form, "item_vat_rate")
    count = max(len(descs), len(qtys), len(units), len(prices), len(rates))
    items: List[Dict[str, Any]] = []
    for i in range(count):
        description = _at(descs, i).strip()
        if not description:
            continue
        quantity = max(_to_int(_at(qtys, i, "1"), default=1), 1)
        unit = _at(units, i).strip()[:20]
        price = _to_decimal(_at(prices, i, "0"))
        if vat_status == "payer":
            rate = _to_rate(_at(rates, i))
            base, vat, gross = vat_parts(quantity, price, rate)
        else:
            rate = None
            base = vat = None
            gross = int((price * quantity * 100).to_integral_value(rounding=ROUND_HALF_UP))
        items.append(
            {
                "kind": "other",
                "description": description[:150],
                "quantity": quantity,
                "unit": unit,
                "vat_rate": rate,
                "base_haler": base,
                "vat_haler": vat,
                "gross_haler": gross,
            }
        )
    return items


def build_draft(entity, form, lang: str, *, today: date) -> Dict[str, Any]:
    """Snapshot the free-form issue form into a draft. Pure except for reads."""
    vat_status = (entity["vat_status"] or "non_payer") if entity else "non_payer"
    items = _items_from_form(form, vat_status)
    if vat_status == "payer":
        total_base = sum(i["base_haler"] or 0 for i in items)
        total_vat = sum(i["vat_haler"] or 0 for i in items)
    else:
        total_base = None
        total_vat = None
    total_haler = sum(i["gross_haler"] for i in items)

    already_paid = bool(form.get("already_paid"))
    due_days = entity["invoice_due_days"] if entity and entity["invoice_due_days"] is not None else 14
    due_date = _form_str(form, "due_date")
    if not due_date and not already_paid:
        due_date = (today + timedelta(days=due_days)).isoformat()
    paid_via = _form_str(form, "paid_via") if already_paid else ""
    if paid_via == "custom":
        # "Paid via" offered a free-text field: the host's own wording is what
        # the invoice should print, exactly as typed (minus the edges).
        paid_via = _form_str(form, "paid_via_custom")[:60]

    return {
        "kind": "invoice",
        "lang": "cs" if _form_str(form, "lang") == "cs" else "en",
        "vat_status": vat_status,
        "issue_date": today.isoformat(),
        "duzp": _form_str(form, "duzp") or None,
        "due_date": due_date or None,
        "paid_on": today.isoformat() if already_paid else None,
        "paid_via": paid_via or None,
        "seller": {
            "name": entity["name"] if entity else "",
            "seat": entity["seat"] if entity else "",
            "ico": entity["ico"] if entity else "",
            "dic": entity["dic"] if entity else "",
            "registry": entity["registry_entry"] if entity else "",
            "bank_account": entity["bank_account"] if entity else "",
            "iban": entity["iban"] if entity else "",
            "bic": entity["bic"] if entity else "",
            "email": entity["contact_email"] if entity else "",
            "phone": entity["contact_phone"] if entity else "",
        },
        "buyer": {
            "name": _form_str(form, "buyer_name"),
            "street": _form_str(form, "buyer_street"),
            "city": _form_str(form, "buyer_city"),
            "zip": _form_str(form, "buyer_zip"),
            "country": _form_str(form, "buyer_country") or "CZE",
            "ico": _form_str(form, "buyer_ico"),
            "dic": _form_str(form, "buyer_dic"),
            "email": _form_str(form, "buyer_email"),
        },
        "note": _form_str(form, "note")[:300],
        "items": items,
        "total_base_haler": total_base,
        "total_vat_haler": total_vat,
        "total_haler": total_haler,
    }


def custom_paid_via_label(paid_via: Optional[str]) -> str:
    """The printed payment-method label.

    Listed options translate through ``PAID_VIA_LABELS``; anything else is the
    host's own "Paid via" text captured verbatim on the form.
    """
    if not paid_via:
        return ""
    return PAID_VIA_LABELS.get(paid_via, paid_via)


def validate_for_issue(draft: Dict[str, Any]) -> List[validation.Issue]:
    """The legal minimum for this document, as issue keys for the route to translate."""
    seller = draft["seller"]
    buyer = draft["buyer"]
    issues: List[validation.Issue] = []
    if not seller["name"]:
        issues.append(validation.Issue("seller_name", "invoice.err.seller_name"))
    if not seller["seat"]:
        issues.append(validation.Issue("seller_seat", "invoice.err.seller_seat"))
    if not seller["registry"]:
        issues.append(validation.Issue("seller_registry", "invoice.err.registry"))
    if draft["vat_status"] == "payer" and not seller["dic"]:
        issues.append(validation.Issue("seller_dic", "invoice.err.seller_dic"))
    if not buyer["name"]:
        issues.append(validation.Issue("buyer_name", "invoice.buyer.required"))
    if not draft["items"]:
        issues.append(validation.Issue("items", "invoice.err.no_items"))
    if draft["total_haler"] <= 0:
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    return issues

def preview_number(entity) -> str:
    """The next number as a hint for the form; not the allocated one."""
    year = date.today().year
    row = db.query_one(
        "SELECT last_no FROM invoice_sequence WHERE legal_entity_id = ? AND year = ?",
        (entity["id"], year),
    )
    last = row["last_no"] if row else 0
    seq = last + 1
    width = max(4, len(str(seq)))
    return f"{entity['invoice_prefix'] or ''}{year}-{seq:0{width}d}"


def allocate_number(cur, entity, issue_year: int) -> tuple:
    """(year, seq, number, vs). Caller holds the write lock (db.immediate)."""
    row = cur.execute(
        "SELECT last_no FROM invoice_sequence WHERE legal_entity_id = ? AND year = ?",
        (entity["id"], issue_year),
    ).fetchone()
    last = row["last_no"] if row else 0
    if entity["invoice_next_number"] and entity["invoice_next_number_year"] == issue_year:
        last = max(last, entity["invoice_next_number"] - 1)
        cur.execute(
            "UPDATE legal_entity SET invoice_next_number = NULL, invoice_next_number_year = NULL "
            "WHERE id = ?",
            (entity["id"],),
        )
    seq = last + 1
    cur.execute(
        "INSERT INTO invoice_sequence (legal_entity_id, year, last_no) VALUES (?, ?, ?) "
        "ON CONFLICT(legal_entity_id, year) DO UPDATE SET last_no = excluded.last_no",
        (entity["id"], issue_year, seq),
    )
    width = max(4, len(str(seq)))
    number = f"{entity['invoice_prefix'] or ''}{issue_year}-{seq:0{width}d}"
    vs = f"{issue_year}{seq:0{width}d}"
    return issue_year, seq, number, vs


def _invoice_columns(draft: Dict[str, Any], number: str, vs: str, seq_year: int, seq_no: int) -> Dict[str, Any]:
    seller = draft["seller"]
    buyer = draft["buyer"]
    return {
        "legal_entity_id": draft["legal_entity_id"],
        "apartment_id": draft.get("apartment_id"),
        "reservation_id": draft.get("reservation_id"),
        "kind": draft["kind"],
        "corrects_invoice_id": draft.get("corrects_invoice_id"),
        "correction_reason": draft.get("correction_reason"),
        "correction_date": draft.get("correction_date"),
        "seq_year": seq_year,
        "seq_no": seq_no,
        "number": number,
        "vs": vs,
        "lang": draft["lang"],
        "currency": "CZK",
        "vat_status": draft["vat_status"],
        "issue_date": draft["issue_date"],
        "duzp": draft.get("duzp"),
        "due_date": draft.get("due_date"),
        "paid_on": draft.get("paid_on"),
        "paid_via": draft.get("paid_via"),
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
        "seller_ico": seller["ico"] or None,
        "seller_dic": seller["dic"] or None,
        "seller_registry": seller["registry"] or None,
        "seller_bank_account": seller["bank_account"] or None,
        "seller_iban": seller["iban"] or None,
        "seller_bic": seller["bic"] or None,
        "seller_email": seller["email"] or None,
        "seller_phone": seller["phone"] or None,
        "buyer_name": buyer["name"],
        "buyer_street": buyer["street"] or None,
        "buyer_city": buyer["city"] or None,
        "buyer_zip": buyer["zip"] or None,
        "buyer_country": buyer["country"] or None,
        "buyer_ico": buyer["ico"] or None,
        "buyer_dic": buyer["dic"] or None,
        "buyer_email": buyer["email"] or None,
        "stay_from": draft.get("stay_from"),
        "stay_to": draft.get("stay_to"),
        "stay_label": draft.get("stay_label") or None,
        "total_base_haler": draft.get("total_base_haler"),
        "total_vat_haler": draft.get("total_vat_haler"),
        "total_haler": draft["total_haler"],
        "owner_user_id": draft.get("owner_user_id"),
        "created_at": db.utcnow(),
    }


def pdf_view_row(cur, invoice_id: int) -> Dict[str, Any]:
    """The invoice row plus the view-only fields invoice_pdf.render expects."""
    raw = cur.execute("SELECT * FROM invoice WHERE id = ?", (invoice_id,)).fetchone()
    row = dict(raw)
    country = row.get("buyer_country") or ""
    row["buyer_country_name"] = (
        "" if not country or country == "CZE" else validation.country_name(country, "cs")
    )
    row["paid_via_label"] = custom_paid_via_label(row.get("paid_via"))
    row["corrects_number"] = None
    if row.get("corrects_invoice_id"):
        src = cur.execute(
            "SELECT number FROM invoice WHERE id = ?", (row["corrects_invoice_id"],)
        ).fetchone()
        row["corrects_number"] = src["number"] if src else None
    return row


def view_row(invoice_id: int) -> Dict[str, Any]:
    """The stored invoice row plus the view fields, for detail/PDF/preview."""
    with db.cursor() as cur:
        return pdf_view_row(cur, invoice_id)


def _write_issued(draft: Dict[str, Any], actor_user_id: Optional[int]) -> tuple:
    """Write an issued document inside one write lock. Returns (id, number)."""
    year = int(draft["issue_date"][:4])
    with db.immediate() as cur:
        entity = cur.execute(
            "SELECT * FROM legal_entity WHERE id = ?", (draft["legal_entity_id"],)
        ).fetchone()
        seq_year, seq_no, number, vs = allocate_number(cur, entity, year)
        columns = _invoice_columns(draft, number, vs, seq_year, seq_no)
        cur.execute(
            f"INSERT INTO invoice ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            list(columns.values()),
        )
        invoice_id = cur.lastrowid
        for position, item in enumerate(draft["items"], start=1):
            cur.execute(
                "INSERT INTO invoice_item (invoice_id, position, kind, description, quantity, "
                "unit, vat_rate, base_haler, vat_haler, gross_haler) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    invoice_id, position, item["kind"], item["description"], item["quantity"],
                    item["unit"], item["vat_rate"], item["base_haler"], item["vat_haler"],
                    item["gross_haler"],
                ),
            )
        view = pdf_view_row(cur, invoice_id)
        items = [
            dict(r)
            for r in cur.execute(
                "SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY position", (invoice_id,)
            ).fetchall()
        ]
        pdf = invoice_pdf.render(view, items, draft["lang"])
        digest = hashlib.sha256(pdf).hexdigest()
        cur.execute(
            "UPDATE invoice SET pdf_blob = ?, pdf_sha256 = ?, issued_at = ?, issued_by = ? WHERE id = ?",
            (pdf, digest, db.utcnow(), actor_user_id, invoice_id),
        )
    return invoice_id, number


def issue(draft: Dict[str, Any], actor_user_id: Optional[int]) -> int:
    """Allocate a number, write the invoice + items and its PDF, atomically."""
    issues = validate_for_issue(draft)
    if issues:
        raise ValueError(issues[0].message)
    invoice_id, number = _write_issued(draft, actor_user_id)
    db.audit(
        "invoice_issued",
        f"id={invoice_id} number={number} entity={draft['legal_entity_id']} total={draft['total_haler']}",
        owner_user_id=draft.get("owner_user_id"),
    )
    return invoice_id


def _draft_from_original(original, items, kind, reason, correction_date, today: date) -> Dict[str, Any]:
    neg = -1
    new_items = [
        {
            "kind": item["kind"],
            "description": item["description"],
            "quantity": item["quantity"],
            "unit": item["unit"],
            "vat_rate": item["vat_rate"],
            "base_haler": (item["base_haler"] * neg) if item["base_haler"] is not None else None,
            "vat_haler": (item["vat_haler"] * neg) if item["vat_haler"] is not None else None,
            "gross_haler": item["gross_haler"] * neg,
        }
        for item in items
    ]
    return {
        "legal_entity_id": original["legal_entity_id"],
        "apartment_id": original["apartment_id"],
        "reservation_id": original["reservation_id"],
        "kind": kind,
        "corrects_invoice_id": original["id"],
        "correction_reason": reason,
        "correction_date": correction_date if kind == "corrective" else None,
        "lang": original["lang"],
        "vat_status": original["vat_status"],
        "issue_date": today.isoformat(),
        "duzp": None,
        "due_date": None,
        "paid_on": today.isoformat() if original["paid_on"] else None,
        "paid_via": original["paid_via"],
        "seller": {
            "name": original["seller_name"], "seat": original["seller_seat"],
            "ico": original["seller_ico"] or "", "dic": original["seller_dic"] or "",
            "registry": original["seller_registry"] or "",
            "bank_account": original["seller_bank_account"] or "",
            "iban": original["seller_iban"] or "", "bic": original["seller_bic"] or "",
            "email": original["seller_email"] or "", "phone": original["seller_phone"] or "",
        },
        "buyer": {
            "name": original["buyer_name"], "street": original["buyer_street"] or "",
            "city": original["buyer_city"] or "", "zip": original["buyer_zip"] or "",
            "country": original["buyer_country"] or "CZE",
            "ico": original["buyer_ico"] or "", "dic": original["buyer_dic"] or "",
            "email": original["buyer_email"] or "",
        },
        "stay_from": original["stay_from"], "stay_to": original["stay_to"],
        "stay_label": original["stay_label"] or "",
        "items": new_items,
        "total_base_haler": (original["total_base_haler"] * neg) if original["total_base_haler"] is not None else None,
        "total_vat_haler": (original["total_vat_haler"] * neg) if original["total_vat_haler"] is not None else None,
        "total_haler": original["total_haler"] * neg,
        "owner_user_id": original["owner_user_id"],
    }


def cancel(invoice_id: int, reason: str, correction_date: Optional[str], actor_user_id: Optional[int], *, today: date) -> int:
    """Issue a storno (non-payer) or ODD (payer) reversing an issued invoice."""
    original = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    if not original or original["kind"] != "invoice":
        raise ValueError("not_cancellable")
    if not reason or len(reason.strip()) < 5:
        raise ValueError("reason_required")
    if db.query_one("SELECT id FROM invoice WHERE corrects_invoice_id = ?", (invoice_id,)):
        raise ValueError("already_corrected")
    items = db.query(
        "SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY position", (invoice_id,)
    )
    kind = "corrective" if original["vat_status"] == "payer" else "storno"
    date_text = correction_date or today.isoformat()
    draft = _draft_from_original(original, items, kind, reason.strip(), date_text, today)
    new_id, _number = _write_issued(draft, actor_user_id)
    db.audit(
        "invoice_corrected",
        f"orig={invoice_id} new={new_id} kind={kind} reason={reason.strip()}",
        owner_user_id=original["owner_user_id"],
    )
    return new_id


def purge_expired(today: date, owner_user_id: Optional[int] = None) -> int:
    """Delete issued documents older than 10 full years, with the unlock flag."""
    cutoff = date(today.year - 10, 1, 1).isoformat()
    ids = [
        r["id"]
        for r in db.query(
            "SELECT id FROM invoice WHERE issue_date < ? AND owner_user_id IS ?",
            (cutoff, owner_user_id),
        )
    ]
    if not ids:
        return 0
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    try:
        for invoice_id in ids:
            db.execute("DELETE FROM invoice_item WHERE invoice_id = ?", (invoice_id,))
            db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
    finally:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
            "ON CONFLICT(key) DO UPDATE SET value = ''"
        )
    db.audit("invoice_retention_purge", f"deleted={len(ids)}")
    return len(ids)


def download_pdf(invoice_id: int) -> bytes:
    """Always the stored bytes; an issued document is never re-rendered."""
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    if not row or not row["pdf_blob"]:
        raise ValueError("invoice_pdf_missing")
    blob = row["pdf_blob"]
    if isinstance(blob, str):
        blob = blob.encode("latin-1")
    digest = hashlib.sha256(blob).hexdigest()
    if row["pdf_sha256"] and digest != row["pdf_sha256"]:
        raise ValueError("invoice_pdf_mismatch")
    return blob
