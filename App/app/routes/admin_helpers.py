"""Shared parsing and redirect helpers for the host and guest route modules."""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse

from .. import host_i18n, validation


def back(path: str, msg: str = "", err: str = "") -> RedirectResponse:
    query = []
    if msg:
        query.append(f"msg={quote(msg)}")
    if err:
        query.append(f"err={quote(err)}")
    if not query:
        return RedirectResponse(path, status_code=303)
    qs = "&".join(query)
    if "#" in path:
        base, fragment = path.split("#", 1)
        sep = "&" if "?" in base else "?"
        return RedirectResponse(f"{base}{sep}{qs}#{fragment}", status_code=303)
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep}{qs}", status_code=303)


def flash(request, key: str, **params) -> str:
    """A flash message in the host's own language.

    ``back()`` carries the message through the query string, so it must already
    be a plain string by the time it gets there - which means a message has to
    be translated where it is raised, not where it is rendered.
    """
    return host_i18n.translate(host_i18n.lang_from_request(request), key, **params)


def flash_plural(request, key: str, n: int, **params) -> str:
    """A counted flash, in the one/few/many form its count needs."""
    return host_i18n.translate_plural(
        host_i18n.lang_from_request(request), key, n, **params
    )


def plural_param(request, key: str, n: int) -> str:
    """A counted fragment for a sentence that carries more than one count.

    "Sent 3 guest records across 2 stays" has two numbers that each need their
    own form, and Czech agrees them differently ("ve 2 pobytech", not "ve 2
    pobyty"), so the two halves are translated separately and the sentence
    around them stays fixed.
    """
    return host_i18n.translate_plural(host_i18n.lang_from_request(request), key, n)


def form_str(form, key: str, default: str = "") -> str:
    value = form.get(key)
    return (value or default).strip() if isinstance(value, str) else default


def _row_str(row, key: str, default: str = "") -> str:
    """One field of a sqlite3.Row, which unlike a dict raises on a missing key."""
    try:
        return row[key] or default
    except (KeyError, IndexError, TypeError):
        return default


def guest_form_raw(form, apartment: Optional[Dict] = None) -> Dict[str, str]:
    """The raw guest record a posted form describes.

    One extractor for the host entry form and the guest link: both post the same
    fields, and a field read in only one of them silently drops data from
    whichever path was forgotten.

    ``apartment`` is what makes the guest link differ: it supplies the property's
    default purpose of stay, because a guest has no reason to know the kodovnik.
    The host form posts a purpose explicitly and is left empty on purpose - a
    made-up code on a legally-required filing is worse than a validation error.
    """
    raw = {field: form_str(form, field) for field in validation.GUEST_TEXT_FIELDS}
    # The guest form says "this child travels on a parent's passport" with a
    # checkbox; the host form has no such box and the host types the marker into
    # the document field instead. Both end up as the same record.
    if form.get("child_in_passport"):
        raw["doc_number"] = validation.INPASS
    if not raw["purpose"] and apartment is not None:
        raw["purpose"] = _row_str(apartment, "default_purpose") or validation.DEFAULT_PURPOSE
    if raw["doc_number"] == validation.INPASS:
        raw["note"] = validation.note_for_parent_document(
            form_str(form, "parent_doc_number"), raw["note"]
        )
    return raw


def guest_form_payload(form, apartment: Optional[Dict] = None) -> Dict[str, str]:
    """The guest record a posted form describes, normalised and not clamped."""
    return validation.normalise_guest(guest_form_raw(form, apartment), clamp=False)


def kept_signature(posted: Optional[str], existing: Optional[str]) -> str:
    """The signature a save should end up with.

    A post that carries no usable signature - an empty pad, a re-rendered form,
    a value nothing here can render - must not replace a good stored one, and
    must never file junk as a collected signature.
    """
    posted = (posted or "").strip()
    if validation.is_valid_signature(posted):
        return posted
    kept = (existing or "").strip()
    if kept and validation.is_valid_signature(kept):
        return kept
    return posted


def stay_dates_from_form(form, fallback: Optional[Tuple[str, str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """stay_from/stay_to are hidden fields, so they arrive by hand or stale.

    Both forms carry the booking's own dates when the fields are empty, so a
    stale or missing hidden field cannot silently file the stay against the
    wrong window.
    """
    fallback_from, fallback_to = fallback or ("", "")
    return (
        form_str(form, "stay_from") or fallback_from or None,
        form_str(form, "stay_to") or fallback_to or None,
    )


def query_int(request: Request, key: str) -> Optional[int]:
    """A hand-edited query string must never produce a 500."""
    raw = (request.query_params.get(key) or "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def query_date(request: Request, key: str) -> str:
    raw = (request.query_params.get(key) or "").strip()
    parsed = validation.parse_iso_date(raw)
    return parsed.isoformat() if parsed else ""
