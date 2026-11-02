"""RÚIAN address suggestions for the property form (0834 D).

Sends only the typed address text to ČÚZK. Nothing is stored. Every failure
returns an empty list, so the plain address fields always work without this.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import rate_limit

# TODO-verify: ČÚZK public GeocodeSOE endpoint and parameters. Not checked from the
# sandbox (outbound HTTPS is blocked there); confirm the URL before the owner merges.
_FIND_URL = "https://ags.cuzk.cz/arcgis/rest/services/GeocodeSOE/GeocodeServer/findAddressCandidates"

# TODO-verify: attribute keys of an address candidate in the ČÚZK response.
# Structured values only: never parse the display label.
_ATTR_KEYS = {
    "street": "StreetName",
    "house_no": "BuildingNumber",  # číslo popisné
    "orientation_no": "OrientationNumber",  # číslo orientační
    "zip": "PostalCode",  # PSČ
    "town": "Municipality",  # obec
    "district_part": "MunicipalityPart",  # část obce
    "okres": "District",  # okres
}

_TIMEOUT_SECONDS = 4
_USER_AGENT = "UbyHost"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_RATE_SCOPE = "ruian"
_RATE_LIMIT = 60
_RATE_WINDOW = 60 * 60
_MIN_CHARS = 3
_MAX_RESULTS = 6

_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def enabled() -> bool:
    """Feature switch: on unless UBYHOST_RUIAN_ENABLED is 0, false, no or off."""
    value = os.environ.get("UBYHOST_RUIAN_ENABLED", "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def usable_query(q: Optional[str]) -> Optional[str]:
    text = " ".join((q or "").split())
    return text if len(text) >= _MIN_CHARS else None


def rate_limited(owner_user_id: int) -> bool:
    return rate_limit.blocked(_RATE_SCOPE, str(owner_user_id), _RATE_LIMIT, _RATE_WINDOW)


def record_lookup(owner_user_id: int) -> None:
    rate_limit.record(_RATE_SCOPE, str(owner_user_id))


def _fields(attributes: Dict[str, Any]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for field, key in _ATTR_KEYS.items():
        value = attributes.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            fields[field] = text
    return fields


def suggest(q: str) -> List[Dict[str, Any]]:
    """Up to six ``{label, fields}`` suggestions. ``[]`` on error, short query or disabled."""
    text = usable_query(q)
    if text is None or not enabled():
        return []
    key = text.lower()
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        response = requests.get(
            _FIND_URL,
            params={"SingleLine": text, "outFields": "*", "maxLocations": _MAX_RESULTS, "f": "json"},
            timeout=_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
        if not response.ok:
            return []
        candidates = (response.json() or {}).get("candidates") or []
    except Exception:
        return []
    results: List[Dict[str, Any]] = []
    for candidate in candidates[:_MAX_RESULTS]:
        label = str(candidate.get("address") or "").strip()
        fields = _fields(candidate.get("attributes") or {})
        if label and fields:
            results.append({"label": label, "fields": fields})
    if len(_CACHE) > 1000:
        _CACHE.clear()
    _CACHE[key] = (now, results)
    return results
