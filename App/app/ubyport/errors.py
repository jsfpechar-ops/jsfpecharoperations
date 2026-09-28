"""Interpretation of UbyPort error codes.

The authoritative code book lives in the service itself and is fetched with
DejMiCiselnik(Chyby); it is cached in the `codelist` table. This module holds
the small set of codes documented in writing plus the classification the host
actually needs: can this record be fixed and resent, or not?

That distinction matters. As of 1 September 2025 the police re-enabled the
duplicate check, and a duplicate (150) proves the register already holds the
record, so resending it cannot succeed. Repeatedly resending duplicates without
reason is grounds for revoking web-service access, so the app must never
blind-retry a record the server has already accepted.

112 is the opposite case and must not be confused with it. The Foreign Police
answered this in writing: in the UBYPORT application 112 is a *critical
transmission error* (the 1xx series) meaning **the batch was not received at
all**. Typical causes are a structural fault in the submitted file, an empty
mandatory field, or a connection interrupted during upload. The remedy they
give is to check the guest's card and repeat the submission. Nothing reached
the register, so 112 is correctable and the record must stay retryable; see
CORRECTABLE_CODES below.
"""
from __future__ import annotations

import re

from typing import Dict, List, Optional, Tuple

# Documented explicitly in appendix 5, section 5.3.2. The full book is fetched
# from the service; these are the ones that must be understood even offline,
# because the codes the host has to act on live here.
#
# The wording of a value must not contain a marker from
# NON_CORRECTABLE_MARKERS below: describe() falls back to these strings and
# classify() substring-matches the result, so a careless wording would silently
# reclassify the code. test_soap.py pins that for 112.
KNOWN_CODES: Dict[str, str] = {
    "1": "Incorrect file extension",
    "106": "Invalid value in a guest field",
    "112": (
        "Critical transmission error (1xx series) - the register did not receive "
        "the batch. Check the guest's nationality, date of birth and document "
        "number, then repeat the submission"
    ),
    "150": "Duplicate record - the data was not taken over",
}

# Substrings that mark an error as pointless to retry.
#
# WARNING: this is substring matching, not code matching. `describe()` prefers
# the live code book text over KNOWN_CODES, so when the police reword an entry
# the classification of the code changes with it, with no change here. It
# matches the code book's Czech or English prose, and the markers are short
# enough to appear inside unrelated words.
NON_CORRECTABLE_MARKERS = ("duplic", "pozd", "late")

# Whole-word forms of the markers above. A bare substring match made
# "později" (later) and "related"/"calculated" look like "late".
_NON_CORRECTABLE_RE = re.compile(r"duplic|\bpozdě\b|\bpozdn\w*|\blate\b", re.IGNORECASE)

# Codes whose classification the owner settled in writing and which therefore
# win over the code book prose.
#
# 112: the Foreign Police confirmed in writing that in UBYPORT it is a critical
# transmission error (1xx series) meaning the batch was not received at all, so
# the record is correctable and the remedy is fix-and-resend. That answer is
# authoritative over both the wording this module used to carry and whatever
# prose the live code book holds for the code: a text change there must not
# quietly turn a record the register never received into one we abandon.
#
# Only 112 is listed. The police describe 1xx as a series, but no code book
# entry tells us the other 1xx codes mean "nothing was received", and
# blind-retrying a batch the service did accept is what the docstring above
# warns can cost the host web-service access. Unrecognised codes already
# classify as correctable, so nothing is abandoned while we wait for the book.
CORRECTABLE_CODES = {"112"}

# What the host reads when the live code book has no entry for a code. It names
# where the explanation comes from, because a rejected report has no Doručenka
# to point at: the only PDF it produced is the error report.
FALLBACK_TEXT: Dict[str, str] = {
    "en": "UbyPort error %(code)s — refresh code lists on the property page to see the explanation.",
    "cs": "Chyba UbyPortu %(code)s — vysvětlení uvidíte po obnovení číselníků na stránce ubytování.",
}


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


def is_non_correctable(text: str) -> bool:
    """Whether a code's description means resending it cannot succeed.

    Substring matching on purpose-built markers; see NON_CORRECTABLE_MARKERS for
    why that is fragile and CORRECTABLE_CODES for the codes that bypass it.
    """
    lowered = (text or "").lower()
    return bool(_NON_CORRECTABLE_RE.search(lowered))


def is_duplicate(text: str) -> bool:
    """A duplicate means the register already holds the record."""
    lowered = (text or "").lower()
    return "duplic" in lowered or lowered.startswith("150:")


def classify(
    header_errors: Optional[str],
    record_errors: Optional[str],
    codebook: Optional[Dict[str, str]] = None,
    lang: str = "en",
) -> Tuple[str, List[str]]:
    """Return (state, human-readable messages) for one guest record.

    state is one of:
      "accepted"        - no errors reported
      "error"           - rejected, worth fixing and resending
      "not_correctable" - rejected or flagged in a way resending will not fix

    ``lang`` only chooses the wording of the messages. The state is decided from
    the English text, so translating the display can never change what the app
    is willing to resend.
    """
    messages: List[str] = []
    codes = split_codes(header_errors) + split_codes(record_errors)
    if not codes:
        return "accepted", messages

    non_correctable = False
    for code in codes:
        text = describe(code, codebook)
        shown = text if lang == "en" else describe(code, codebook, lang)
        messages.append(f"{code}: {shown}")
        if code in CORRECTABLE_CODES:
            continue
        if is_non_correctable(text) or code in {"150"}:
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
