"""A4: setup consistency check for the Foreigner police section.

Warns, never blocks. Pure except ``first_filing_pending`` (one read through
db.py). Nothing here stores or logs anything. A finding carries only the values
it compares (login, IDUB, short name, facility name, house number), and only in
the answer to the host who pasted or opened the page. The password and the
letter text never enter this module's output.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field as _field
from typing import Any, Dict, List, Mapping, Optional

from . import db, host_i18n, police_letter, validation

# The submission states that mean UbyPort accepted at least one guest.
ACCEPTED_STATES = ("ok", "ok_duplicate", "partial")

# The four values a letter and the form can disagree on (never the password).
FIELD_LABELS = {
    "uby_ws_user": "setup.label.login",
    "uby_idub": "setup.label.idub",
    "uby_mark": "setup.label.mark",
    "uby_name": "setup.label.facility",
}

_FACILITY_LABEL_RE = re.compile(
    r"^[ \t]*Ubytovac[ií][ \t]+za[rř][ií]zen[ií][ \t]*:", re.IGNORECASE | re.MULTILINE
)
_BRACKET_RE = re.compile(r"\[([A-Za-z0-9]{2,6})\]")
_LETTER_RE = re.compile(r"[A-Za-z]")
_NUMBER_RE = re.compile(r"\d+")
_MAX_BLOCK = 200


@dataclass(frozen=True)
class Finding:
    code: str
    field: str = ""
    params: Dict[str, str] = _field(default_factory=dict)


def _get(row: Any, key: str) -> str:
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = None
    return "" if value is None else str(value).strip()


def _fold(value: str) -> str:
    """Lower case, no diacritics, only letters and digits, single spaces."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.casefold()).split())


def _facility_block(text: Any) -> str:
    """The first two non-empty lines after "Ubytovací zařízení:", at most 200 characters."""
    if not isinstance(text, str):
        return ""
    text = text.replace(" ", " ")
    match = _FACILITY_LABEL_RE.search(text)
    if not match:
        return ""
    lines = [line.strip() for line in text[match.end():].split("\n")]
    return " ".join([line for line in lines if line][:2])[:_MAX_BLOCK]


def letter_values(result: Any, text: Any) -> Dict[str, str]:
    """What the pasted letter prints, for the compared fields only.

    ``result`` is ``police_letter.parse_letter(text)``. The printed short name
    is the single ``[CODE]`` token (2 to 6 letters or digits, at least one
    letter) in the facility block; a digits-only token such as ``[2]`` is a
    flat number and is ignored. ``address_numbers`` are the digit runs after
    the first ``(`` of the block. The caller deletes the text afterwards.
    """
    values: Dict[str, str] = {}
    for name in ("uby_idub", "uby_ws_user"):
        item = result.fields.get(name)
        if item and item.state in police_letter.FILLED_STATES and item.value:
            values[name] = item.value
    facility = result.facility
    if facility.state == "found" and facility.value:
        values["uby_name"] = facility.value
    block = _facility_block(text)
    codes = {code.upper() for code in _BRACKET_RE.findall(block) if _LETTER_RE.search(code)}
    if len(codes) == 1:
        values["uby_mark"] = next(iter(codes))
    if "(" in block:
        values["address_numbers"] = " ".join(_NUMBER_RE.findall(block[block.index("("):]))
    return values


def form_values(apartment: Any, prefill: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """The values the boxes hold: the saved row, overlaid with what a letter just filled."""
    values = {
        name: _get(apartment, name)
        for name in (*FIELD_LABELS, "addr_street", "addr_house_no")
    }
    for name, value in (prefill or {}).items():
        if name in FIELD_LABELS and value:
            values[name] = str(value).strip()
    return values


def letter_findings(letter: Mapping[str, str], form: Mapping[str, str]) -> List[Finding]:
    out: List[Finding] = []
    for name in FIELD_LABELS:
        printed, held = letter.get(name, ""), form.get(name, "")
        if printed and held and _fold(printed) != _fold(held):
            out.append(Finding("letter_mismatch", name, {"letter": printed, "form": held}))
    numbers = letter.get("address_numbers", "").split()
    house = form.get("addr_house_no", "")
    digits = _NUMBER_RE.findall(house)
    if numbers and digits and not set(digits) & set(numbers):
        out.append(Finding("letter_address", "uby_name", {"letter": " ".join(numbers), "form": house}))
    return out


def local_findings(form: Mapping[str, str], *, has_accepted: bool) -> List[Finding]:
    out: List[Finding] = []
    login, mark, name = form.get("uby_ws_user", ""), form.get("uby_mark", ""), form.get("uby_name", "")
    if login and not login.upper().startswith(("UBY-WS", "UBY-TWS")):
        out.append(Finding("login_prefix", "uby_ws_user"))
    suffix = validation.mark_from_ws_user(login)
    if not has_accepted and suffix and mark.upper() == suffix:
        out.append(Finding("mark_is_login_suffix", "uby_mark", {"mark": suffix}))
    street, house = form.get("addr_street", ""), form.get("addr_house_no", "")
    if name and (street or house):
        folded = _fold(name)
        if (street and _fold(street) not in folded) or (house and _fold(house) not in folded):
            out.append(Finding("name_address", "uby_name"))
    return out


def first_filing_pending(apartment_id: int) -> bool:
    """True while no submission of the apartment was accepted (no new column needed)."""
    row = db.query_one(
        "SELECT 1 AS found FROM submission WHERE apartment_id = ? "
        "AND state IN (?, ?, ?) LIMIT 1",
        (apartment_id, *ACCEPTED_STATES),
    )
    return row is None


def render(lang: str, finding: Finding) -> Dict[str, str]:
    params = dict(finding.params)
    if finding.code == "letter_mismatch":
        params["field"] = host_i18n.translate(lang, FIELD_LABELS[finding.field])
    return {
        "code": finding.code,
        "field": finding.field,
        "text": host_i18n.translate(lang, f"police_check.{finding.code}", **params),
    }


def findings_for(
    lang: str,
    apartment: Any,
    *,
    prefill: Optional[Mapping[str, str]] = None,
    letter: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, str]]:
    """Every warning for the police section, as {"code", "field", "text"} dicts."""
    form = form_values(apartment, prefill)
    pending = first_filing_pending(apartment["id"])
    items: List[Finding] = []
    if letter:
        items.extend(letter_findings(letter, form))
    items.extend(local_findings(form, has_accepted=not pending))
    if pending and all(form.get(name) for name in FIELD_LABELS):
        items.append(Finding("first_filing"))
    return [render(lang, item) for item in items]
