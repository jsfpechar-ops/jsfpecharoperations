"""Interpretation of UbyPort error codes.

The authoritative code book lives in the service itself and is fetched with
DejMiCiselnik(Chyby); it is cached in the `codelist` table. This module holds
the small set of codes that must be understood offline plus the rule that
decides what a code means for the guest record.

The rule comes from the Foreign Police in writing (ŘSCP, č. j.
CPR-34587-2/ČJ-2026-930023, 24 September 2026, answers A1-A5): the Chyby code
book is complete and binding, and **the decision depends only on the severity
("síla chyby")** that the code book gives each code:

* severity 0-2: the record **was accepted**. 0 is information for the user,
  1-2 ask the user to correct the value in their own records. Nothing is resent.
* severity 4-6: the record **was not accepted**. The host corrects the data and
  sends only the refused records again, in a new batch (answer C3).

112 is "Oznámeno pozdě" (reported late) with severity 0, so a late record is in
the register. An earlier reading of 112 as "critical transmission error, batch
not received" was wrong and is withdrawn: resending a 112 produces a duplicate.

A duplicate (150) is a refusal (severity 4), but it proves the register already
holds the record (answer C2), so the host application counts it as filed. The
police key duplicates on: dates from-to, surname, first name, date of birth,
nationality, travel document number and purpose of stay (answer A3). Note,
visa number and address are not compared.

Automatic resending of records the register refused raises the host's error
count with the police (answers B2-B3), so a refused record is never resent
blindly: the host has to change the data first.
"""
from __future__ import annotations

import re

from typing import Dict, List, Optional, Tuple

# Documented explicitly in appendix 5, section 5.3.2, or in the police letter.
# The full book is fetched from the service; these are the ones that must be
# understood even offline.
#
# The wording of a value must not contain a marker from
# NON_CORRECTABLE_MARKERS below: describe() falls back to these strings and
# classify() substring-matches the result for codes of unknown severity.
KNOWN_CODES: Dict[str, str] = {
    "1": "Incorrect file extension",
    "106": "Invalid value in a guest field",
    "112": "Reported after the deadline - the record was accepted",
    "150": "Duplicate record - the register already holds it",
}

# Severity ("síla chyby") of the codes above, used when the live code book has
# not been fetched yet. Appendix 5 section 5.3.2 prints 001 and 112 with
# severity 0; the police letter of 24 September 2026 lists the duplicate rows
# with severity 4. A code with no known severity is treated as a refusal.
KNOWN_SEVERITY: Dict[str, int] = {"1": 0, "112": 0, "150": 4}

# Highest severity at which the police say the record is accepted (answer A1-A2).
ACCEPTED_MAX_SEVERITY = 2

# Substrings that mark an error as pointless to retry. Only consulted for codes
# whose severity says "not accepted" or is unknown.
#
# WARNING: this is substring matching, not code matching. `describe()` prefers
# the live code book text over KNOWN_CODES, so when the police reword an entry
# the classification of the code changes with it, with no change here.
NON_CORRECTABLE_MARKERS = ("duplic", "pozd", "late")

# Whole-word forms of the markers above. A bare substring match made
# "později" (later) and "related"/"calculated" look like "late".
_NON_CORRECTABLE_RE = re.compile(r"duplic|\bpozdě\b|\bpozdn\w*|\blate\b", re.IGNORECASE)

# What the host reads when the live code book has no entry for a code. It names
# where the explanation comes from, because a rejected report has no Doručenka
# to point at: the only PDF it produced is the error report.
FALLBACK_TEXT: Dict[str, str] = {
    "en": "UbyPort error %(code)s — refresh code lists on the property page to see the explanation.",
    "cs": "Chyba UbyPortu %(code)s — vysvětlení uvidíte po obnovení číselníků na stránce ubytování.",
}

_ERR_PREFIX = re.compile(r"^ERR_CZE_", re.IGNORECASE)


def normalise_code(code: str) -> str:
    """"ERR_CZE_112", "0112" and "112" all become "112"."""
    bare = _ERR_PREFIX.sub("", (code or "").strip())
    return bare.lstrip("0") or ("0" if bare else "")


def split_codes(raw: Optional[str]) -> List[str]:
    """"5;6;7;" -> ["5", "6", "7"]."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(";") if part.strip()]


def describe(
    code: str, codebook: Optional[Dict[str, str]] = None, lang: str = "en"
) -> str:
    codebook = codebook or {}
    padded = code.zfill(3)
    for key in (code, padded, f"ERR_CZE_{padded}"):
        if key in codebook and codebook[key]:
            return codebook[key]
    if code in KNOWN_CODES:
        return KNOWN_CODES[code]
    return FALLBACK_TEXT.get(lang, FALLBACK_TEXT["en"]) % {"code": code}


def severity(code: str, severities: Optional[Dict[str, int]] = None) -> Optional[int]:
    """The police severity of a code, or None when nobody has told us."""
    key = normalise_code(code)
    if severities and key in severities:
        return severities[key]
    return KNOWN_SEVERITY.get(key)


def is_accepted_code(code: str, severities: Optional[Dict[str, int]] = None) -> bool:
    """Whether the register accepted a record that carries this code."""
    value = severity(code, severities)
    return value is not None and value <= ACCEPTED_MAX_SEVERITY


def is_non_correctable(text: str) -> bool:
    """Whether a code's description means resending it cannot succeed.

    Substring matching on purpose-built markers; see NON_CORRECTABLE_MARKERS for
    why that is fragile. Never consulted for a code the register accepted.
    """
    lowered = (text or "").lower()
    return bool(_NON_CORRECTABLE_RE.search(lowered))


def is_duplicate(text: str) -> bool:
    """A duplicate means the register already holds the record."""
    lowered = (text or "").lower()
    return "duplic" in lowered or lowered.startswith("150:")


def is_duplicate_code(code: str, codebook: Optional[Dict[str, str]] = None) -> bool:
    """Whether this record-level code is the register's duplicate answer.

    150 is the documented code. The police code book also names duplicate rows
    ("Duplicitní záznam ...") whose number we only see once it is fetched, so
    the cached police text for the code itself counts too. Only the code book's
    own entry for the code is read, never free text from elsewhere.
    """
    key = normalise_code(code)
    if key == "150":
        return True
    if not codebook:
        return False
    padded = key.zfill(3)
    for candidate in (key, padded, f"ERR_CZE_{padded}"):
        text = codebook.get(candidate)
        if text:
            return text.strip().lower().startswith("duplic")
    return False


def record_is_duplicate(record_errors: Optional[str], codebook: Optional[Dict[str, str]] = None) -> bool:
    """Whether this record's own codes include the duplicate answer."""
    return any(is_duplicate_code(code, codebook) for code in split_codes(record_errors))


def classify(
    header_errors: Optional[str],
    record_errors: Optional[str],
    codebook: Optional[Dict[str, str]] = None,
    lang: str = "en",
    severities: Optional[Dict[str, int]] = None,
) -> Tuple[str, List[str]]:
    """Return (state, human-readable messages) for one guest record.

    state is one of:
      "accepted"        - no errors, or only codes of severity 0-2 (the record
                          is in the register; messages carry the notes)
      "error"           - not accepted, worth fixing and resending
      "not_correctable" - not accepted in a way resending will not fix

    ``lang`` only chooses the wording of the messages. The state is decided from
    severities and the English text, so translating the display can never
    change what the app is willing to resend.
    """
    messages: List[str] = []
    codes = split_codes(header_errors) + split_codes(record_errors)
    if not codes:
        return "accepted", messages

    refused = False
    non_correctable = False
    for code in codes:
        text = describe(code, codebook)
        shown = text if lang == "en" else describe(code, codebook, lang)
        messages.append(f"{code}: {shown}")
        if is_accepted_code(code, severities):
            continue
        refused = True
        if normalise_code(code) == "150" or is_non_correctable(text):
            non_correctable = True

    if not refused:
        return "accepted", messages
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
            book[normalise_code(code)] = text
    return book


def severities_from_rows(rows) -> Dict[str, int]:
    """Build a code -> severity map from cached `codelist` rows.

    The severity is stored in ``extra`` for the error list (TextKratkyCZ in the
    service's answer, see appendix 5 section 5.3.2).
    """
    out: Dict[str, int] = {}
    for row in rows:
        code = normalise_code(row["code"] or "")
        raw = (row["extra"] or "").strip()
        if code and raw.isdigit():
            out[code] = int(raw)
    return out
