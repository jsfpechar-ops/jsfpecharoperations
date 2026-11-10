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
* Out of scope (§3a): more than 60 nights. A stay of exactly 60 nights (61
  calendar days) follows the facility's recorded council ruling:
  ``calendar_days`` excludes it, ``nights`` counts it. With no ruling the stay
  is still calculated and finalization is blocked.
* Exempt: under 18 on the arrival day (§3b(1)(b)), or the host chose
  ``exempt`` (with a reason). ``charge`` forces liable - the correction for a
  wrong birth date, never a way to charge a real minor.
* Counted guests: on an active stay, not archived. A missing signature does not
  drop a guest from the fee (the fee follows the stay); it only raises the
  ``unsigned`` flag.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from . import alerts, config, db, payments, reporting, stay_fee_rate, validation
from .csv_safety import csv_safe

MAX_RATE_CZK = 50        # §3d
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


RAIL_ORDER = ("iban", "revolut", "cash")
NO_PAY_WAY_KIND = "stay_fee_no_pay_way"


def payout_account(apartment) -> Tuple[str, str]:
    """(account, payee) of the operator guests pay, or ("", "") when none is on file."""
    account = ""
    payee = ""
    if apartment["legal_entity_id"]:
        entity = db.query_one(
            "SELECT iban, bank_account, name FROM legal_entity WHERE id = ?",
            (apartment["legal_entity_id"],),
        )
        if entity is not None:
            payee = (entity["name"] or "").strip()
            if entity["iban"]:
                account = entity["iban"]
            elif entity["bank_account"]:
                try:
                    account = payments.normalise_account(entity["bank_account"])[1]
                except ValueError:
                    # Same as guest_pay_ways: a malformed stored account is
                    # not a pay way. Raising here 500s the guest hub and the
                    # host save that reconciles the no-pay-way alert.
                    account = ""
    return account, payee


def usable_rail_keys(apartment) -> List[str]:
    """The guest pay ways that work for this property, in the order the guest sees them.

    The one rule for the guest pay box and for the host alert (brief 1071).
    A stored "qr" is the bank rail. A way works when it is enabled and has what it needs:
    bank transfer an account, Revolut a link; cash needs nothing.
    """
    enabled = {part for part in (apartment["stay_fee_guest_rails"] or "").split(",") if part}
    if "qr" in enabled:
        enabled.add("iban")
    first = apartment["stay_fee_guest_default_rail"] or ""
    if first == "qr":
        first = "iban"
    order = ([first] if first in RAIL_ORDER else []) + [key for key in RAIL_ORDER if key != first]
    account, _payee = payout_account(apartment)
    usable = []
    for key in order:
        if key not in enabled:
            continue
        if key == "iban" and not account:
            continue
        if key == "revolut" and not apartment["stay_fee_guest_revolut_link"]:
            continue
        usable.append(key)
    return usable


def no_pay_way(apartment) -> bool:
    """Collection is on, the fee is active, the deployment asks guests to pay, and no way works."""
    return (
        bool(apartment["stay_fee_collect"])
        and is_active(apartment)
        and bool(config.STAY_FEE_GUEST_PAY)
        and not apartment["archived_at"]
        and not usable_rail_keys(apartment)
    )


def reconcile_no_pay_way_alert(apartment_id: int) -> None:
    """Raise the host alert while no pay way works; resolve it as soon as one does or collection is off."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    key = f"{NO_PAY_WAY_KIND}:{apartment_id}"
    if apartment is None or not no_pay_way(apartment):
        alerts.resolve(key)
        return
    alerts.raise_alert(
        "warning",
        NO_PAY_WAY_KIND,
        "Guests cannot pay the stay fee: add a bank account",
        "",
        dedupe_key=key,
        apartment_id=apartment_id,
        params={"property": apartment["internal_name"]},
    )


def reconcile_all_no_pay_way() -> int:
    """Daily sweep: re-check every property that collects, and every open alert of this kind."""
    ids = {
        row["id"]
        for row in db.query("SELECT id FROM apartment WHERE stay_fee_collect = 1 AND archived_at IS NULL")
    }
    ids |= {
        row["apartment_id"]
        for row in db.query(
            "SELECT apartment_id FROM alert WHERE kind = ? AND resolved_at IS NULL AND apartment_id IS NOT NULL",
            (NO_PAY_WAY_KIND,),
        )
    }
    for apartment_id in ids:
        reconcile_no_pay_way_alert(apartment_id)
    return len(ids)


def parse_czk_int(raw) -> Optional[int]:
    """Non-negative integer from ASCII digits only.

    ``str.isdigit()`` is true for characters such as ``²``, which ``int()`` rejects.
    """
    text = str(raw or "").strip()
    if not text.isascii() or not text.isdigit():
        return None
    return int(text)


def clamp_rate(raw) -> int:
    value = parse_czk_int(raw)
    if value is None:
        return 0
    return max(0, min(value, MAX_RATE_CZK))


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
        month = date(int(text[:4]), int(text[5:]), 1)
    except ValueError:
        return None
    # Earlier years only come from a crafted link and break month arithmetic.
    return month if month.year >= 2000 else None


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


def _day_liability(guest, decision: Optional[str], day: date, birth: Optional[date] = None) -> str:
    if decision == "exempt":
        return "exempt"
    if birth is None and decision != "exempt":
        birth = conservative_birth(guest["birth_date"])
    minor = bool(birth and validation.age_on(birth, day) < ADULT_AGE)
    if decision == "charge":
        return "exempt" if minor else "liable"
    return "exempt" if minor else "liable"


def format_czk(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " Kč"


# --- same-obec residence (0898) ---------------------------------------------
# Backend only. Exact match after folding; statutory-city district suffix dropped
# ("Praha 5", "Praha-Smichov"); Prague folds to Praha. Anything else, a typo
# included, is not exempt: the form is the guest's own declaration.

STATUTORY_DISTRICT_BASES = (
    "PRAHA", "BRNO", "CESKE BUDEJOVICE", "DECIN", "FRYDEK-MISTEK", "HAVIROV",
    "HRADEC KRALOVE", "CHOMUTOV", "JABLONEC NAD NISOU", "JIHLAVA", "KARLOVY VARY",
    "KARVINA", "KLADNO", "LIBEREC", "MLADA BOLESLAV", "MOST", "OLOMOUC", "OPAVA",
    "OSTRAVA", "PARDUBICE", "PLZEN", "PROSTEJOV", "PREROV", "TEPLICE", "TRINEC",
    "USTI NAD LABEM", "ZLIN",
)
# Names guests type for Czech towns -> the Czech name, folded (1031, owner list).
OBEC_ALIASES = {
    "PRAGUE": "PRAHA", "PRAG": "PRAHA",
    "BRUNN": "BRNO", "PILSEN": "PLZEN", "BUDWEIS": "CESKE BUDEJOVICE",
    "OSTRAU": "OSTRAVA", "MAHRISCH OSTRAU": "OSTRAVA", "MAHRISCH-OSTRAU": "OSTRAVA",
    "MORAVIAN OSTRAVA": "OSTRAVA", "MORAVSKA OSTRAVA": "OSTRAVA",
    "KARLSBAD": "KARLOVY VARY", "CARLSBAD": "KARLOVY VARY",
    "MARIENBAD": "MARIANSKE LAZNE", "FRANZENSBAD": "FRANTISKOVY LAZNE",
    "OLMUTZ": "OLOMOUC", "REICHENBERG": "LIBEREC", "AUSSIG": "USTI NAD LABEM",
    "KONIGGRATZ": "HRADEC KRALOVE", "PARDUBITZ": "PARDUBICE", "IGLAU": "JIHLAVA",
    "TROPPAU": "OPAVA", "TEPLITZ": "TEPLICE", "KOMOTAU": "CHOMUTOV", "TETSCHEN": "DECIN",
    "JUNGBUNZLAU": "MLADA BOLESLAV", "GABLONZ": "JABLONEC NAD NISOU",
    "PROSSNITZ": "PROSTEJOV", "PRERAU": "PREROV", "BRUX": "MOST",
    "KRUMAU": "CESKY KRUMLOV", "KUTTENBERG": "KUTNA HORA", "ZNAIM": "ZNOJMO",
}
# The official long name of a statutory city; dropped only when such a city follows.
# Never "MESTO " or "OBEC " alone: "Město Albrechtice" is its own town.
OFFICIAL_PREFIXES = ("HLAVNI MESTO ", "HL. M. ", "HL.M. ", "HL M ", "STATUTARNI MESTO ")
# Okres (district) names that start with a city name but are not that city.
OKRES_NOT_OBEC = ("PRAHA-VYCHOD", "PRAHA-ZAPAD", "BRNO-VENKOV", "PLZEN-JIH", "PLZEN-SEVER")
# What may follow a city name in a city-part form. signature.js uses this same text.
OBEC_AFTER_BASE = r"$|\s*\d|-|\s*,|\s*\(| (?!(?:NAD|POD|U|NA|PRI)(?: |$))[A-Z]"
_AFTER_BASE = re.compile("(?:" + OBEC_AFTER_BASE + ")")
OBEC_SUFFIX_BASES = tuple(sorted(
    set(STATUTORY_DISTRICT_BASES)
    | {name for name, target in OBEC_ALIASES.items() if target in STATUTORY_DISTRICT_BASES},
    key=lambda name: (-len(name), name),
))
_OKRES_NEXT_LETTER = re.compile(r"[A-Z]")


def fold_text(value) -> str:
    """Diacritics, case and spacing folded (same approach as payments.ascii_upper)."""
    plain = unicodedata.normalize("NFKD", value or "")
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).upper()
    return re.sub(r"\s+", " ", plain).strip()


def _suffix_base(text: str) -> Optional[str]:
    for base in OBEC_SUFFIX_BASES:
        if text.startswith(base) and _AFTER_BASE.match(text, len(base)):
            return base
    return None


def _obec_key(value) -> str:
    """The town a typed name means, folded (1031 rules; signature.js key() mirrors this)."""
    # Any dash (en, em, minus) counts as "-": "Praha – Řepy" = "Praha-Řepy" (1031b).
    text = re.sub(r"\s*[-\u2010-\u2015\u2212]\s*", "-", fold_text(value))
    for prefix in OFFICIAL_PREFIXES:
        rest = text[len(prefix):].strip()
        if text.startswith(prefix) and _suffix_base(rest):
            text = rest
            break
    for name in OKRES_NOT_OBEC:
        if text.startswith(name) and not _OKRES_NEXT_LETTER.match(text[len(name):]):
            return text
    base = _suffix_base(text)
    if base:
        text = base
    return OBEC_ALIASES.get(text, text)


def property_obec(apartment) -> str:
    """The property's town: addr_obec, else the town the host typed in city_en (1031)."""
    for key in ("addr_obec", "city_en"):
        try:
            value = apartment[key]
        except (KeyError, IndexError):
            value = None
        if value and str(value).strip():
            return str(value)
    return ""


def same_obec_resident(guest, apartment) -> bool:
    """True only for a CZ resident whose city is the property's town (1031 folding rules)."""
    if guest["res_country"] != validation.CZECH_CODE:
        return False
    obec = _obec_key(property_obec(apartment))
    return bool(obec) and _obec_key(guest["res_city"]) == obec


# --- per guest --------------------------------------------------------------

def guest_period(guest, reservation, first: date, last: date,
                 apartment=None, schedule=None) -> Optional[Dict[str, Any]]:
    """One guest's share of one period, or None when no counted day falls in it.

    With ``apartment`` the same-obec rule applies (0898); without it the output is unchanged.
    """
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
    amount = 0
    by_rate: Dict[int, int] = {}
    auto_minor = False
    birth = conservative_birth(guest["birth_date"]) if decision is None else None
    # 0898: the host's decision always wins; the same-obec rule applies only with no decision.
    obec_auto = (apartment is not None and decision is None
                 and same_obec_resident(guest, apartment))
    d = max(start + timedelta(days=1), first)
    end_in_period = min(end, last)
    while d <= end_in_period:
        if status == "not_subject":
            pass
        else:
            day_status = "exempt" if obec_auto else _day_liability(guest, decision, d, birth)
            if day_status == "liable":
                liable += 1
                if schedule is not None:
                    night_rate = stay_fee_rate.rate_on(schedule, d)
                    amount += night_rate
                    by_rate[night_rate] = by_rate.get(night_rate, 0) + 1
            else:
                exempt += 1
                if decision is None and birth and validation.age_on(birth, d) < ADULT_AGE:
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
    # A row from the db helpers already carries the decrypted reason; decrypting
    # it a second time per guest and period was most of the list page's work.
    if guest.get("fee_host_reason_enc") and not db.is_decrypted(guest):
        reason = db.decrypt_field(guest["fee_host_reason_enc"]) or reason
    share = {
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
    if schedule is not None:
        share["amount_czk"] = amount
        share["rate_nights"] = sorted([r, n] for r, n in by_rate.items())
    if apartment is not None:
        share["auto_obec_resident"] = obec_auto and status == "exempt"
    return share


# --- per property -----------------------------------------------------------

_GUESTS_SQL = (
    "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id "
    "FROM guest g JOIN reservation r ON r.id = g.reservation_id "
    "WHERE r.apartment_id = ? AND r.status = 'active' AND g.archived_at IS NULL "
    # 0100: the setup guide's demo stay (demo.DEMO_STAY_SOURCE) owes no fee.
    "AND COALESCE(r.source, '') != 'demo' "
    "AND COALESCE(g.stay_from, r.date_from) <= ? AND COALESCE(g.stay_to, r.date_to) >= ? "
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)


def _scope_rule(apartment) -> str:
    try:
        return (apartment["stay_fee_scope_rule"] or "").strip()
    except (KeyError, IndexError):
        return ""


def _apply_scope_boundary(share: Dict[str, Any], apartment) -> None:
    """Apply a recorded 60-night ruling. Exactly 60 nights is 61 calendar days."""
    if not share.get("threshold_nights"):
        return
    if _scope_rule(apartment) != "calendar_days":
        return
    share["status"] = "not_subject"
    share["liable_nights"] = 0
    share["exempt_nights"] = 0
    share["auto_minor"] = False
    if "amount_czk" in share:
        share["amount_czk"] = 0
    if "rate_nights" in share:
        share["rate_nights"] = []
    if "auto_obec_resident" in share:
        share["auto_obec_resident"] = False


def property_period(
    apartment,
    month: date,
    *,
    live_only: bool = False,
    cadence: Optional[str] = None,
    rate: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Figures for one property and the period (of its cadence) containing month.

    ``rate`` overrides the property's current rate: a correction recalculates a
    sealed period at the rate it was sealed with, not at today's rate.
    """
    chosen = cadence if cadence in CADENCES else cadence_of(apartment)
    if not live_only:
        from . import stay_fee_filing

        row = stay_fee_filing.covering(apartment["id"], month)
        if row:
            return stay_fee_filing.frozen_summary(row, apartment)
    if not is_active(apartment):
        return None
    first, last = period_bounds(chosen, month)
    schedule = stay_fee_rate.flat(rate) if rate is not None else stay_fee_rate.schedule_for(apartment)
    rate = stay_fee_rate.rate_on(schedule, last)
    lines: List[Dict[str, Any]] = []
    # Counted in the same pass so the pages need not read (and decrypt) the
    # period's guests a second time for unsigned_stays().
    unsigned = 0
    for row in db.query(_GUESTS_SQL, (apartment["id"], last.isoformat(), first.isoformat())):
        if not reporting.guest_has_signature(row):
            unsigned += 1
        share = guest_period(row, {"date_from": row["res_from"], "date_to": row["res_to"]},
                             first, last, apartment=apartment, schedule=schedule)
        if share is None:
            continue
        _apply_scope_boundary(share, apartment)
        share.update({
            "reservation_id": row["res_id"],
            "name": f"{row['first_name'] or ''} {row['surname'] or ''}".strip(),
            "restricted": bool(row["restricted_at"]),
            "res_country": row["res_country"] or "",
            "res_city": row["res_city"] or "",
        })
        lines.append(share)
    liable = sum(line["liable_nights"] for line in lines)
    period = {
        "apartment": apartment,
        "cadence": chosen,
        "first": first,
        "last": last,
        "label": period_label_cs(chosen, first),
        "rate_czk": rate,
        "lines": lines,
        "guest_liable_nights": liable,
        "liable_nights": liable,
        "exempt_nights": sum(line["exempt_nights"] for line in lines),
        "total_czk": liable * rate,
        "adjustment_bed_days": 0,
        "adjustments": [],
        "unsigned_guests": unsigned,
    }
    return _apply_adjustments(period, month)


_GUESTS_FOR_RES_SQL = (
    "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id "
    "FROM guest g JOIN reservation r ON r.id = g.reservation_id "
    "WHERE r.apartment_id = ? AND r.id = ? AND r.status = 'active' AND g.archived_at IS NULL "
    "AND COALESCE(r.source, '') != 'demo' "
    "ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
)
_CHARGE_KEYS = ("guest_id", "liable_nights", "exempt_nights", "status", "auto_minor",
                "auto_obec_resident", "amount_czk")


def charge_for_reservation(apartment, reservation) -> Optional[Dict[str, Any]]:
    """Live amount for one reservation over its whole stay (guest panel and register share this)."""
    if not is_active(apartment) or not config.STAY_FEE_GUEST_PAY:
        return None
    schedule = stay_fee_rate.schedule_for(apartment)
    lines: List[Dict[str, Any]] = []
    stay = None
    for row in db.query(_GUESTS_FOR_RES_SQL, (apartment["id"], reservation["id"])):
        stay = stay or (row["res_from"], row["res_to"])
        share = guest_period(row, {"date_from": row["res_from"], "date_to": row["res_to"]},
                             date.min, date.max, apartment=apartment, schedule=schedule)
        if share is None:
            continue
        _apply_scope_boundary(share, apartment)
        lines.append({key: share[key] for key in _CHARGE_KEYS})
    liable = sum(line["liable_nights"] for line in lines)
    total = sum(line["amount_czk"] for line in lines)
    # Callers may pass only {"id": ...}: the stay dates come from the query.
    res_from, res_to = stay or (None, None)
    last_night = validation.parse_iso_date(res_to) or date.today()
    first_night = (validation.parse_iso_date(res_from) or date.today()) + timedelta(days=1)
    return {"total_czk": total, "liable_nights": liable,
            "rate_czk": stay_fee_rate.rate_on(schedule, last_night), "lines": lines,
            "mixed": not stay_fee_rate.is_uniform(schedule, first_night, last_night)}


def qr_offered_for_reservation(reservation) -> bool:
    """True when the stay has a Czech or Slovak guest: their banks read the QR."""
    rows = db.query(
        "SELECT nationality FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
        (reservation["id"],),
    )
    return any((row["nationality"] or "").upper() in ("CZE", "SVK") for row in rows)


def guest_pay_ways(apartment, reservation, charge, qr_ok=None) -> List[Dict[str, Any]]:
    """The one rule for the guest pay ways and the QR code (brief 1084).

    Screen and mail both call this. Ways: usable_rail_keys (enabled, default
    first, a way without what it needs is left out); bank details go to
    everyone. The QR (spayd) rides on the bank way only, and only when the
    stay has a Czech or Slovak guest. qr_ok overrides that for tests only.
    """
    if qr_ok is None:
        qr_ok = qr_offered_for_reservation(reservation)
    total = int(charge["total_czk"])
    vs = str(int(reservation["id"]))
    account, payee = payout_account(apartment)
    ways: List[Dict[str, Any]] = []
    for key in usable_rail_keys(apartment):
        if key == "iban":
            spayd = payments.spayd(account, total, vs, f"Stay fee {vs}") if qr_ok else ""
            ways.append({"key": "iban", "payee": payee,
                         "account": payments.format_iban(account), "spayd": spayd})
        elif key == "revolut":
            ways.append({"key": "revolut", "link": apartment["stay_fee_guest_revolut_link"]})
        else:
            ways.append({"key": "cash", "note": apartment["stay_fee_guest_cash_note"] or ""})
    return ways


def _rate_segments(period: Dict[str, Any]) -> List[List[int]]:
    """Nights per rate for the period: guest nights plus bed-days at the last-day rate."""
    nights: Dict[int, int] = {}
    for line in period["lines"]:
        for rate, count in line.get("rate_nights", []):
            nights[rate] = nights.get(rate, 0) + count
    base = int(period["rate_czk"])
    nights[base] = nights.get(base, 0) + period["adjustment_bed_days"]
    # A removal larger than the last-day-rate nights takes the rest off the
    # other rates, highest first (liable_nights is clamped at 0, so it fits).
    deficit = -nights[base] if nights[base] < 0 else 0
    if deficit:
        nights[base] = 0
        for rate in sorted(nights, reverse=True):
            take = min(deficit, nights[rate])
            nights[rate] -= take
            deficit -= take
    return sorted([r, n] for r, n in nights.items() if n > 0) or [[base, 0]]


def _apply_adjustments(period: Dict[str, Any], month: date) -> Dict[str, Any]:
    """Fold open aggregate corrections into the live liable total."""
    from . import stay_fee_adjustment, stay_fee_filing

    key = stay_fee_filing.period_key(period["cadence"], month)
    delta, rows = stay_fee_adjustment.active(period["apartment"]["id"], key)
    guest_nights = period["guest_liable_nights"]
    # A stored correction that would go below zero is clamped for display.
    # The write path refuses to create that correction in the first place.
    liable = max(guest_nights + delta, 0)
    period["adjustment_bed_days"] = liable - guest_nights
    period["adjustments"] = rows
    period["liable_nights"] = liable
    period["rate_segments"] = _rate_segments(period)
    # Sum of the segments: guest nights at their own rates plus bed-days at the
    # last-day rate. With one rate this is liable * rate, as before.
    period["total_czk"] = sum(rate * nights for rate, nights in period["rate_segments"])
    period["period_key"] = key
    return period


def owner_periods(owner_user_id, month: date) -> List[Dict[str, Any]]:
    """The list page: active properties, plus disabled ones that still have a sealed period."""
    rows = db.query(
        f"SELECT * FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL "
        "AND (stay_fee_rate_czk > 0 OR id IN ("
        "SELECT apartment_id FROM stay_fee_filing WHERE superseded_at IS NULL)) "
        "ORDER BY internal_name, id",
        (owner_user_id,),
    )
    periods = []
    for row in rows:
        period = property_period(row, month)
        if period is not None:
            periods.append(period)
    return periods


# --- the report (one hlášení = one payer + one VS) --------------------------

def vs_of(apartment) -> str:
    return "".join(ch for ch in (apartment["stay_fee_vs"] or "") if ch.isdigit())


def report_group(
    apartment,
    month: date,
    *,
    live_only: bool = False,
    period: Optional[Dict[str, Any]] = None,
    cadence: Optional[str] = None,
) -> Dict[str, Any]:
    """One hlášení and register per facility (§3g), even when VS is shared."""
    vs = vs_of(apartment)
    if period is None:
        period = property_period(apartment, month, live_only=live_only, cadence=cadence)
    periods = [period] if period else []
    if period is not None and period.get("first") and period.get("last"):
        cadence = period["cadence"]
        first, last = period["first"], period["last"]
        label = period.get("label") or period_label_cs(cadence, first)
    else:
        cadence = cadence if cadence in CADENCES else cadence_of(apartment)
        first, last = period_bounds(cadence, month)
        label = period_label_cs(cadence, month)
    return {
        "anchor": apartment,
        "vs": vs,
        "cadence": cadence,
        "first": first,
        "last": last,
        "label": label,
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
    if group.get("first"):
        from . import stay_fee_filing

        if stay_fee_filing.foreign_overlap(anchor["id"], group["cadence"], group["first"]):
            issues.append("stay_fees.issue.overlaps_saved")
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


def unsigned_stays(
    apartment_id: int, first: date, last: date, period: Optional[Dict[str, Any]] = None
) -> int:
    """Guests in the period with no signature yet (they are still in the fee; this only flags them).

    ``period`` is the live ``property_period`` for the same property and dates
    when the caller has it; its count comes from the same rows, so no second
    read is needed.
    """
    if (
        period is not None
        and "unsigned_guests" in period
        and period.get("first") == first
        and period.get("last") == last
        and period["apartment"]["id"] == apartment_id
    ):
        return period["unsigned_guests"]
    rows = db.query(
        "SELECT g.* FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "WHERE r.apartment_id = ? AND r.status = 'active' AND g.archived_at IS NULL "
        "AND COALESCE(r.source, '') != 'demo' "
        "AND COALESCE(g.stay_from, r.date_from) <= ? AND COALESCE(g.stay_to, r.date_to) >= ?",
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
# The register line for bed-days the host entered without guest records.
REGISTER_HOST_LINE = "přenocování bez záznamu hosta (doplněno ubytovatelem)"


def hlaseni(group, issued_on: date) -> Dict[str, Any]:
    """The report object ``stay_fee_remittance_pdf.render`` draws (Invoice companion design)."""
    anchor = group["anchor"]
    entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (anchor["legal_entity_id"],))
    signature_png = db.decrypt_field(entity["signature_png_enc"]) if entity["signature_png_enc"] else ""
    rows, minors, hosts = [], {"count": 0, "nights": 0}, {"count": 0, "nights": 0}
    for period in group["periods"]:
        # One line per facility with the bed-days the host owes. A host
        # adjustment (bed-days added or removed without naming guests) is part
        # of that number, not a line of its own: the office receives what is
        # due, and the adjustment history stays in UbyHost (owner, 2026-10-06).
        # A period that spans a rate change gets one row per rate (1027), so
        # nights x rate == amount holds on every row. Pairs are [rate, nights].
        segments = period.get("rate_segments") or [[period["rate_czk"], period["liable_nights"]]]
        for rate, nights in segments:
            rows.append({
                "property_name": period["apartment"]["internal_name"],
                "property_address": property_address(period["apartment"]),
                "liable_nights": nights,
                "rate_czk": rate,
                "amount_czk": nights * rate,
            })
        for line in period["lines"]:
            if line["exempt_nights"]:
                # A guest who turns 18 inside the period is "liable" overall
                # but still carries exempt minor nights; they count as minors.
                bucket = minors if (line["auto_minor"] or line["status"] == "liable") else hosts
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
    # Bed-days the host added or removed without naming guests get one neutral
    # line, so the register adds up to the same total as the report and the
    # payment. The PDF folds them into the facility row (owner, 2026-10-06).
    delta = int(period.get("adjustment_bed_days") or 0)
    if delta:
        rows.append({
            "property": apartment["internal_name"],
            "period": period["label"],
            "stay_from": "",
            "stay_to": "",
            "surname": "",
            "first_name": "",
            "home_address": "",
            "birth_date": "",
            "doc_type": "",
            "doc_number": "",
            "nights": delta,
            "rate_czk": period["rate_czk"],
            "amount_czk": delta * period["rate_czk"],
            "exempt_reason": REGISTER_HOST_LINE,
            "vs": vs_of(apartment),
            "council_account": apartment["stay_fee_council_account"] or "",
        })
    return rows


def register_csv(rows: List[Dict[str, Any]]) -> bytes:
    """';'-separated, UTF-8 with BOM, like housebook.housebook_csv."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _, label in REGISTER_COLUMNS])
    for row in rows:
        writer.writerow([csv_safe(row[key]) for key, _ in REGISTER_COLUMNS])
    return ("﻿" + buffer.getvalue()).encode("utf-8")
