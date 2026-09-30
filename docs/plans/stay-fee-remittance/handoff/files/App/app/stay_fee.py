"""Místní poplatek z pobytu: a host-only calculator for the council report.

Guests never see any of this. The host sets a rate and the council details on a
property once; each period UbyHost counts the liable and exempt lůžkodny
(person-nights) of signed guests and renders the hlášení on demand. Nothing is
stored except the host's per-guest decision and the template fields.

The rules, in one place (zákon č. 565/1990 Sb.):

* Base = nights ("Lůžkoden = osoba × počet nocí", the councils' own form note;
  = "započaté dny s výjimkou dne počátku", §3c).
* A night belongs to the period its date falls in (the night of 31 Aug counts
  in August, the night of 1 Sep in September). Praha 1: "na konci měsíce je
  nutné spočítat dny a přiřadit je do správného měsíce".
* Out of scope (§3a): a stay longer than 60 consecutive calendar days, i.e.
  nights + 1 > 60. Such a stay is neither liable nor exempt; it is not counted.
* Exempt: under 18 on the arrival day (§3b(1)(b)), or the host chose
  ``exempt`` (with a reason). ``charge`` forces liable - the correction for a
  wrong birth date, never a way to charge a real minor.
* Counted guests: a signed form, on an active stay, not archived.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from . import db, payments, reporting, validation

MAX_RATE_CZK = 50        # §3d
MAX_CALENDAR_DAYS = 60   # §3a
ADULT_AGE = 18           # §3b(1)(b)
CADENCES = ("monthly", "quarterly")
DECISIONS = ("exempt", "charge")
REASON_MAX = 120

MONTHS_CS = ("Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec",
             "Srpen", "Září", "Říjen", "Listopad", "Prosinec")
DOC_TYPE_LABELS_CS = {
    "op": "Občanský průkaz",
    "pas": "Cestovní pas",
    "prechodny_pobyt": "Potvrzení o přechodném pobytu",
    "pobytova_karta_eu": "Pobytová karta rodinného příslušníka občana EU",
    "povoleni_pobyt": "Průkaz o povolení k pobytu",
    "povoleni_pobyt_cizinec": "Průkaz o povolení k pobytu pro cizince",
    "trvaly_pobyt": "Průkaz o povolení k trvalému pobytu",
    "zadatel_mezinarodni_ochrana": "Průkaz žadatele o mezinárodní ochranu",
    "zadatel_docasna_ochrana": "Průkaz žadatele o dočasnou ochranu",
}


# --- pure helpers -----------------------------------------------------------

def is_active(apartment) -> bool:
    return bool(apartment) and int(apartment["stay_fee_rate_czk"] or 0) > 0


def clamp_rate(raw) -> int:
    text = str(raw or "").strip()
    return max(0, min(int(text), MAX_RATE_CZK)) if text.isdigit() else 0


def cadence_of(apartment) -> str:
    value = apartment["stay_fee_cadence"] or "monthly"
    return value if value in CADENCES else "monthly"


def default_doc_type(nationality: Optional[str]) -> str:
    return "op" if (nationality or "").upper() == validation.CZECH_CODE else "pas"


def doc_type_of(guest) -> str:
    stored = guest["doc_type"]
    return stored if stored in validation.DOC_TYPES else default_doc_type(guest["nationality"])


def conservative_birth(raw) -> Optional[date]:
    """The earliest possible birthday, so an unknown day or month never makes
    an adult look like a minor. ``00000000`` returns None (treated as adult)."""
    digits = validation.normalise_birth_date(raw)
    if len(digits) != 8 or not digits.isdigit():
        return None
    day, month, year = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if year == 0:
        return None
    try:
        return date(year, month or 1, day or 1)
    except ValueError:
        return None


def parse_month(value: Optional[str]) -> Optional[date]:
    """'2026-08' -> date(2026, 8, 1); anything else -> None."""
    text = (value or "").strip()
    if len(text) != 7 or text[4] != "-" or not (text[:4] + text[5:]).isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[5:]), 1)
    except ValueError:
        return None


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def shift_month(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def previous_month(today: date) -> date:
    return shift_month(today.replace(day=1), -1)


def period_bounds(cadence: str, month: date) -> Tuple[date, date]:
    """(first, last) inclusive of the monthly or quarterly period containing month."""
    if cadence == "quarterly":
        first = date(month.year, (month.month - 1) // 3 * 3 + 1, 1)
        after = shift_month(first, 3)
    else:
        first = month.replace(day=1)
        after = shift_month(first, 1)
    return first, after - timedelta(days=1)


def period_label_cs(cadence: str, month: date) -> str:
    """'Srpen 2026' or '3. čtvrtletí 2026' (the PDF and the Czech UI)."""
    if cadence == "quarterly":
        return f"{(month.month - 1) // 3 + 1}. čtvrtletí {month.year}"
    return f"{MONTHS_CS[month.month - 1]} {month.year}"


def period_complete(cadence: str, month: date, today: date) -> bool:
    return period_bounds(cadence, month)[1] < today


def nights_in(start: date, end: date, first: date, last: date) -> int:
    """Nights of a start..end stay (night n: arrival <= n < departure) inside first..last."""
    lo = max(start, first)
    hi = min(end - timedelta(days=1), last)
    return max((hi - lo).days + 1, 0)


def format_czk(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Kč"


# --- per guest --------------------------------------------------------------

def guest_period(guest, reservation, first: date, last: date) -> Optional[Dict[str, Any]]:
    """One guest's share of one period, or None when no night falls in it."""
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    end = validation.parse_iso_date(guest["stay_to"] or reservation["date_to"])
    if not start or not end or end <= start:
        return None
    nights = nights_in(start, end, first, last)
    if nights <= 0:
        return None
    total_nights = (end - start).days
    decision = guest["fee_host_decision"] if guest["fee_host_decision"] in DECISIONS else None
    if total_nights + 1 > MAX_CALENDAR_DAYS:
        status = "not_subject"                    # §3a scope limit, not an exemption
    elif decision == "exempt":
        status = "exempt"
    elif decision == "charge":
        status = "liable"
    else:
        birth = conservative_birth(guest["birth_date"])
        minor = bool(birth and validation.age_on(birth, start) < ADULT_AGE)
        status = "exempt" if minor else "liable"
    return {
        "guest_id": guest["id"],
        "stay_from": start.isoformat(),
        "stay_to": end.isoformat(),
        "nights": nights,
        "liable_nights": nights if status == "liable" else 0,
        "exempt_nights": nights if status == "exempt" else 0,
        "status": status,
        "auto_minor": status == "exempt" and decision is None,
        "decision": decision,
        "reason": guest["fee_host_reason"] or "",
    }


# --- per property -----------------------------------------------------------

_GUESTS_SQL = (
    "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id "
    "FROM guest g JOIN reservation r ON r.id = g.reservation_id "
    "WHERE r.apartment_id = ? AND r.status = 'active' AND g.archived_at IS NULL "
    "AND COALESCE(g.stay_from, r.date_from) <= ? AND COALESCE(g.stay_to, r.date_to) > ? "
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)


def property_period(apartment, month: date) -> Optional[Dict[str, Any]]:
    """Figures for one property and the period (of its cadence) containing month."""
    if not is_active(apartment):
        return None
    cadence = cadence_of(apartment)
    first, last = period_bounds(cadence, month)
    rate = int(apartment["stay_fee_rate_czk"])
    lines: List[Dict[str, Any]] = []
    for row in db.query(_GUESTS_SQL, (apartment["id"], last.isoformat(), first.isoformat())):
        if not reporting.guest_has_signature(row):
            continue
        share = guest_period(row, {"date_from": row["res_from"], "date_to": row["res_to"]},
                             first, last)
        if share is None:
            continue
        share.update({
            "reservation_id": row["res_id"],
            "name": f"{row['first_name'] or ''} {row['surname'] or ''}".strip(),
            "restricted": bool(row["restricted_at"]),
            "amount_czk": share["liable_nights"] * rate,
        })
        lines.append(share)
    liable = sum(line["liable_nights"] for line in lines)
    return {
        "apartment": apartment,
        "cadence": cadence,
        "first": first,
        "last": last,
        "label": period_label_cs(cadence, month),
        "rate_czk": rate,
        "lines": lines,
        "liable_nights": liable,
        "exempt_nights": sum(line["exempt_nights"] for line in lines),
        "total_czk": liable * rate,
    }


def owner_periods(owner_user_id, month: date) -> List[Dict[str, Any]]:
    """The list page: every non-archived property with a rate > 0."""
    rows = db.query(
        "SELECT * FROM apartment WHERE owner_user_id IS ? AND archived_at IS NULL "
        "AND stay_fee_rate_czk > 0 ORDER BY internal_name, id",
        (owner_user_id,),
    )
    return [property_period(row, month) for row in rows]


# --- the report (one hlášení = one payer + one VS) --------------------------

def vs_of(apartment) -> str:
    return "".join(ch for ch in (apartment["stay_fee_vs"] or "") if ch.isdigit())


def report_group(apartment, month: date) -> Dict[str, Any]:
    """The hlášení the property belongs to.

    A payer files one hlášení per variabilní symbol, so every active property
    of the same legal entity with the same VS and cadence is summed into it.
    Without a VS the property stands alone (and the report is blocked).
    """
    vs = vs_of(apartment)
    members = [apartment]
    if vs and apartment["legal_entity_id"]:
        members = [
            row for row in db.query(
                "SELECT * FROM apartment WHERE owner_user_id IS ? AND legal_entity_id = ? "
                "AND archived_at IS NULL AND stay_fee_rate_czk > 0 ORDER BY internal_name, id",
                (apartment["owner_user_id"], apartment["legal_entity_id"]),
            )
            if vs_of(row) == vs and cadence_of(row) == cadence_of(apartment)
        ] or [apartment]
    periods = [property_period(row, month) for row in members]
    periods = [p for p in periods if p]
    cadence = cadence_of(apartment)
    first, last = period_bounds(cadence, month)
    return {
        "anchor": apartment,
        "vs": vs,
        "cadence": cadence,
        "first": first,
        "last": last,
        "label": period_label_cs(cadence, month),
        "periods": periods,
        "liable_nights": sum(p["liable_nights"] for p in periods),
        "exempt_nights": sum(p["exempt_nights"] for p in periods),
        "total_czk": sum(p["total_czk"] for p in periods),
    }


def report_issues(group, today: date) -> List[str]:
    """Host-UI keys that block the PDF (empty list = ready)."""
    anchor = group["anchor"]
    issues = []
    if not period_complete(group["cadence"], group["first"], today):
        issues.append("stay_fees.issue.period_running")
    if not group["vs"]:
        issues.append("stay_fees.issue.no_vs")
    if not (anchor["stay_fee_authority_name"] or "").strip():
        issues.append("stay_fees.issue.no_authority")
    entity = (db.query_one("SELECT * FROM legal_entity WHERE id = ?", (anchor["legal_entity_id"],))
              if anchor["legal_entity_id"] else None)
    if not entity or not (entity["name"] or "").strip():
        issues.append("stay_fees.issue.no_payer")
    return issues


def payment_details(group) -> Optional[Dict[str, Any]]:
    """Host-facing payment panel + QR Platba. None when the council account is unset."""
    anchor = group["anchor"]
    iban = anchor["stay_fee_council_iban"] or ""
    if not iban:
        return None
    payload = ""
    if group["vs"] and group["total_czk"] > 0:
        payload = payments.spayd(iban, group["total_czk"], group["vs"],
                                 f"POPLATEK Z POBYTU {group['vs']}")
    return {
        "account": anchor["stay_fee_council_account"] or "",
        "iban": iban,
        "iban_display": payments.format_iban(iban),
        "vs": group["vs"],
        "spayd": payload,
        "qr": payments.qr_data_uri(payload) if payload else "",
    }


def property_address(apartment) -> str:
    number = "/".join(p for p in (apartment["addr_house_no"] or "", apartment["addr_orient_no"] or "") if p)
    street = " ".join(p for p in (apartment["addr_street"] or "", number) if p)
    town = " ".join(p for p in (apartment["addr_zip"] or "", apartment["addr_obec"] or "") if p)
    return ", ".join(p for p in (street, town) if p)


EXEMPT_LABEL_MINOR = "Mladší 18 let"
EXEMPT_LABEL_HOST = "Osvobozeno ubytovatelem (důvod v evidenční knize)"


def hlaseni(group, issued_on: date) -> Dict[str, Any]:
    """The report object ``stay_fee_remittance_pdf.render`` draws (Invoice companion design)."""
    anchor = group["anchor"]
    entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (anchor["legal_entity_id"],))
    signature_png = db.decrypt_field(entity["signature_png_enc"]) if entity["signature_png_enc"] else ""
    rows, minors, hosts = [], {"count": 0, "nights": 0}, {"count": 0, "nights": 0}
    for period in group["periods"]:
        rows.append({
            "property_name": period["apartment"]["internal_name"],
            "property_address": property_address(period["apartment"]),
            "liable_nights": period["liable_nights"],
            "rate_czk": period["rate_czk"],
            "amount_czk": period["total_czk"],
        })
        for line in period["lines"]:
            if line["status"] == "exempt":
                bucket = minors if line["auto_minor"] else hosts
                bucket["count"] += 1
                bucket["nights"] += line["exempt_nights"]
    not_charged = [
        {"reason": label, **bucket}
        for label, bucket in ((EXEMPT_LABEL_MINOR, minors), (EXEMPT_LABEL_HOST, hosts))
        if bucket["count"]
    ]
    return {
        "payer_name": entity["name"],
        "payer_seat": entity["seat"] or "",
        "payer_ico": entity["ico"] or "",
        "payer_contact": entity["contact_email"] or "",
        "vs": group["vs"],
        "recipient_name": anchor["stay_fee_authority_name"] or "",
        "recipient_address": anchor["stay_fee_authority_address"] or "",
        "recipient_contact": anchor["stay_fee_authority_contact"] or "",
        "payee": (anchor["stay_fee_payee"] or "").strip(),
        "instruction": anchor["stay_fee_instruction"] or "",
        "cadence": group["cadence"],
        "period_start": group["first"].isoformat(),
        "period_end": group["last"].isoformat(),
        "issued_on": issued_on.isoformat(),
        "rows": rows,
        "liable_nights": group["liable_nights"],
        "exempt_nights": group["exempt_nights"],
        "total_czk": group["total_czk"],
        "not_charged": not_charged,
        "signature_png": signature_png or "",
        "signature_name": entity["signature_name"] or "",
    }


# --- the register (evidenční kniha, §3g) ------------------------------------

REGISTER_COLUMNS = (
    ("property", "Zařízení"), ("period", "Období"),
    ("stay_from", "Den počátku pobytu"), ("stay_to", "Den konce pobytu"),
    ("surname", "Příjmení"), ("first_name", "Jméno"),
    ("home_address", "Adresa místa přihlášení / v zahraničí"), ("birth_date", "Datum narození"),
    ("doc_type", "Druh průkazu"), ("doc_number", "Číslo průkazu"),
    ("nights", "Nocí v období"), ("rate_czk", "Sazba (Kč)"),
    ("amount_czk", "Poplatek (Kč)"), ("exempt_reason", "Důvod osvobození"),
    ("vs", "Variabilní symbol"), ("council_account", "Účet obce"),
)
RESTRICTED_NOTE = "zpracování omezeno (čl. 18 GDPR)"


def register_rows(period) -> List[Dict[str, Any]]:
    apartment = period["apartment"]
    rows = []
    for line in period["lines"]:
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (line["guest_id"],))
        if line["status"] == "exempt":
            reason = line["reason"] or ("mladší 18 let" if line["auto_minor"] else "")
        elif line["status"] == "not_subject":
            reason = "pobyt delší než 60 dnů (není předmětem poplatku)"
        else:
            reason = ""
        row = {
            "property": apartment["internal_name"],
            "period": period["label"],
            "stay_from": validation.fmt_date(line["stay_from"]),
            "stay_to": validation.fmt_date(line["stay_to"]),
            "surname": guest["surname"] or "",
            "first_name": guest["first_name"] or "",
            "home_address": validation.compose_residence(
                guest["res_street"] or "", guest["res_city"] or "", (guest["res_country"] or "").upper()
            ),
            "birth_date": validation.format_birth_date(guest["birth_date"]),
            "doc_type": DOC_TYPE_LABELS_CS[doc_type_of(guest)],
            "doc_number": ("zapsán v dokladu rodiče" if guest["doc_number"] == validation.INPASS
                           else guest["doc_number"] or ""),
            "nights": line["nights"],
            "rate_czk": period["rate_czk"],
            "amount_czk": line["amount_czk"],
            "exempt_reason": reason,
            "vs": vs_of(apartment),
            "council_account": apartment["stay_fee_council_account"] or "",
        }
        if line["restricted"]:
            for key in ("first_name", "home_address", "birth_date", "doc_number"):
                row[key] = ""
            row["surname"] = RESTRICTED_NOTE
        rows.append(row)
    return rows


def register_csv(rows: List[Dict[str, Any]]) -> bytes:
    """';'-separated, UTF-8 with BOM, like housebook.housebook_csv."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _, label in REGISTER_COLUMNS])
    for row in rows:
        writer.writerow([row[key] for key, _ in REGISTER_COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
