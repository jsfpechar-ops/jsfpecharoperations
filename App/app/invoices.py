"""Invoice building, numbering and issuing (host tool).

A new invoice belongs to one stay: line 1 is the accommodation, built from the
stay; up to three extras come from a fixed list (``EXTRA_KINDS``). Amounts are
integers in haléře. An issued invoice is immutable; a correction is a new paper.
Drafts built without a stay (corrections, older tests) keep the free-form path.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from . import db, invoice_pdf, payments, validation

VAT_RATES = (0, 12, 21)
# The one-page PDF fits four two-line items with VAT detail and the QR block.
MAX_ITEMS = 4
# Ten million CZK per figure: anything larger is a typo, not an invoice.
MAX_AMOUNT = Decimal("10000000")
# Invoices belong to one stay (docs/plans/stay-only-invoices.md).
STAY_PAST_DAYS = 400
STAY_FUTURE_DAYS = 365
STAY_MAX_INVOICES = 3
EXTRA_MAX_QUANTITY = 99
OTHER_MAX_CHARS = 60
# All extras together may equal the accommodation line; "Other" alone 30 % of it.
EXTRAS_MAX_SHARE = Decimal("1.00")
OTHER_MAX_SHARE = Decimal("0.30")
EXTRA_KINDS = (
    "cleaning", "stay_fee", "breakfast", "parking", "pet", "extra_bed", "late_checkout", "other",
)
EXTRA_LABELS = {
    "cs": {
        "cleaning": "Úklid", "stay_fee": "Poplatek z pobytu", "breakfast": "Snídaně",
        "parking": "Parkování", "pet": "Domácí zvíře", "extra_bed": "Přistýlka",
        "late_checkout": "Pozdní odjezd",
    },
    "en": {
        "cleaning": "Cleaning", "stay_fee": "Local stay fee", "breakfast": "Breakfast",
        "parking": "Parking", "pet": "Pet", "extra_bed": "Extra bed",
        "late_checkout": "Late check-out",
    },
}
STAY_LINE_PREFIX = {"cs": "Ubytování", "en": "Accommodation"}
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


def _parse_decimal(text: str) -> Optional[Decimal]:
    """The amount, or None when it is not a finite number within MAX_AMOUNT."""
    cleaned = (text or "").replace(" ", "").replace("\u00a0", "")
    if "," in cleaned:
        # Czech style "1.000,50": the dot groups thousands, the comma is decimal.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or abs(value) > MAX_AMOUNT:
        return None
    return value


def _to_decimal(text: str) -> Decimal:
    value = _parse_decimal(text)
    return Decimal(0) if value is None else value


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
        raw_price = _at(prices, i, "0")
        price = _to_decimal(raw_price)
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
                # A typed price that is not a number must not become 0 Kč.
                "price_invalid": bool(raw_price.strip()) and _parse_decimal(raw_price) is None,
            }
        )
    return items


def seller_snapshot(entity, form) -> Dict[str, Any]:
    """The seller block for a draft: explicit presence checks, not defaults.

    A field the form carries is used verbatim — including a deliberate blank,
    which is not the same as a field the form never sent. Any posted bank
    number goes through the shared payments helper so the format printed on
    the document and used for the QR code is always the same. Fields the form
    does not carry fall back to the operator's stored details.
    """
    def pick(key: str) -> str:
        form_key = f"seller_{key}"
        if form_key in form:
            return _form_str(form, form_key)
        entity_key = {
            "registry": "registry_entry",
            "email": "contact_email",
            "phone": "contact_phone",
        }.get(key, key)
        if entity and entity_key in entity.keys():
            return entity[entity_key] or ""
        return ""

    seller = {
        "name": pick("name"),
        "seat": pick("seat"),
        "ico": pick("ico"),
        "dic": pick("dic"),
        "registry": pick("registry"),
        "bank_account": pick("bank_account"),
        "iban": pick("iban"),
        "bic": pick("bic"),
        "email": pick("email"),
        "phone": pick("phone"),
    }
    if "seller_bank_account" in form:
        form_bank = _form_str(form, "seller_bank_account")
        if form_bank:
            try:
                seller["bank_account"], seller["iban"] = payments.normalise_account(
                    form_bank
                )
            except ValueError:
                # A bank number the helper rejects is never printed; the
                # operator's stored account stays on the document.
                seller["bank_account"] = entity["bank_account"] if entity else ""
                seller["iban"] = entity["iban"] if entity else ""
        else:
            seller["bank_account"] = ""
            seller["iban"] = ""
    return seller


def form_item_rows(form) -> List[Dict[str, str]]:
    """Raw item rows the browser posted, aligned per column index.

    Used only to rebuild the form for a 422 rerender, so trailing blank rows
    (a cloned template row) are dropped but a part-typed row survives.
    """
    descs = _getlist(form, "item_description")
    kinds = _getlist(form, "item_kind")
    qtys = _getlist(form, "item_quantity")
    units = _getlist(form, "item_unit")
    prices = _getlist(form, "item_unit_price")
    rates = _getlist(form, "item_vat_rate")
    rows: List[Dict[str, str]] = []
    for i in range(max(len(kinds), len(descs), len(qtys), len(units), len(prices), len(rates))):
        row = {
            "kind": _at(kinds, i),
            "description": _at(descs, i),
            "quantity": _at(qtys, i, "1"),
            "unit": _at(units, i),
            "unit_price": _at(prices, i),
            "vat_rate": _at(rates, i, "21"),
        }
        if not (row["kind"].strip() or row["description"].strip() or row["unit_price"].strip()):
            continue
        rows.append(row)
    return rows


def stay_nights(reservation) -> int:
    """Nights between check-in and check-out; 0 when a date is unreadable."""
    try:
        start = date.fromisoformat(str(reservation["date_from"])[:10])
        end = date.fromisoformat(str(reservation["date_to"])[:10])
    except ValueError:
        return 0
    return (end - start).days


def stay_problem(reservation, today: date) -> Optional[str]:
    """None when an invoice may be issued for this stay, else an i18n key."""
    if reservation is None:
        return "invoice.err.no_stay"
    if (reservation["status"] or "") == "cancelled":
        return "invoice.err.stay_cancelled"
    if stay_nights(reservation) < 1:
        return "invoice.err.stay_dates"
    if str(reservation["date_to"])[:10] < (today - timedelta(days=STAY_PAST_DAYS)).isoformat():
        return "invoice.err.stay_too_old"
    if str(reservation["date_from"])[:10] > (today + timedelta(days=STAY_FUTURE_DAYS)).isoformat():
        return "invoice.err.stay_too_far"
    return None


def _nights_text(nights: int, lang: str) -> str:
    if lang == "cs":
        word = "noc" if nights == 1 else ("noci" if 2 <= nights <= 4 else "nocí")
    else:
        word = "night" if nights == 1 else "nights"
    return f"{nights} {word}"


def stay_label(property_name: str, reservation, lang: str) -> str:
    """'Chata, 12.10.2026 – 15.10.2026 (3 noci)': the PDF prints it under the header."""
    dates = validation.fmt_date_range(reservation["date_from"], reservation["date_to"])
    return f"{property_name}, {dates} ({_nights_text(stay_nights(reservation), lang)})"


def _price_invalid(raw_price: str, price: Decimal) -> bool:
    return (not raw_price) or _parse_decimal(raw_price) is None or price <= 0


def _stay_item(form, vat_status: str, label: str, lang: str) -> Dict[str, Any]:
    """Line 1. Only the price (and, for payers, the rate) comes from the form."""
    raw_price = _form_str(form, "stay_price")
    price = _to_decimal(raw_price)
    if vat_status == "payer":
        rate = _to_rate(_form_str(form, "stay_vat_rate") or "12")
        base, vat, gross = vat_parts(1, price, rate)
    else:
        rate = None
        base = vat = None
        gross = int((price * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return {
        "kind": "accommodation",
        "extra_kind": "stay",
        "description": f"{STAY_LINE_PREFIX[lang]} – {label}"[:150],
        "quantity": 1,
        "unit": "pobyt" if lang == "cs" else "stay",
        "vat_rate": rate,
        "base_haler": base,
        "vat_haler": vat,
        "gross_haler": gross,
        "price_invalid": _price_invalid(raw_price, price),
    }


def _extras_from_form(form, vat_status: str, lang: str) -> List[Dict[str, Any]]:
    """Lines 2-4. The wording comes from EXTRA_LABELS; only "other" takes typed text."""
    kinds = _getlist(form, "item_kind")
    descs = _getlist(form, "item_description")
    qtys = _getlist(form, "item_quantity")
    units = _getlist(form, "item_unit")
    prices = _getlist(form, "item_unit_price")
    rates = _getlist(form, "item_vat_rate")
    count = max(len(kinds), len(descs), len(qtys), len(units), len(prices), len(rates))
    items: List[Dict[str, Any]] = []
    for i in range(count):
        kind = _at(kinds, i).strip()
        text = _at(descs, i).strip()
        raw_price = _at(prices, i).strip()
        if not (kind or text or raw_price):
            continue  # an untouched blank row
        if not kind:
            kind = "other"  # no kind picked: typed text is an "Other" line
        # "stay" is the accommodation line only; a forged extra must not use it.
        if kind == "stay":
            kind = "invalid"
        quantity = _to_int(_at(qtys, i, "1"), default=1)
        price = _to_decimal(raw_price)
        if kind == "other":
            description = text[:OTHER_MAX_CHARS]
        else:
            description = EXTRA_LABELS[lang].get(kind, "")
        if vat_status == "payer":
            # The local stay fee is a municipal fee outside VAT (owner, 2026-10-08).
            rate = 0 if kind == "stay_fee" else _to_rate(_at(rates, i))
            base, vat, gross = vat_parts(quantity, price, rate)
        else:
            rate = None
            base = vat = None
            gross = int((price * quantity * 100).to_integral_value(rounding=ROUND_HALF_UP))
        items.append(
            {
                "kind": "stay_fee" if kind == "stay_fee" else "other",
                "extra_kind": kind,
                "description": description,
                "quantity": quantity,
                "unit": _at(units, i).strip()[:20],
                "vat_rate": rate,
                "base_haler": base,
                "vat_haler": vat,
                "gross_haler": gross,
                "price_invalid": _price_invalid(raw_price, price),
            }
        )
    return items


def build_draft(entity, form, lang: str, *, today: date, stay: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Snapshot the free-form issue form into a draft. Pure except for reads."""
    vat_status = (entity["vat_status"] or "non_payer") if entity else "non_payer"
    doc_lang = "cs" if _form_str(form, "lang") == "cs" else "en"
    label = ""
    if stay is not None:
        # stay = {"reservation": row, "property_name": str}; the route checked ownership.
        label = stay_label(stay["property_name"], stay["reservation"], doc_lang)
        items = [_stay_item(form, vat_status, label, doc_lang)]
        items += _extras_from_form(form, vat_status, doc_lang)
    else:
        items = _items_from_form(form, vat_status)
    if vat_status == "payer":
        total_base = sum(i["base_haler"] or 0 for i in items)
        total_vat = sum(i["vat_haler"] or 0 for i in items)
    else:
        total_base = None
        total_vat = None
    total_haler = sum(i["gross_haler"] for i in items)

    # The payment row is a radio pair ("already paid" = "1", "payment
    # requested" = "0"); older clients post a checkbox that appears only
    # when ticked, so both spellings land on the same decision.
    already_paid = _form_str(form, "already_paid") in ("1", "on")
    due_days = entity["invoice_due_days"] if entity and entity["invoice_due_days"] is not None else 14
    due_date = _form_str(form, "due_date")
    if not due_date and not already_paid:
        due_date = (today + timedelta(days=due_days)).isoformat()
    paid_via = _form_str(form, "paid_via") if already_paid else ""
    if paid_via == "custom":
        # "Paid via" offered a free-text field: the host's own wording is what
        # the invoice should print, exactly as typed (minus the edges).
        paid_via = _form_str(form, "paid_via_custom")[:60]

    draft = {
        "kind": "invoice",
        "lang": "cs" if _form_str(form, "lang") == "cs" else "en",
        "vat_status": vat_status,
        "issue_date": today.isoformat(),
        "duzp": _form_str(form, "duzp") or None,
        "due_date": due_date or None,
        "paid_on": today.isoformat() if already_paid else None,
        "paid_via": paid_via or None,
        "seller": seller_snapshot(entity, form),
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
    if stay is not None:
        reservation = stay["reservation"]
        stay_to = str(reservation["date_to"])[:10]
        draft.update(
            {
                "reservation_id": reservation["id"],
                "apartment_id": reservation["apartment_id"],
                "stay_from": str(reservation["date_from"])[:10],
                "stay_to": stay_to,
                "stay_label": label,
                # Tax point: the check-out day, never in the future.
                "duzp": draft["duzp"] or min(stay_to, today.isoformat()),
            }
        )
    return draft


def custom_paid_via_label(paid_via: Optional[str]) -> str:
    """The printed payment-method label.

    Listed options translate through ``PAID_VIA_LABELS``; anything else is the
    host's own "Paid via" text captured verbatim on the form.
    """
    if not paid_via:
        return ""
    return PAID_VIA_LABELS.get(paid_via, paid_via)


def _stay_issues(draft: Dict[str, Any]) -> List[validation.Issue]:
    items = draft["items"]
    issues: List[validation.Issue] = []
    # Line 1 must be the stay line; everything after it is an extra. Filtering by
    # extra_kind == "stay" would let a forged form row with kind "stay" skip the caps.
    if not items or items[0].get("extra_kind") != "stay":
        issues.append(validation.Issue("items", "invoice.err.extra_kind"))
        return issues
    stay_gross = items[0]["gross_haler"] or 0
    extras = items[1:]
    if any(i.get("extra_kind") not in EXTRA_KINDS or not i["description"] for i in extras):
        issues.append(validation.Issue("items", "invoice.err.extra_kind"))
    if sum(1 for i in extras if i.get("extra_kind") == "other") > 1:
        issues.append(validation.Issue("items", "invoice.err.one_other"))
    if any(not 1 <= i["quantity"] <= EXTRA_MAX_QUANTITY for i in extras):
        issues.append(validation.Issue("items", "invoice.err.extra_quantity"))
    # Skip noisy caps when the stay price is already invalid (amount error covers it).
    if items[0].get("price_invalid") or stay_gross <= 0:
        return issues
    extras_gross = sum(i["gross_haler"] for i in extras)
    other_gross = sum(i["gross_haler"] for i in extras if i.get("extra_kind") == "other")
    if extras_gross > stay_gross * EXTRAS_MAX_SHARE:
        issues.append(validation.Issue("items", "invoice.err.extras_cap"))
    if other_gross > stay_gross * OTHER_MAX_SHARE:
        issues.append(validation.Issue("items", "invoice.err.other_cap"))
    return issues


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
    elif len(draft["items"]) > MAX_ITEMS:
        issues.append(validation.Issue("items", "invoice.err.too_many_items"))
    if draft["total_haler"] <= 0 or any(i.get("price_invalid") for i in draft["items"]):
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    if draft.get("kind") == "invoice" and draft.get("reservation_id"):
        issues.extend(_stay_issues(draft))
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
        "note": draft.get("note") or None,
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


class StayLimit(ValueError):
    """The stay already has its invoice, or its last allowed one."""

    def __init__(self, key: str, invoice_id: Optional[int] = None):
        super().__init__(key)
        self.key = key
        self.invoice_id = invoice_id


_ACTIVE_FOR_STAY_SQL = (
    "SELECT i.id, i.number FROM invoice i WHERE i.reservation_id = ? AND i.kind = 'invoice' "
    "AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = i.id) "
    "ORDER BY i.id DESC LIMIT 1"
)


def active_invoice_for_stay(reservation_id: int):
    """The stay's invoice that has no storno/ODD yet, or None."""
    return db.query_one(_ACTIVE_FOR_STAY_SQL, (reservation_id,))


def _check_stay_limit(cur, reservation_id: int) -> None:
    """Runs inside the write lock, so a double click cannot slip a second one in."""
    active = cur.execute(_ACTIVE_FOR_STAY_SQL, (reservation_id,)).fetchone()
    if active:
        raise StayLimit("invoice.err.stay_has_invoice", int(active["id"]))
    total = cur.execute(
        "SELECT COUNT(*) FROM invoice WHERE reservation_id = ? AND kind = 'invoice'",
        (reservation_id,),
    ).fetchone()[0]
    if total >= STAY_MAX_INVOICES:
        raise StayLimit("invoice.err.stay_limit")


def _write_issued(draft: Dict[str, Any], actor_user_id: Optional[int]) -> tuple:
    """Write an issued document inside one write lock. Returns (id, number)."""
    year = int(draft["issue_date"][:4])
    with db.immediate() as cur:
        entity = cur.execute(
            "SELECT * FROM legal_entity WHERE id = ?", (draft["legal_entity_id"],)
        ).fetchone()
        if draft["kind"] == "invoice" and draft.get("reservation_id"):
            _check_stay_limit(cur, draft["reservation_id"])
        seq_year, seq_no, number, vs = allocate_number(cur, entity, year)
        columns = _invoice_columns(draft, number, vs, seq_year, seq_no)
        cur.execute(
            f"INSERT INTO invoice ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)}) "
            "RETURNING id",
            list(columns.values()),
        )
        invoice_id = int(cur.fetchall()[0][0])
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


def retention_cutoff(today: date) -> date:
    """Issued before this date means the 10 years have run (§ 35 zákon 235/2004 Sb.).

    Ten years from the end of the calendar year of issue: a 2015 invoice is
    kept through 31 December 2025 and goes from 1 January 2026.
    """
    return date(today.year - 10, 1, 1)


def expired_ids(today: date, owner_user_id: Optional[int] = None) -> List[int]:
    """Issued documents past the 10-year rule; ``None`` means every workspace.

    An original whose correction is still inside its own ten years stays: the
    correction points at it and has to remain readable. Corrections come first
    in the list so a batch that holds both deletes them in a valid order.
    """
    cutoff = retention_cutoff(today).isoformat()
    return [
        r["id"]
        for r in db.query(
            "SELECT id FROM invoice WHERE issue_date < ? "
            "AND (? IS NULL OR owner_user_id = ?) "
            "AND NOT EXISTS (SELECT 1 FROM invoice c "
            "                WHERE c.corrects_invoice_id = invoice.id AND c.issue_date >= ?) "
            "ORDER BY CASE WHEN corrects_invoice_id IS NULL THEN 1 ELSE 0 END, id",
            (cutoff, owner_user_id, owner_user_id, cutoff),
        )
    ]


def purge_expired(today: date, owner_user_id: Optional[int] = None) -> int:
    """Delete issued documents past the 10-year rule, with the unlock flag."""
    ids = expired_ids(today, owner_user_id)
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
