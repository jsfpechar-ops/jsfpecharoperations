"""Interpretation of UbyPort error codes.

The authoritative code book lives in the service itself and is fetched with
DejMiCiselnik(Chyby); it is cached in the `codelist` table. This module holds
the small set of codes documented in writing plus the classification the host
actually needs: can this record be fixed and resent, or not?

That distinction matters. As of 1 September 2025 the police re-enabled the
duplicate check and put duplicates in the "errors that cannot be corrected"
bucket alongside "reported late". Repeatedly resending duplicates without
reason is grounds for revoking web-service access, so the app must never
blind-retry a record the server has already accepted.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Documented explicitly in appendix 5, section 5.3.2. The full book is fetched
# from the service; these are the ones that must be understood even offline,
# because both of the uncorrectable outcomes live here.
KNOWN_CODES: Dict[str, str] = {
    "1": "Incorrect file extension",
    "106": "Invalid value in a guest field",
    "112": "Reported late - the three-working-day deadline had already passed",
    "150": "Duplicate record - the data was not taken over",
}

# Substrings that mark an error as pointless to retry.
NON_CORRECTABLE_MARKERS = ("duplic", "pozd", "late")

# Substrings that mean the record never reached the register at all.
REJECTED_MARKERS = ("nepřev", "neprev", "nepřijat", "neprijat", "reject")


def split_codes(raw: Optional[str]) -> List[str]:
    """"5;6;7;" -> ["5", "6", "7"]."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def describe(code: str, codebook: Optional[Dict[str, str]] = None) -> str:
    codebook = codebook or {}
    padded = code.zfill(3)
    for key in (code, padded, f"ERR_CZE_{padded}"):
        if key in codebook and codebook[key]:
            return codebook[key]
    if code in KNOWN_CODES:
        return KNOWN_CODES[code]
    return f"UbyPort error {code} (see the Doručenka for details)"


def is_non_correctable(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in NON_CORRECTABLE_MARKERS)


def is_duplicate(text: str) -> bool:
    """A duplicate means the register already holds the record."""
    lowered = (text or "").lower()
    return "duplic" in lowered or lowered.startswith("150:")


def classify(
    header_errors: Optional[str],
    record_errors: Optional[str],
    codebook: Optional[Dict[str, str]] = None,
) -> Tuple[str, List[str]]:
    """Return (state, human-readable messages) for one guest record.

    state is one of:
      "accepted"        - no errors reported
      "error"           - rejected, worth fixing and resending
      "not_correctable" - rejected or flagged in a way resending will not fix
    """
    messages: List[str] = []
    codes = split_codes(header_errors) + split_codes(record_errors)
    if not codes:
        return "accepted", messages

    non_correctable = False
    for code in codes:
        text = describe(code, codebook)
        messages.append(f"{code}: {text}")
        if is_non_correctable(text) or code in {"112", "150"}:
            non_correctable = True

    return ("not_correctable" if non_correctable else "error"), messages


def codebook_from_rows(rows) -> Dict[str, str]:
    """Build a code -> text map from cached `codelist` rows."""
    book: Dict[str, str] = {}
    for row in rows:
        code = (row["code"] or "").strip()
        text = (row["text_cs"] or row["text_en"] or "").strip()
        if not code:
            continue
        book[code] = text
        # The service returns codes as ERR_CZE_112 but reports them as "112".
        if code.upper().startswith("ERR_CZE_"):
            book[code.upper().replace("ERR_CZE_", "").lstrip("0") or "0"] = text
    return book
