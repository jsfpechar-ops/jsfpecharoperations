"""Místní poplatek z pobytu: a host-only calculator for the council report.

Guests never see any of this. The host sets a rate and the council details on a
property once; each period UbyHost counts the liable and exempt lůžkodny
(person-nights) of signed guests and renders the hlášení on demand. Nothing is
stored except the host's per-guest decision and the template fields.

The rules, in one place (zákon č. 565/1990 Sb.):

* Base = commenced days after arrival through departure (§3c), i.e. (arrival, departure].
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
EXEMPT_CATEGORIES = (
    "disability",
    "diplomat",
    "local_rule",
    "other_statutory",
)
SCOPE_RULES = ("calendar_days", "nights")
THRESHOLD_NIGHTS = 60

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


def counted_days_in(start: date, end: date, first: date, last: date) -> int:
    """Days in (arrival, departure] that fall inside first..last inclusive."""
    first_day = start + timedelta(days=1)
    if end < first_day:
        return 0
    lo = max(first_day, first)
    hi = min(end, last)
    return max((hi - lo).days + 1, 0)


def nights_in(start: date, end: date, first: date, last: date) -> int:
    """Alias kept for tests and PDF copy that still say lůžkodny."""
    return counted_days_in(start, end, first, last)


def _day_liability(guest, decision: Optional[str], day: date) -> str:
    if decision == "exempt":
        return "exempt"
    birth = conservative_birth(guest["birth_date"])
    minor = bool(birth and validation.age_on(birth, day) < ADULT_AGE)
    if decision == "charge":
        return "exempt" if minor else "liable"
    return "exempt" if minor else "liable"


def format_czk(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Kč"


# --- per guest --------------------------------------------------------------

def guest_period(guest, reservation, first: date, last: date) -> Optional[Dict[str, Any]]:
    """One guest's share of one period, or None when no counted day falls in it."""
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    end = validation.parse_iso_date(guest["stay_to"] or reservation["date_to"])
    if not start or not end or end <= start:
        return None
    stay_nights = (end - start).days
    decision = guest["fee_host_decision"] if guest["fee_host_decision"] in DECISIONS else None
    if stay_nights > THRESHOLD_NIGHTS:
        status = "not_subject"
    else:
        status = "liable"
    liable = exempt = 0
    auto_minor = False
    d = start + timedelta(days=1)
    while d <= end:
        if first <= d <= last:
            if status == "not_subject":
                pass
            else:
                day_status = _day_liability(guest, decision, d)
                if day_status == "liable":
                    liable += 1
                else:
                    exempt += 1
                    if decision is None:
                        birth = conservative_birth(guest["birth_date"])
                        if birth and validation.age_on(birth, d) < ADULT_AGE:
                            auto_minor = True
        d += timedelta(days=1)
    days = liable + exempt
    if days <= 0 and status != "not_subject":
        return None
    if status == "not_subject":
        days = counted_days_in(start, end, first, last)
        liable = exempt = 0
    elif exempt and not liable:
        status = "exempt"
    elif liable:
        status = "liable"
    reason = guest["fee_host_reason"] or ""
    if guest.get("fee_host_reason_enc"):
        reason = db.decrypt_field(guest["fee_host_reason_enc"]) or reason
    return {
        "guest_id": guest["id"],
        "stay_from": start.isoformat(),
        "stay_to": end.isoformat(),
        "nights": days,
        "liable_nights": liable,
        "exempt_nights": exempt,
        "status": status,
        "auto_minor": auto_minor and status == "exempt",
        "decision": decision,
        "reason": reason,
        "threshold_nights": stay_nights == THRESHOLD_NIGHTS,
    }


# --- per property -----------------------------------------------------------

_GUESTS_SQL = (
    "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id "
    "FROM guest g JOIN reservation r ON r.id = g.reservation_id "
    "WHERE r.apartment_id = ? AND r.status = 'active' AND g.archived_at IS NULL "
    "AND COALESCE(g.stay_from, r.date_from) <= ? AND COALESCE(g.stay_to, r.date_to) > ? "
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)


def property_period(apartment, month: date, *, live_only: bool = False) -> Optional[Dict[str, Any]]:
    """Figures for one property and the period (of its cadence) containing month."""
    cadence = cadence_of(apartment)
    if not live_only:
        from . import stay_fee_filing

        key = stay_fee_filing.period_key(cadence, month)
        row = stay_fee_filing.latest(apartment["id"], key)
        if row:
            return stay_fee_filing.frozen_summary(row, apartment)
    if not is_active(apartment):
        return None
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


def report_group(apartment, month: date, *, live_only: bool = False) -> Dict[str, Any]:
    """One hlášení and register per facility (§3g), even when VS is shared."""
    vs = vs_of(apartment)
    period = property_period(apartment, month, live_only=live_only)
    periods = [period] if period else []
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
    """Host-UI keys that block finalization (empty list = ready to save)."""
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
    for period in group["periods"]:
        issues.extend(_period_line_issues(anchor, period))
    return list(dict.fromkeys(issues))


def _period_line_issues(apartment, period) -> List[str]:
    issues: List[str] = []
    for line in period.get("lines") or []:
        if line.get("threshold_nights"):
            rule = (apartment["stay_fee_scope_rule"] or "").strip()
            ref = (apartment["stay_fee_scope_reference"] or "").strip()
            if rule not in SCOPE_RULES or len(ref) < 3:
                issues.append("stay_fees.issue.scope_ruling")
    return issues


def unsigned_stays(apartment_id: int, first: date, last: date) -> int:
    rows = db.query(
        "SELECT g.* FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "WHERE r.apartment_id = ? AND r.status = 'active' AND g.archived_at IS NULL "
        "AND COALESCE(g.stay_from, r.date_from) <= ? AND COALESCE(g.stay_to, r.date_to) > ?",
        (apartment_id, last.isoformat(), first.isoformat()),
    )
    return sum(1 for row in rows if not reporting.guest_has_signature(row))


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
            row["exempt_reason"] = (row["exempt_reason"] + f"; {RESTRICTED_NOTE}").strip("; ")
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
