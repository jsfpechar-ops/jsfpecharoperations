"""Local stay fee (poplatek z pobytu): host-declared rate, one total per stay.

See docs/plans/PLAN_POPLATEK_Z_POBYTU.md. The host types a rate per property
(0 = off); UbyHost multiplies it by nights and people, excludes minors and long
stays, and shows the guest one total with one QR. It never files anything and
never checks a payment — the host marks the stay paid.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from . import db, payments, reporting, validation

MAX_CALENDAR_DAYS = 60   # zákon 565/1990 §3a: stays longer than this are not subject
ADULT_AGE = 18           # §3b(1)(b)
MAX_RATE_CZK = 50        # §3d
VS_PREFIX = "8"
CLAIM_CODES = ("disability_card", "local_resident", "other")
DECISIONS = ("exempt", "charge")


def is_active(apartment) -> bool:
    return bool(apartment) and int(apartment["stay_fee_rate_czk"] or 0) > 0


def shows_to_guest(apartment) -> bool:
    return is_active(apartment) and (apartment["stay_fee_policy"] or "on") == "on"


def conservative_birth(raw) -> Optional[date]:
    """Earliest possible birthday, so an unknown day/month never makes someone a minor."""
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


def stay_rate(reservation, apartment) -> int:
    return int(reservation["stay_fee_rate_czk"] or apartment["stay_fee_rate_czk"] or 0)


def snapshot_rate(reservation_id: int) -> None:
    """Freeze the property's current rate on the stay, once."""
    db.execute(
        "UPDATE reservation SET stay_fee_rate_czk = "
        "(SELECT a.stay_fee_rate_czk FROM apartment a WHERE a.id = reservation.apartment_id) "
        "WHERE id = ? AND stay_fee_rate_czk IS NULL",
        (reservation_id,),
    )


def stay_vs(reservation_id: int) -> str:
    return VS_PREFIX + str(reservation_id).zfill(9)


def person_fee(guest, reservation, rate: int) -> Dict[str, Any]:
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    end = validation.parse_iso_date(guest["stay_to"] or reservation["date_to"])
    nights = max((end - start).days, 0) if start and end else 0
    decision = guest["fee_host_decision"]
    if decision == "exempt":
        charged, reason = 0, "host_exempt"
    elif decision == "charge":
        charged, reason = nights, None
    elif nights + 1 > MAX_CALENDAR_DAYS:
        charged, reason = 0, "over_60_days"
    else:
        birth = conservative_birth(guest["birth_date"])
        minor = bool(birth and start and validation.age_on(birth, start) < ADULT_AGE)
        charged, reason = (0, "under_18") if minor else (nights, None)
    return {
        "guest_id": guest["id"],
        "nights": nights,
        "charged_nights": charged,
        "amount_czk": charged * rate,
        "reason": reason,
        "claim": guest["fee_claim"],
        "host_decision": decision,
        "host_reason": guest["fee_host_reason"] or "",
    }


def stay_summary(reservation, apartment) -> Optional[Dict[str, Any]]:
    """None when the feature never applied to this stay."""
    if not is_active(apartment) and not int(reservation["stay_fee_rate_czk"] or 0):
        return None
    rate = stay_rate(reservation, apartment)
    guests = db.query(
        "SELECT * FROM guest WHERE reservation_id = ? ORDER BY id", (reservation["id"],)
    )
    people = [person_fee(g, reservation, rate) for g in guests if reporting.guest_has_signature(g)]
    return {
        "rate_czk": rate,
        "people": people,
        "total_czk": sum(p["amount_czk"] for p in people),
        "vs": stay_vs(reservation["id"]),
        "paid_at": reservation["stay_fee_paid_at"],
        "paid_amount_czk": reservation["stay_fee_paid_amount_czk"],
    }


def format_czk(amount: int) -> str:
    return f"{amount:,}".replace(",", "\u00a0")      # 1 200 with a no-break space


def payment_details(reservation, apartment, summary) -> Dict[str, Any]:
    """The host's payment options for one stay, used by the guest card and mail."""
    entity = (
        db.query_one("SELECT * FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
        if apartment["legal_entity_id"] else None
    )
    iban = (entity["iban"] or "") if entity else ""
    vs = summary["vs"]
    return {
        "iban": iban,
        "iban_display": payments.format_iban(iban) if iban else "",
        "account": (entity["bank_account"] or "") if entity and "/" in (entity["bank_account"] or "") else "",
        "bic": (entity["bic"] or "") if entity else "",
        "beneficiary": (entity["name"] or "") if entity else "",
        "vs": vs,
        "reference": payments.ascii_upper(f"POPLATEK Z POBYTU {vs}", 60),
        "amount_plain": str(summary["total_czk"]),
        "payment_link": apartment["stay_fee_payment_link"] or "",
        "cash": bool(apartment["stay_fee_cash"]),
    }


def mail_details(reservation, apartment) -> Optional[Dict[str, Any]]:
    """The fee facts for the completion e-mail, or None when there is nothing to pay."""
    if not shows_to_guest(apartment):
        return None
    summary = stay_summary(reservation, apartment)
    if not summary or summary["total_czk"] <= 0 or summary["paid_at"]:
        return None
    return {
        "total": format_czk(summary["total_czk"]),
        **payment_details(reservation, apartment, summary),
    }
