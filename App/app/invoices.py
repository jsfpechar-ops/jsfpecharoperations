"""Invoice building, numbering and issuing (host-only Phase 1).

See docs/plans/PLAN_GUEST_INVOICE_FEATURE.md. Amounts are integers in haléře.
An issued invoice is immutable; a correction is always a new document.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from . import db, reporting, stay_fee, validation

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
