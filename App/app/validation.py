"""Field normalisation and validation implementing the UbyPort data rules.

Everything here follows "Popis polozek ubytovaciho zarizeni, cizince a formát
UNL souboru" (appendix 3 of the Ubyport operating rules) and the web-service
description (appendix 5). Catching these problems while the guest is still
filling the form is the whole point: appendix 5 section 10.5 requires the host
application to check the data on first save and tell the user what blocks the
submission, rather than discovering it after the legal deadline has passed.
"""
from __future__ import annotations

import base64
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

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

# XML 1.0 cannot carry these at all; one of them in any field makes the
# whole UbyPort batch unparseable for every guest in it.
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

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

# The note is the only free-text field that travels with the record, so the
# parent's document number is written in front of whatever else it holds. Both
# forms build it here so a child filed by the host reads the same as one filed
# from the guest link.
INPASS_NOTE_PREFIX = "Dítě zapsané v pasu rodiče, číslo dokladu rodiče: "

# Purpose-of-stay code list (kodovnik uctu pobytu). The web service is
# authoritative via DejMiCiselnik(UcelyPobytu); this is the offline fallback.
# The texts are display labels, not the police wording: sentence case, and the
# numeric code stays out of them. Only the code is ever submitted (cPurp).
PURPOSES: List[Tuple[str, str, str]] = [
    ("00", "Zdravotní", "Medical"),
    ("01", "Obchodní", "Business"),
    ("02", "Kulturní", "Cultural"),
    ("03", "Návštěva rodiny nebo přátel", "Visiting family or friends"),
    ("04", "Pozvání", "Invitation"),
    ("05", "Oficiální (politický)", "Official (political)"),
    ("06", "Podnikání (OSVČ)", "Self-employment"),
    ("07", "Sportovní", "Sport"),
    ("10", "Turistika", "Tourism"),
    ("11", "Studium (školení, stáž)", "Study (training, internship)"),
    ("12", "Tranzit (průjezd)", "Transit"),
    ("13", "Letištní tranzit", "Airport transit"),
    ("27", "Zaměstnání", "Employment"),
    ("93", "Vízum ADS (občané Číny)", "ADS visa (Chinese nationals)"),
    ("99", "Ostatní", "Other"),
]
# WP26: the purpose labels for the guest form's other languages. ``PURPOSES``
# keeps its (code, cs, en) shape because the host app and UbyPort read it.
PURPOSE_LABELS: Dict[str, Dict[str, str]] = {
    "de": {
        "00": "Medizinisch",
        "01": "Geschäftlich",
        "02": "Kulturell",
        "03": "Besuch von Familie oder Freunden",
        "04": "Einladung",
        "05": "Dienstlich (politisch)",
        "06": "Selbstständige Tätigkeit",
        "07": "Sport",
        "10": "Tourismus",
        "11": "Studium (Ausbildung, Praktikum)",
        "12": "Transit",
        "13": "Flughafentransit",
        "27": "Beschäftigung",
        "93": "ADS-Visum (chinesische Staatsangehörige)",
        "99": "Sonstiges",
    },
    "es": {
        "00": "Médico",
        "01": "Negocios",
        "02": "Cultural",
        "03": "Visita a familiares o amigos",
        "04": "Invitación",
        "05": "Oficial (político)",
        "06": "Trabajo por cuenta propia",
        "07": "Deporte",
        "10": "Turismo",
        "11": "Estudios (formación, prácticas)",
        "12": "Tránsito",
        "13": "Tránsito aeroportuario",
        "27": "Empleo",
        "93": "Visado ADS (ciudadanos chinos)",
        "99": "Otro",
    },
    "fr": {
        "00": "Médical",
        "01": "Affaires",
        "02": "Culture",
        "03": "Visite familiale ou amicale",
        "04": "Invitation",
        "05": "Officiel (politique)",
        "06": "Activité indépendante",
        "07": "Sport",
        "10": "Tourisme",
        "11": "Études (formation, stage)",
        "12": "Transit",
        "13": "Transit aéroportuaire",
        "27": "Emploi",
        "93": "Visa ADS (ressortissants chinois)",
        "99": "Autre",
    },
}
PURPOSE_CODES = {code for code, _cs, _en in PURPOSES}
DEFAULT_PURPOSE = "99"

# Czech nationals are not reported to the foreign police at all - the duty
# covers foreigners only - but they still belong in the house book.
CZECH_CODE = "CZE"

# Identity-document kinds the stay-fee register (evidenční kniha, zákon
# 565/1990 Sb. § 3g(2)(d)) must name. The guest never picks one: stay_fee
# derives it from nationality and the host may correct it.
DOC_TYPES = (
    "op", "pas", "prechodny_pobyt", "pobytova_karta_eu", "povoleni_pobyt",
    "povoleni_pobyt_cizinec", "trvaly_pobyt", "zadatel_mezinarodni_ochrana",
    "zadatel_docasna_ochrana",
)


def age_on(birth: date, when: date) -> int:
    """Whole years between ``birth`` and ``when``."""
    years = when.year - birth.year
    if (when.month, when.day) < (birth.month, birth.day):
        years -= 1
    return years

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


def ico_ok(ico: str) -> bool:
    """Czech IČO: 8 digits, the last is the mod-11 check digit."""
    text = (ico or "").strip()
    if len(text) != 8 or not text.isdigit():
        return False
    weights = (8, 7, 6, 5, 4, 3, 2)
    total = sum(int(digit) * weight for digit, weight in zip(text[:7], weights))
    remainder = total % 11
    check = 1 if remainder == 0 else 0 if remainder == 1 else 11 - remainder
    return int(text[7]) == check


def country_name(code: str, lang: str = "en") -> str:
    entry = country_codes().get((code or "").upper())
    if not entry:
        return code or ""
    if lang in ("cs", "de", "es", "fr") and entry.get(lang):
        return entry[lang]
    return entry.get("en", code)


def purpose_label(code: str, lang: str = "en") -> str:
    """The purpose as a person reads it — no police code, sentence case."""
    for c, cs, en in PURPOSES:
        if c == code:
            if lang in PURPOSE_LABELS:
                return PURPOSE_LABELS[lang].get(c) or en
            return cs if lang == "cs" else en
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
    text = _XML_ILLEGAL.sub(" ", text)
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


def note_for_parent_document(parent_document: Optional[str], note: str = "") -> str:
    """The note a child travelling on a parent's passport must carry.

    Appendix 3 wants the parent's document number on the record, and the note is
    the only free-text field that reaches UbyPort, so it is written in front of
    whatever the person already typed there.
    """
    parent = normalise_document(parent_document)
    if not parent:
        return note
    return (INPASS_NOTE_PREFIX + parent + (f" {note}" if note else ""))[:MAX_NOTE]


def normalise_zip(value: Optional[str]) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


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
    """Guest and host form display: DD.MM.YYYY."""
    normalised = normalise_birth_date(value)
    if len(normalised) == 8 and normalised.isdigit():
        return f"{normalised[:2]}.{normalised[2:4]}.{normalised[4:]}"
    return (value or "").strip()


def validate_birth_date(ddmmyyyy: str, stay_from: Optional[date]) -> List[Issue]:
    if not ddmmyyyy:
        return [Issue("birth_date", "Date of birth is required.")]
    if len(ddmmyyyy) != 8 or not ddmmyyyy.isdigit():
        return [Issue("birth_date", "Enter the full date as DD.MM.YYYY.")]
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


def display_residence(street: str, city: str, country_code: str, lang: str = "cs") -> str:
    """The residence as a person reads it: the country by name, no ISO code.

    UbyPort's "Bydliste" needs the "GBR-United Kingdom" shape, which is what
    ``compose_residence`` builds. A guest looking at their own summary does
    not, so the code is left out here.
    """
    parts = []
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    if country_code:
        parts.append(country_name(country_code, lang))
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

# Every field ``normalise_guest`` reads and ``validate_guest`` checks. The host
# form, the guest form and the UbyPort payload all describe the same record, so
# they all iterate this one tuple - a field added here reaches every path at
# once instead of being silently dropped by whichever copy was forgotten.
GUEST_TEXT_FIELDS = (
    "surname",
    "first_name",
    "birth_date",
    "nationality",
    "doc_number",
    "visa_number",
    "res_street",
    "res_city",
    "res_country",
    "purpose",
    "note",
)

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


STAY_OUTSIDE_BOOKING_MESSAGE = (
    "These dates do not match your booking. Reload this page, or ask your host."
)

STAY_DATE_UNREADABLE_MESSAGE = (
    "The stay dates on this page are not readable. Reload the page and try again."
)


def validate_stay_date_text(
    stay_from: Optional[str], stay_to: Optional[str]
) -> List[Issue]:
    """An unreadable stay date is refused, never stored.

    ``stay_from``/``stay_to`` arrive as hidden fields, so they can be stale or
    hand-built. A value that does not parse used to slip through the window
    check entirely and be written to the row as typed - and ``stay_to`` in a
    form like ``garbage`` then escaped the retention purge, which compares the
    column as text. Both fields therefore have to be real ISO dates.
    """
    issues: List[Issue] = []
    for field, value in (("stay_from", stay_from), ("stay_to", stay_to)):
        if value and parse_iso_date(value) is None:
            issues.append(Issue(field, STAY_DATE_UNREADABLE_MESSAGE))
    return issues

# The product does not let a guest record a stay outside their booking: a guest
# who really did arrive early is told to ask the host, rather than having the
# period in the police record rewritten for them. The knob is here so that a
# future decision to allow a day of slack at each end is a one-line change.
STAY_DATE_TOLERANCE_DAYS = 0


def validate_stay_dates(
    stay_from: Optional[date],
    stay_to: Optional[date],
    allowed_from: Optional[date],
    allowed_to: Optional[date],
) -> List[Issue]:
    """Reasons a stay period falls outside the window its host set for it.

    ``stay_from``/``stay_to`` reach the guest save route as hidden fields, so a
    period outside the window is either a page the host has since re-dated or a
    hand-built request. Both are refused rather than clamped: the period is
    what UbyPort receives as ``cFrom``/``cUntil``, and ``stay_to`` is what
    decides how long a passport scan is kept.
    """
    issues: List[Issue] = []
    slack = timedelta(days=STAY_DATE_TOLERANCE_DAYS)
    if stay_from and allowed_from and stay_from < allowed_from - slack:
        issues.append(Issue("stay_from", STAY_OUTSIDE_BOOKING_MESSAGE))
    if stay_to and allowed_to and stay_to > allowed_to + slack:
        issues.append(Issue("stay_to", STAY_OUTSIDE_BOOKING_MESSAGE))
    return issues


# How far back a stay-specific guest link keeps reaching. ``permalink_window_days``
# is the forward lead window (which stays the apartment link lists); this is the
# opposite direction, and the two must not be conflated: the reach-back window
# exists so a forgotten form can still be finished, and it is deliberately a year
# rather than the couple of weeks a lead window is measured in.
REACHBACK_DAYS_DEFAULT = 365
REACHBACK_DAYS_MAX = 3650


def normalise_reachback_days(value: Any) -> int:
    """A blank, missing or nonsensical reach-back window falls back to the default.

    Never to "no bound": an unset or hand-edited value must not widen access, so
    a value below a day is clamped up and one beyond the cap clamped down.
    """
    try:
        days = int(value)
    except (TypeError, ValueError):
        return REACHBACK_DAYS_DEFAULT
    if days <= 0:
        return REACHBACK_DAYS_DEFAULT
    return min(days, REACHBACK_DAYS_MAX)


# The first bytes each accepted type has to start with. The browser draws into
# a canvas and hands over ``canvas.toDataURL("image/png")``, so PNG is the only
# type this app itself produces; JPEG is allowed for a signature pad embedded
# elsewhere (for example a camera-captured paper form).
SIGNATURE_MIME_MAGIC = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}

# A drawn signature is a few kilobytes of mostly transparent canvas PNG. The cap
# exists because ``signature_png`` is a TEXT column in a single SQLite file: it
# is generous enough for a dense signature on a large screen, and small enough
# that a hand-built request cannot put a blob in the database.
MAX_SIGNATURE_BYTES = 256 * 1024
MAX_SIGNATURE_SIDE = 6000
MAX_SIGNATURE_PIXELS = 12_000_000

SIGNATURE_INVALID_MESSAGE = (
    "That signature could not be saved. Sign again on the signature pad."
)

# The whole value has to be one base64 data URL of an allowed image type. The
# prefix is matched before decoding so an oversized body is never decoded.
_SIGNATURE_DATA_URL = re.compile(
    r"^data:(?P<mime>image/[a-z0-9.+-]+);base64,(?P<payload>[A-Za-z0-9+/=]*)$"
)
# 4 base64 characters carry 3 bytes, so this is the longest payload that can
# still decode to an allowed number of bytes.
_MAX_SIGNATURE_PAYLOAD_CHARS = 4 * (MAX_SIGNATURE_BYTES // 3) + 4


def parse_signature_data_url(value: Optional[str]) -> bytes:
    """Return the image bytes of a drawn signature, or raise ``ValueError``.

    ``signature_png`` is a TEXT column on a single-file SQLite database, and
    every downstream "this guest signed" check is a look at its prefix, so this
    is the one place that decides what may be stored: a base64 data URL of a PNG
    or JPEG, under ``MAX_SIGNATURE_BYTES``, whose first bytes really are that
    type's magic bytes. ``image/svg+xml`` is refused even though it is an image
    - an SVG is a script container, and nothing here renders one.
    """
    match = _SIGNATURE_DATA_URL.match((value or "").strip())
    if not match:
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    magic = SIGNATURE_MIME_MAGIC.get(match.group("mime").lower())
    if magic is None:
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    payload = match.group("payload")
    if not payload or len(payload) > _MAX_SIGNATURE_PAYLOAD_CHARS:
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    try:
        # validate=True: a payload that is not base64 must not be silently
        # repaired into bytes that happen to start with a magic number.
        content = base64.b64decode(payload, validate=True)
    except ValueError:
        raise ValueError(SIGNATURE_INVALID_MESSAGE) from None
    if not content or len(content) > MAX_SIGNATURE_BYTES:
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    if not content.startswith(magic):
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    try:
        with Image.open(io.BytesIO(content)) as image:  # reads the header only
            width, height = image.size
    except Exception:
        raise ValueError(SIGNATURE_INVALID_MESSAGE) from None
    if (
        width > MAX_SIGNATURE_SIDE
        or height > MAX_SIGNATURE_SIDE
        or width * height > MAX_SIGNATURE_PIXELS
    ):
        raise ValueError(SIGNATURE_INVALID_MESSAGE)
    return content


def signature_issue(value: Optional[str]) -> Optional[Issue]:
    """The ``signature`` issue a value would raise, or ``None`` when it is fine."""
    try:
        parse_signature_data_url(value)
    except ValueError as exc:
        return Issue("signature", str(exc))
    return None


def is_valid_signature(value: Optional[str]) -> bool:
    """True for a value both save paths may store as a collected signature.

    Not the same question as ``reporting.guest_has_signature``, which also
    accepts the ``"imported"`` marker a paper house-book row carries.
    """
    return signature_issue(value) is None


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


def fmt_date(value: Optional[str]) -> str:
    """An ISO date as the Czech ``DD.MM.YYYY`` the forms and mail both print.

    Unparseable input is passed through unchanged rather than blanked: a value
    that got here is a date someone needs to see, even if it is malformed.
    """
    parsed = parse_iso_date(value)
    return parsed.strftime("%d.%m.%Y") if parsed else (value or "")


def fmt_date_range(date_from: Optional[str], date_to: Optional[str]) -> str:
    """``from - to``, with an en dash, or whichever end exists."""
    start, end = fmt_date(date_from), fmt_date(date_to)
    if start and end:
        return f"{start} \u2013 {end}"
    return start or end
