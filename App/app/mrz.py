"""Machine-readable zone parsing for passports and ID cards (ICAO 9303).

Guests type or paste the two (or three) MRZ lines from the bottom of their
document instead of typing six separate fields. The MRZ is already the
transliterated, UbyPort-compatible form of the name, and the check digits let
us catch a mistyped document number before it reaches the police - which is
the single most common cause of a rejected record.

Supported: TD3 (passport, 2x44), TD2 (2x36), TD1 (ID card, 3x30).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

FILLER = "<"
_WEIGHTS = (7, 3, 1)


@dataclass
class MrzResult:
    ok: bool
    kind: str = ""
    surname: str = ""
    first_name: str = ""
    doc_number: str = ""
    nationality: str = ""
    birth_date: str = ""  # DDMMYYYY
    sex: str = ""
    expiry: str = ""  # DDMMYYYY
    issuing_state: str = ""
    warnings: List[str] = field(default_factory=list)
    error: str = ""


def _char_value(ch: str) -> int:
    if ch == FILLER:
        return 0
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 0


def check_digit(value: str) -> str:
    total = sum(_char_value(ch) * _WEIGHTS[i % 3] for i, ch in enumerate(value))
    return str(total % 10)


def _valid_check(value: str, digit: str) -> bool:
    if digit == FILLER:
        return True  # optional fields may leave the check digit blank
    return check_digit(value) == digit


def _clean_line(line: str) -> str:
    text = (line or "").strip().upper().replace(" ", "")
    # OCR and manual typing routinely swap these for the filler character.
    text = text.replace("«", FILLER).replace("‹", FILLER)
    return re.sub(r"[^A-Z0-9<]", "", text)


def _names(field_text: str) -> tuple:
    """Split the MRZ name field into surname and given names."""
    parts = field_text.split("<<", 1)
    surname = parts[0].replace(FILLER, " ").strip()
    given = parts[1].replace(FILLER, " ").strip() if len(parts) > 1 else ""
    return surname, re.sub(r"\s+", " ", given)


def _yymmdd_to_ddmmyyyy(yymmdd: str, kind: str) -> str:
    """Expand the two-digit MRZ year.

    Birth dates are always in the past; expiry dates are normally in the
    future, so the century is chosen accordingly.
    """
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return ""
    yy, mm, dd = int(yymmdd[:2]), yymmdd[2:4], yymmdd[4:6]
    current = date.today().year
    if kind == "birth":
        year = 2000 + yy if 2000 + yy <= current else 1900 + yy
    else:
        year = 2000 + yy if 2000 + yy >= current - 10 else 1900 + yy
    return f"{dd}{mm}{year}"


def parse(text: str) -> MrzResult:
    """Parse pasted MRZ text, autodetecting the document format."""
    lines = [_clean_line(l) for l in (text or "").splitlines()]
    lines = [l for l in lines if l]

    # Some guests paste everything as one unbroken run of characters.
    if len(lines) == 1:
        blob = lines[0]
        for size in (44, 36, 30):
            if len(blob) == size * 2:
                lines = [blob[:size], blob[size:]]
                break
            if len(blob) == size * 3 and size == 30:
                lines = [blob[:30], blob[30:60], blob[60:]]
                break

    if not lines:
        return MrzResult(False, error="No MRZ text found.")

    widths = {len(l) for l in lines}
    if len(lines) == 2 and widths == {44}:
        return _parse_td3(lines)
    if len(lines) == 2 and widths == {36}:
        return _parse_td2(lines)
    if len(lines) == 3 and widths == {30}:
        return _parse_td1(lines)

    return MrzResult(
        False,
        error=(
            "Unrecognised MRZ layout: got %s line(s) of length %s. Expected 2x44 (passport), "
            "2x36 or 3x30 (ID card)." % (len(lines), ", ".join(str(len(l)) for l in lines))
        ),
    )


def _parse_td3(lines: List[str]) -> MrzResult:
    top, bottom = lines
    surname, given = _names(top[5:44])
    doc_number = bottom[0:9].replace(FILLER, "")
    result = MrzResult(
        ok=True,
        kind="TD3",
        issuing_state=top[2:5].replace(FILLER, ""),
        surname=surname,
        first_name=given,
        doc_number=doc_number,
        nationality=bottom[10:13].replace(FILLER, ""),
        birth_date=_yymmdd_to_ddmmyyyy(bottom[13:19], "birth"),
        sex=bottom[20] if bottom[20] in "MF" else "",
        expiry=_yymmdd_to_ddmmyyyy(bottom[21:27], "expiry"),
    )
    if not _valid_check(bottom[0:9], bottom[9]):
        result.warnings.append("Document number check digit does not match - please re-check the number.")
    if not _valid_check(bottom[13:19], bottom[19]):
        result.warnings.append("Date of birth check digit does not match.")
    if not _valid_check(bottom[21:27], bottom[27]):
        result.warnings.append("Expiry date check digit does not match.")
    _finish(result)
    return result


def _parse_td2(lines: List[str]) -> MrzResult:
    top, bottom = lines
    surname, given = _names(top[5:36])
    result = MrzResult(
        ok=True,
        kind="TD2",
        issuing_state=top[2:5].replace(FILLER, ""),
        surname=surname,
        first_name=given,
        doc_number=bottom[0:9].replace(FILLER, ""),
        nationality=bottom[10:13].replace(FILLER, ""),
        birth_date=_yymmdd_to_ddmmyyyy(bottom[13:19], "birth"),
        sex=bottom[20] if bottom[20] in "MF" else "",
        expiry=_yymmdd_to_ddmmyyyy(bottom[21:27], "expiry"),
    )
    if not _valid_check(bottom[0:9], bottom[9]):
        result.warnings.append("Document number check digit does not match - please re-check the number.")
    _finish(result)
    return result


def _parse_td1(lines: List[str]) -> MrzResult:
    first, second, third = lines
    surname, given = _names(third)
    result = MrzResult(
        ok=True,
        kind="TD1",
        issuing_state=first[2:5].replace(FILLER, ""),
        doc_number=first[5:14].replace(FILLER, ""),
        birth_date=_yymmdd_to_ddmmyyyy(second[0:6], "birth"),
        sex=second[7] if second[7] in "MF" else "",
        expiry=_yymmdd_to_ddmmyyyy(second[8:14], "expiry"),
        nationality=second[15:18].replace(FILLER, ""),
        surname=surname,
        first_name=given,
    )
    if not _valid_check(first[5:14], first[14]):
        result.warnings.append("Document number check digit does not match - please re-check the number.")
    _finish(result)
    return result


def _finish(result: MrzResult) -> None:
    """Post-process shared fields and sanity-check the essentials."""
    # ICAO uses "D" for Germany; UbyPort wants ISO 3166-1 alpha-3.
    fixes = {"D": "DEU", "GBD": "GBR", "GBN": "GBR", "GBO": "GBR", "GBP": "GBR", "GBS": "GBR"}
    result.nationality = fixes.get(result.nationality, result.nationality)
    result.issuing_state = fixes.get(result.issuing_state, result.issuing_state)
    if not result.surname:
        result.ok = False
        result.error = "Could not read the surname from the MRZ."
    if not result.doc_number:
        result.ok = False
        result.error = "Could not read the document number from the MRZ."
