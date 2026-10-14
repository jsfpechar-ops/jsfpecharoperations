"""Presentation helpers for the host's existing operator contact phone."""
from __future__ import annotations

import re
from typing import Dict

_TWO_DIGIT_CODES = frozenset(
    "20 27 30 31 32 33 34 36 39 40 41 43 44 45 46 47 48 49 "
    "51 52 53 54 55 56 57 58 60 61 62 63 64 65 66 81 82 84 86 90 91 92 93 94 95 98".split()
)


def form_parts(value: str) -> Dict[str, str]:
    """Split international numbers; suggest +420 for a blank or Czech local number."""
    raw = (value or "").strip()
    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+") and compact[1:].isdigit():
        digits = compact[1:]
        size = 1 if digits[:1] in ("1", "7") else 2 if digits[:2] in _TWO_DIGIT_CODES else 3
        if len(digits) > size:
            return {"code": "+" + digits[:size], "number": digits[size:]}
    if not raw or (compact.isdigit() and len(compact) == 9):
        return {"code": "+420", "number": compact}
    # Keep unusual legacy formats intact rather than guessing their country.
    return {"code": "", "number": raw}


def with_country_code(code: str, number: str) -> str:
    """Compose the existing contact_phone field without doubling a pasted prefix."""
    raw = (number or "").strip()
    if not raw:
        return ""
    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    if compact.startswith("+"):
        return compact
    prefix = (code or "").strip()
    if prefix and not prefix.startswith("+"):
        prefix = "+" + prefix
    if re.fullmatch(r"\+[1-9][0-9]{0,3}", prefix) and compact.isdigit():
        return prefix + compact
    return raw
