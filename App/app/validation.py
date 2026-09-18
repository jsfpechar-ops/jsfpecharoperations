"""Field normalisation and validation implementing the UbyPort data rules.

Everything here follows "Popis polozek ubytovaciho zarizeni, cizince a formát
UNL souboru" (appendix 3 of the Ubyport operating rules) and the web-service
description (appendix 5). Catching these problems while the guest is still
filling the form is the whole point: appendix 5 section 10.5 requires the host
application to check the data on first save and tell the user what blocks the
submission, rather than discovering it after the legal deadline has passed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data"

# Characters the appendix 3 "Name" regular expression allows, i.e. the CP1250
# letter repertoire plus whitespace, apostrophe and hyphen.
_NAME_LETTERS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "ĄŁĽŚŠŞŤŹŽŻąłľśšşťźžżŔÁÂĂÄĹĆÇČÉĘËĚÍÎĎĐŃŇÓÔŐÖŘŮÚŰÜÝŢ"
    "ŕáâăäĺćçčéęëěíîďđńňóôőöřůúűüýţß"
)
NAME_ALLOWED = set(_NAME_LETTERS) | set(" '-")
# The appendix 3 "Bydliste" regular expression: as above plus digits and punctuation.
RESIDENCE_ALLOWED = NAME_ALLOWED | set("0123456789/.,;:()&#@")
DOC_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# Never allowed in any field (appendix 3, section 2.1).
FORBIDDEN_ANYWHERE = ("\r", "\n", "|")

# Field length limits, appendix 3 section 3.3 (record type U).
MAX_SURNAME = 50
MAX_FIRST_NAME = 24
MAX_DOC = 30
MIN_DOC = 6
MAX_VISA = 15
MAX_RESIDENCE = 255
MAX_RESIDENCE_PART = 42
MAX_NOTE = 255

# Children travelling on a parent's passport: the document number is the literal
# "INPASS" and the parent's document number must then go into the note.
INPASS = "INPASS"

# Purpose-of-stay code list (kodovnik uctu pobytu). The web service is
# authoritative via DejMiCiselnik(UcelyPobytu); this is the offline fallback.
PURPOSES: List[Tuple[str, str, str]] = [
    ("00", "ZDRAVOTNÍ", "Medical"),
    ("01", "OBCHODNÍ", "Business"),
    ("02", "KULTURNÍ", "Cultural"),
    ("03", "NÁVŠTĚVA RODINY NEBO PŘÁTEL", "Visiting family or friends"),
    ("04", "POZVÁNÍ", "Invitation"),
    ("05", "OFICIÁLNÍ (POLITICKÝ)", "Official (political)"),
    ("06", "PODNIKÁNÍ – OSVČ", "Self-employment"),
    ("07", "SPORTOVNÍ", "Sport"),
    ("10", "TURISTIKA", "Tourism"),
    ("11", "STUDIUM (ŠKOLENÍ, STÁŽ)", "Study (training, internship)"),
    ("12", "TRANZIT (průjezd)", "Transit"),
    ("13", "LETIŠTNÍ TRANZIT (letištní průjezd)", "Airport transit"),
    ("27", "ZAMĚSTNÁNÍ", "Employment"),
    ("93", "TZV. ADS vízum udělované občanu Číny", "ADS visa (Chinese nationals)"),
    ("99", "OSTATNÍ / JINÉ", "Other"),
]
PURPOSE_CODES = {code for code, _cs, _en in PURPOSES}
DEFAULT_PURPOSE = "99"

# Czech nationals are not reported to the foreign police at all - the duty
# covers foreigners only - but they still belong in the house book.
CZECH_CODE = "CZE"

_COUNTRIES_CACHE: Optional[List[Dict[str, str]]] = None


def countries() -> List[Dict[str, str]]:
    """ISO 3166-1 alpha-3 list used for nationality and home-country fields."""
    global _COUNTRIES_CACHE
    if _COUNTRIES_CACHE is None:
        with open(DATA_DIR / "countries.json", encoding="utf-8") as fh:
            _COUNTRIES_CACHE = json.load(fh)
    return _COUNTRIES_CACHE


def country_codes() -> Dict[str, Dict[str, str]]:
    return {c["code"]: c for c in countries()}


def country_name(code: str, lang: str = "en") -> str:
    entry = country_codes().get((code or "").upper())
    if not entry:
        return code or ""
    return entry.get("cs" if lang == "cs" else "en", code)


def purpose_label(code: str, lang: str = "en") -> str:
    for c, cs, en in PURPOSES:
        if c == code:
            return f"{c} - {cs if lang == 'cs' else en}"
    return code or ""


@dataclass
class Issue:
    field: str
    message: str
    severity: str = "error"  # "error" blocks submission, "warning" does not

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


# --- normalisation -------------------------------------------------------

def strip_forbidden(value: Optional[str]) -> str:
    text = (value or "")
    for ch in FORBIDDEN_ANYWHERE:
        text = text.replace(ch, " ")
    return text


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# Letters outside CP1250 that have no combining-mark decomposition, so NFKD
# alone would leave them unrepresentable. The replacements are the ones ICAO
# Doc 9303 uses for the passport machine-readable zone, which is also what the
# police compare a record against.
_MRZ_FOLD = {
    "Đ": "D", "đ": "d", "Ð": "D", "ð": "d",
    "Ø": "O", "ø": "o", "Œ": "OE", "œ": "oe",
    "Æ": "AE", "æ": "ae", "Þ": "TH", "þ": "th",
    "İ": "I", "ı": "i", "Ħ": "H", "ħ": "h",
    "Ŧ": "T", "ŧ": "t", "Ə": "E", "ə": "e",
    "Ŀ": "L", "ŀ": "l", "Ŋ": "N", "ŋ": "n",
    "Ƶ": "Z", "ƶ": "z", "Ɖ": "D", "ɖ": "d",
}


def fold_to_allowed(text: str, allowed: set) -> str:
    """Keep what UbyPort accepts and transliterate the rest instead of deleting it.

    Dropping an unsupported letter silently changes the guest's identity
    (NGUYỄN would become NGUYN), so anything outside the CP1250 repertoire is
    folded to its passport-MRZ equivalent first and only dropped when even that
    has no representation.
    """
    out = []
    for ch in text:
        if ch in allowed:
            out.append(ch)
            continue
        mapped = _MRZ_FOLD.get(ch)
        if mapped is None:
            decomposed = unicodedata.normalize("NFKD", ch)
            mapped = "".join(c for c in decomposed if not unicodedata.combining(c))
        out.extend(c for c in mapped if c in allowed)
    return "".join(out)


def normalise_name(value: Optional[str]) -> str:
    """Uppercase, collapse whitespace, and fold to the characters UbyPort accepts."""
    text = collapse_spaces(strip_forbidden(value)).upper()
    return collapse_spaces(fold_to_allowed(text, NAME_ALLOWED))


def normalise_residence_part(value: Optional[str]) -> str:
    text = collapse_spaces(strip_forbidden(value))
    return collapse_spaces(fold_to_allowed(text, RESIDENCE_ALLOWED))


def normalise_document(value: Optional[str]) -> str:
    """Remove all spaces and uppercase; only A-Z and 0-9 survive."""
    text = strip_forbidden(value).upper()
    return fold_to_allowed(text, DOC_ALLOWED)


def normalise_note(value: Optional[str]) -> str:
    return collapse_spaces(strip_forbidden(value))[:MAX_NOTE]


def normalise_zip(value: Optional[str]) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def ascii_fold(value: str) -> str:
    """Diacritics-free copy, used for search and for MRZ comparison."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# --- birth date ----------------------------------------------------------

def normalise_birth_date(value: Optional[str]) -> str:
    """Return DDMMYYYY. Accepts / . - as separators; 0 means unknown."""
    raw = strip_forbidden(value).strip()
    if not raw:
        return ""
    separated = raw.replace("/", ".").replace("-", ".")
    digits_and_dots = "".join(ch for ch in separated if ch.isdigit() or ch == ".")
    if "." in digits_and_dots:
        parts = [p for p in digits_and_dots.split(".") if p != ""]
        if len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = _expand_two_digit_year(year)
            return f"{int(day or 0):02d}{int(month or 0):02d}{year.zfill(4)}"
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 8:
        return digits
    if len(digits) == 6:  # DDMMYY
        return digits[:4] + _expand_two_digit_year(digits[4:])
    return digits


def _expand_two_digit_year(two: str) -> str:
    """Pick the century that lands closest to today, per appendix 3."""
    n = int(two)
    current = date.today().year
    candidates = [1900 + n, 2000 + n]
    valid = [c for c in candidates if c <= current]
    return str(max(valid) if valid else min(candidates))


def parse_birth_date(ddmmyyyy: str) -> Optional[date]:
    """Real date if fully specified, else None (partial dates are legal)."""
    if not ddmmyyyy or len(ddmmyyyy) != 8:
        return None
    try:
        day, month, year = int(ddmmyyyy[:2]), int(ddmmyyyy[2:4]), int(ddmmyyyy[4:])
    except ValueError:
        return None
    if day == 0 or month == 0 or year == 0:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def format_birth_date(ddmmyyyy: Optional[str]) -> str:
    if not ddmmyyyy or len(ddmmyyyy) != 8:
        return ddmmyyyy or ""
    return f"{ddmmyyyy[:2]}.{ddmmyyyy[2:4]}.{ddmmyyyy[4:]}"


def display_birth_date(value: Optional[str]) -> str:
    """Guest form display: DD/MM/YYYY."""
    normalised = normalise_birth_date(value)
    if len(normalised) == 8 and normalised.isdigit():
        return f"{normalised[:2]}/{normalised[2:4]}/{normalised[4:]}"
    return (value or "").strip()


def validate_birth_date(ddmmyyyy: str, stay_from: Optional[date]) -> List[Issue]:
    if not ddmmyyyy:
        return [Issue("birth_date", "Date of birth is required.")]
    if len(ddmmyyyy) != 8 or not ddmmyyyy.isdigit():
        return [Issue("birth_date", "Enter the full date as DD/MM/YYYY.")]
    day, month, year = int(ddmmyyyy[:2]), int(ddmmyyyy[2:4]), int(ddmmyyyy[4:])
    if year and year < 1900:
        return [Issue("birth_date", "Year must be 1900 or later.")]
    if month > 12:
        return [Issue("birth_date", "Month must be between 01 and 12.")]
    if day > 31:
        return [Issue("birth_date", "Day must be between 01 and 31.")]
    exact = parse_birth_date(ddmmyyyy)
    if day and month and year and exact is None:
        return [Issue("birth_date", "That date does not exist - please check day and month.")]
    if exact and stay_from and exact > stay_from:
        return [Issue("birth_date", "Date of birth cannot be after your arrival date.")]
    if exact and exact > date.today():
        return [Issue("birth_date", "Date of birth cannot be in the future.")]
    return []


def age_on(birth: Optional[date], when: date) -> Optional[int]:
    if not birth:
        return None
    return when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))


# --- permanent residence abroad -----------------------------------------

def compose_residence(street: str, city: str, country_code: str, lang: str = "cs") -> str:
    """Build the single "Bydliste" string UbyPort expects.

    Appendix 3: the three parts are joined with ", " and the country is the
    three-letter code, a hyphen, then the country name.
    """
    parts = []
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    if country_code:
        parts.append(f"{country_code}-{country_name(country_code, lang)}")
    return ", ".join(parts)[:MAX_RESIDENCE]


def validate_residence(street: str, city: str, country_code: str) -> List[Issue]:
    issues: List[Issue] = []
    if not street:
        issues.append(Issue("res_street", "Street and number are required."))
    if not city:
        issues.append(Issue("res_city", "City is required."))
    if not country_code:
        issues.append(Issue("res_country", "Country is required."))
    for field, value, label in (("res_street", street, "Street"), ("res_city", city, "City")):
        if not value:
            continue
        if len(value) > MAX_RESIDENCE_PART:
            issues.append(Issue(field, f"{label} must be at most {MAX_RESIDENCE_PART} characters."))
        if value.isdigit():
            issues.append(Issue(field, f"{label} cannot consist of digits only."))
    if country_code and country_code not in country_codes():
        issues.append(Issue("res_country", "Unknown country code."))
    return issues


# --- guest record --------------------------------------------------------

GUEST_LENGTH_LIMITS = {
    "surname": MAX_SURNAME,
    "first_name": MAX_FIRST_NAME,
    "doc_number": MAX_DOC,
    "visa_number": MAX_VISA,
    "res_street": MAX_RESIDENCE_PART,
    "res_city": MAX_RESIDENCE_PART,
}


def normalise_guest(data: Dict[str, Optional[str]], clamp: bool = True) -> Dict[str, str]:
    """Coerce raw form input into exactly what will be sent to UbyPort.

    With ``clamp=False`` the text fields keep their full length so
    ``validate_guest`` can report "too long" and let the person decide what to
    shorten. Silently cutting a name mid-word submits a record that no longer
    matches the passport, which is what appendix 5 section 10.5 asks us to
    catch on first save instead.
    """
    values = {
        "surname": normalise_name(data.get("surname")),
        "first_name": normalise_name(data.get("first_name")),
        "birth_date": normalise_birth_date(data.get("birth_date")),
        "nationality": (data.get("nationality") or "").strip().upper()[:3],
        "doc_number": normalise_document(data.get("doc_number")),
        "visa_number": normalise_document(data.get("visa_number")),
        "res_street": normalise_residence_part(data.get("res_street")),
        "res_city": normalise_residence_part(data.get("res_city")),
        "res_country": (data.get("res_country") or "").strip().upper()[:3],
        "purpose": (data.get("purpose") or "").strip()[:2],
        # App-built text (the INPASS parent-document prefix), not something the
        # guest can shorten, so this one stays clamped either way.
        "note": normalise_note(data.get("note")),
    }
    if clamp:
        for field, limit in GUEST_LENGTH_LIMITS.items():
            values[field] = values[field][:limit]
    return values


NON_LATIN_MESSAGE = (
    "Type this using Latin letters (A-Z), exactly as printed in the two "
    "machine-readable lines at the bottom of your passport."
)


def validate_guest(
    guest: Dict[str, Optional[str]],
    stay_from: Optional[date] = None,
    stay_to: Optional[date] = None,
    raw: Optional[Dict[str, Optional[str]]] = None,
) -> List[Issue]:
    """All reasons this guest record would be refused, in display order.

    Pass ``raw`` (the untouched form input) so a name written in Cyrillic,
    Chinese or Arabic - which normalises to nothing UbyPort accepts - is told
    to use the passport's Latin transcription rather than the misleading
    "Surname is required".
    """
    issues: List[Issue] = []

    def typed(field: str) -> bool:
        return bool(raw and (raw.get(field) or "").strip())

    surname = guest.get("surname") or ""
    if not surname:
        issues.append(
            Issue("surname", NON_LATIN_MESSAGE if typed("surname") else "Surname is required.")
        )
    elif len(surname) > MAX_SURNAME:
        issues.append(Issue("surname", f"Surname must be at most {MAX_SURNAME} characters."))

    first_name = guest.get("first_name") or ""
    if not first_name:
        if typed("first_name"):
            issues.append(Issue("first_name", NON_LATIN_MESSAGE))
        else:
            # Appendix 3 allows an empty given name, but a blank one is nearly
            # always a filling mistake rather than a genuinely nameless guest.
            issues.append(
                Issue("first_name", "Given name looks missing - please check the passport.", "warning")
            )
    elif len(first_name) > MAX_FIRST_NAME:
        issues.append(Issue("first_name", f"Given name must be at most {MAX_FIRST_NAME} characters."))

    issues.extend(validate_birth_date(guest.get("birth_date") or "", stay_from))

    nationality = (guest.get("nationality") or "").upper()
    if not nationality:
        issues.append(Issue("nationality", "Nationality is required."))
    elif nationality not in country_codes():
        issues.append(Issue("nationality", f"'{nationality}' is not a valid three-letter country code."))

    doc = guest.get("doc_number") or ""
    note = guest.get("note") or ""
    if not doc:
        issues.append(Issue("doc_number", "Travel document number is required."))
    elif doc == INPASS:
        if not note:
            issues.append(
                Issue(
                    "note",
                    "For a child recorded in a parent's passport the note must contain "
                    "the parent's document number.",
                )
            )
    elif len(doc) < MIN_DOC:
        issues.append(Issue("doc_number", f"Document number must be at least {MIN_DOC} characters."))
    elif len(doc) > MAX_DOC:
        issues.append(Issue("doc_number", f"Document number must be at most {MAX_DOC} characters."))

    visa = guest.get("visa_number") or ""
    if visa and len(visa) > MAX_VISA:
        issues.append(Issue("visa_number", f"Visa number must be at most {MAX_VISA} characters."))

    issues.extend(
        validate_residence(
            guest.get("res_street") or "",
            guest.get("res_city") or "",
            (guest.get("res_country") or "").upper(),
        )
    )
    if len(compose_residence(
        guest.get("res_street") or "",
        guest.get("res_city") or "",
        (guest.get("res_country") or "").upper(),
    )) > MAX_RESIDENCE:
        issues.append(Issue("res_street", "Home address is too long."))

    purpose = guest.get("purpose") or ""
    if not purpose:
        issues.append(Issue("purpose", "Purpose of stay is required."))
    elif purpose not in PURPOSE_CODES:
        issues.append(Issue("purpose", "Unknown purpose-of-stay code."))

    # The normalisers strip these, but validation is also the gate in front of
    # values that were already stored, and one pipe or newline anywhere in a
    # record breaks the field framing for the whole batch.
    for field in ("surname", "first_name", "doc_number", "visa_number",
                  "res_street", "res_city", "note"):
        value = guest.get(field) or ""
        if any(ch in value for ch in FORBIDDEN_ANYWHERE):
            issues.append(
                Issue(field, "Remove the | character and any line breaks.")
            )

    if len(note) > MAX_NOTE:
        issues.append(Issue("note", f"Note must be at most {MAX_NOTE} characters."))

    if stay_from and stay_to and stay_to <= stay_from:
        issues.append(Issue("stay_to", "Departure date must be later than the arrival date."))

    return issues


def guest_is_reportable(nationality: Optional[str]) -> bool:
    """Czech nationals are outside the reporting duty; everyone else is in."""
    return bool(nationality) and nationality.upper() != CZECH_CODE


# --- accommodation facility (report header) ------------------------------

_IDUB_RE = re.compile(r"^[A-Za-z0-9]{12,14}$")
_MARK_RE = re.compile(r"^[A-Za-z]{5}$")
_HOUSE_RE = re.compile(r"^(?:\d{1,4}|E\d{1,4}|\d{1,4}E)$", re.IGNORECASE)
_ORIENT_RE = re.compile(r"^\d{1,3}[A-Za-z]?$")
_WS_USER_RE = re.compile(r"^(?:uby-ws[A-Za-z0-9]{6}|uby-tws[A-Za-z0-9]{5})$", re.IGNORECASE)

APARTMENT_FIELD_LIMITS = {
    "uby_name": 35,
    "uby_contact": 50,
    "addr_okres": 32,
    "addr_obec": 48,
    "addr_obec_cast": 48,
    "addr_street": 48,
}


def validate_apartment(ap: Dict[str, Optional[str]]) -> List[Issue]:
    """Reasons this apartment cannot yet submit reports to UbyPort."""
    issues: List[Issue] = []

    idub = (ap.get("uby_idub") or "").strip()
    if not idub:
        issues.append(Issue("uby_idub", "IDUB is required before anything can be reported."))
    elif not _IDUB_RE.match(idub):
        issues.append(Issue("uby_idub", "IDUB must be 12-14 letters or digits."))

    mark = (ap.get("uby_mark") or "").strip()
    if not mark:
        issues.append(Issue("uby_mark", "The facility abbreviation (zkratka) is required."))
    elif not _MARK_RE.match(mark):
        issues.append(Issue("uby_mark", "The abbreviation is exactly five letters, e.g. AAKLI."))

    name = (ap.get("uby_name") or "").strip()
    if not name:
        issues.append(Issue("uby_name", "Accommodation facility name is required."))
    elif len(name) > 35:
        issues.append(Issue("uby_name", "Facility name must be at most 35 characters."))

    for field, limit in APARTMENT_FIELD_LIMITS.items():
        value = (ap.get(field) or "").strip()
        if len(value) > limit:
            issues.append(Issue(field, f"Must be at most {limit} characters."))

    house = (ap.get("addr_house_no") or "").strip()
    if not house:
        issues.append(Issue("addr_house_no", "House number is required."))
    elif not _HOUSE_RE.match(house):
        issues.append(
            Issue("addr_house_no", "House number is up to 4 digits, optionally with E for an evidence number.")
        )

    orient = (ap.get("addr_orient_no") or "").strip()
    if orient and not _ORIENT_RE.match(orient):
        issues.append(Issue("addr_orient_no", "Orientation number is up to 3 digits plus one optional letter."))

    zipcode = normalise_zip(ap.get("addr_zip"))
    if not zipcode:
        issues.append(Issue("addr_zip", "Postcode is required."))
    elif len(zipcode) != 5:
        issues.append(Issue("addr_zip", "Postcode must be exactly 5 digits."))

    if not (ap.get("addr_obec") or "").strip():
        issues.append(Issue("addr_obec", "Municipality is required."))

    user = (ap.get("uby_ws_user") or "").strip()
    if not user:
        issues.append(Issue("uby_ws_user", "UbyPort web-service login is required for automatic reporting."))
    elif not _WS_USER_RE.match(user):
        issues.append(
            Issue(
                "uby_ws_user",
                "Web-service logins look like UBY-WS123abc (production) or uby-tws1ab45 (test). "
                "The ub1234567 login is for the web form and will not work here.",
                "warning",
            )
        )

    if not (ap.get("uby_ws_password") or ""):
        issues.append(Issue("uby_ws_password", "UbyPort web-service password is required."))

    if not ap.get("legal_entity_id"):
        # The operating entity is always the guest's stay contact, even where
        # a separate controller entity is configured.
        message = (
            "No property manager is attached, so guests have no named contact "
            "for questions about their stay."
        )
        if not ap.get("data_controller_entity_id"):
            message += " The privacy notice also cannot name who controls their data."
        issues.append(
            Issue(
                "legal_entity_id",
                message,
                "warning",
            )
        )

    return issues


def errors_only(issues: List[Issue]) -> List[Issue]:
    return [i for i in issues if i.is_error]


def issues_to_text(issues: List[Issue]) -> str:
    return "; ".join(f"{i.field}: {i.message}" for i in issues)


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
