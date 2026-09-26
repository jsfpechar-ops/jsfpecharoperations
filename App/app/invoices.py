"""Invoice building, numbering and issuing (host-only Phase 1).

See docs/plans/PLAN_GUEST_INVOICE_FEATURE.md. Amounts are integers in haléře.
An issued invoice is immutable; a correction is always a new document.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from . import db, invoice_pdf, reporting, stay_fee, validation

VAT_ACCOMMODATION = 12
VAT_OTHER = 21
VAT_RATES = (VAT_ACCOMMODATION, VAT_OTHER)


def _form_str(form, key: str, default: str = "") -> str:
    value = form.get(key)
    if value is None:
        return default
    return str(value).strip()


def _form_int(form, key: str) -> Optional[int]:
    raw = _form_str(form, key)
    return int(raw) if raw.isdigit() else None


def _to_haler(text: str) -> int:
    """'1234.50' or '1 234,5' -> haléře. Raises ValueError on junk."""
    cleaned = (text or "").replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return int((Decimal(cleaned) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def vat_split(gross_haler: int, rate: Optional[int]) -> tuple:
    """(base_haler, vat_haler) computed top-down from the gross, or (None, None)."""
    if not rate:
        return None, None
    gross = Decimal(gross_haler) / 100
    tax = (gross * rate / (100 + rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    base = gross - tax
    base_haler = int((base * 100).to_integral_value(rounding=ROUND_HALF_UP))
    vat_haler = int((tax * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return base_haler, vat_haler


def _locked_rate(vat_status: str, kind: str, vat_rate: Optional[int]) -> Optional[int]:
    if vat_status != "payer":
        return None
    if kind == "stay_fee":
        return None  # outside the VAT base
    return vat_rate if vat_rate in VAT_RATES else VAT_ACCOMMODATION


def _amount_haler(form, key: str) -> int:
    raw = _form_str(form, key)
    if not raw:
        return 0
    try:
        return _to_haler(raw)
    except (ValueError, ArithmeticError):
        return 0


def build_draft(reservation, entity, form, lang: str, *, today: date) -> Dict[str, Any]:
    """Validate-and-snapshot the issue form into a draft. Pure except for reads."""
    vat_status = (entity["vat_status"] or "non_payer") if entity else "non_payer"
    start = validation.parse_iso_date(reservation["date_from"])
    end = validation.parse_iso_date(reservation["date_to"])
    nights = max((end - start).days, 0) if start and end else 0
    progress = reporting.reservation_progress(reservation)
    persons = progress.get("expected") or progress.get("filled") or 1
    price_haler = _amount_haler(form, "price_czk")
    items: List[Dict[str, Any]] = []

    acc_name = _form_str(form, "property_name") or reservation["internal_name"] or ""
    if vat_status and lang == "cs":
        acc_desc = (
            f"Ubytování – {acc_name}, {reservation['date_from']} – {reservation['date_to']}, "
            f"{nights} nocí, {persons} os."
        )
    else:
        acc_desc = (
            f"Accommodation – {acc_name}, {reservation['date_from']} – {reservation['date_to']}, "
            f"{nights} nights, {persons} guests"
        )
    items.append(
        {
            "kind": "accommodation",
            "description": acc_desc,
            "quantity": 1,
            "unit": "pobyt",
            "vat_rate": _locked_rate(vat_status, "accommodation", VAT_ACCOMMODATION),
            "gross_haler": price_haler,
        }
    )

    include_fee = bool(form.get("include_stay_fee"))
    if include_fee:
        summary = stay_fee.stay_summary(reservation, entity)
        fee_total = summary["total_czk"] if summary else 0
        if fee_total > 0:
            items.append(
                {
                    "kind": "stay_fee",
                    "description": "Poplatek z pobytu" if lang == "cs" else "Local stay fee",
                    "quantity": 1,
                    "unit": "",
                    "vat_rate": None,
                    "gross_haler": fee_total * 100,
                }
            )

    other_desc = _form_str(form, "other_description")
    other_price = _amount_haler(form, "other_price_czk")
    if other_desc and other_price:
        rate = _form_int(form, "other_vat_rate") or VAT_OTHER
        items.append(
            {
                "kind": "other",
                "description": other_desc[:80],
                "quantity": 1,
                "unit": "",
                "vat_rate": _locked_rate(vat_status, "other", rate),
                "gross_haler": other_price,
            }
        )

    for item in items:
        base, vat = vat_split(item["gross_haler"], item["vat_rate"])
        item["base_haler"] = base
        item["vat_haler"] = vat

    if vat_status == "payer":
        total_base = sum(i["base_haler"] or 0 for i in items)
        total_vat = sum(i["vat_haler"] or 0 for i in items)
    else:
        total_base = None
        total_vat = None
    total_haler = sum(i["gross_haler"] for i in items)

    already_paid = bool(form.get("already_paid"))
    due_days = entity["invoice_due_days"] if entity and entity["invoice_due_days"] is not None else 14
    due_date = None if already_paid else (today + timedelta(days=due_days)).isoformat()
    duzp = (_form_str(form, "duzp") or reservation["date_to"]) if vat_status == "payer" else None
    paid_via = _form_str(form, "paid_via") if already_paid else ""

    return {
        "kind": "invoice",
        "lang": "cs" if _form_str(form, "lang") == "cs" else "en",
        "vat_status": vat_status,
        "issue_date": today.isoformat(),
        "duzp": duzp,
        "due_date": due_date,
        "paid_on": reservation["date_to"] if already_paid else None,
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
        "stay_from": reservation["date_from"],
        "stay_to": reservation["date_to"],
        "stay_label": reservation["internal_name"] if "internal_name" in reservation.keys() else "",
        "items": items,
        "total_base_haler": total_base,
        "total_vat_haler": total_vat,
        "total_haler": total_haler,
    }


def validate_for_issue(draft: Dict[str, Any]) -> List[validation.Issue]:
    """The legal minimum for this document, as issue keys for the route to translate."""
    seller = draft["seller"]
    buyer = draft["buyer"]
    issues: List[validation.Issue] = []
    if not seller["seat"]:
        issues.append(validation.Issue("seller_seat", "invoice.err.seller_seat"))
    if not seller["registry"]:
        issues.append(validation.Issue("seller_registry", "invoice.err.registry"))
    if draft["vat_status"] == "payer" and not seller["dic"]:
        issues.append(validation.Issue("seller_dic", "invoice.err.seller_dic"))
    if not buyer["name"]:
        issues.append(validation.Issue("buyer_name", "invoice.buyer.required"))
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


PAID_VIA_LABELS = {
    "airbnb": "Airbnb",
    "booking": "Booking.com",
    "direct_transfer": "Převodem",
    "cash": "Hotově",
    "other": "Jinak",
}


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
    row["paid_via_label"] = PAID_VIA_LABELS.get(row.get("paid_via") or "", row.get("paid_via") or "")
    row["corrects_number"] = None
    if row.get("corrects_invoice_id"):
        src = cur.execute(
            "SELECT number FROM invoice WHERE id = ?", (row["corrects_invoice_id"],)
        ).fetchone()
        row["corrects_number"] = src["number"] if src else None
    return row


def issue(draft: Dict[str, Any], actor_user_id: Optional[int]) -> int:
    """Allocate a number, write the invoice + items and its PDF, atomically."""
    issues = validate_for_issue(draft)
    if issues:
        raise ValueError(issues[0].message)
    invoice_id, _number = _write_issued(draft, actor_user_id)
    db.audit(
        "invoice_issued",
        f"id={invoice_id} number={_number} entity={draft['legal_entity_id']} total={draft['total_haler']}",
        owner_user_id=draft.get("owner_user_id"),
    )
    return invoice_id


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
    new_id, number = _write_issued(draft, actor_user_id)
    db.audit(
        "invoice_corrected",
        f"orig={invoice_id} new={new_id} kind={kind} reason={reason.strip()}",
        owner_user_id=original["owner_user_id"],
    )
    return new_id



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

