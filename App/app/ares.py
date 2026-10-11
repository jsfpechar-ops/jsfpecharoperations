"""Czech business register (ARES) lookup for host forms. Sends only the IČO."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import rate_limit, validation

_API_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"
_TIMEOUT_SECONDS = 4
_USER_AGENT = "UbyHost"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_RATE_SCOPE = "ares"
_RATE_LIMIT = 20
_RATE_WINDOW = 60 * 60

_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}

_COURTS = {
    "MSPH": "Městského soudu v Praze",
    "KSBR": "Krajského soudu v Brně",
    "KSOS": "Krajského soudu v Ostravě",
    "KSPH": "Krajského soudu v Praze",
    "KSPL": "Krajského soudu v Plzni",
    "KSUL": "Krajského soudu v Ústí nad Labem",
    "KSHK": "Krajského soudu v Hradci Králové",
    "KSCB": "Krajského soudu v Českých Budějovicích",
}


def rate_limited(owner_user_id: int) -> bool:
    return rate_limit.blocked(_RATE_SCOPE, str(owner_user_id), _RATE_LIMIT, _RATE_WINDOW)


def record_lookup(owner_user_id: int) -> None:
    rate_limit.record(_RATE_SCOPE, str(owner_user_id))


def merge_blank(target: Dict[str, Any], source: Dict[str, Any], fields: Tuple[str, ...]) -> List[str]:
    """Copy ``source`` into ``target`` only for empty fields. Returns filled field names."""
    filled: List[str] = []
    for field in fields:
        if str(target.get(field) or "").strip():
            continue
        value = source.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        target[field] = value if isinstance(value, str) else text
        filled.append(field)
    return filled


def format_registry_mark(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if "/" not in text:
        return text
    mark, court_code = text.rsplit("/", 1)
    mark = mark.strip()
    court_code = court_code.strip()
    court = _COURTS.get(court_code)
    if not court:
        return text
    return f"spisová značka {mark} vedená u {court}"


def _street(sidlo: Dict[str, Any]) -> str:
    name = (sidlo.get("nazevUlice") or "").strip()
    if not name:
        return ""
    parts = [name]
    cd = sidlo.get("cisloDomovni")
    co = sidlo.get("cisloOrientacni")
    letter = (sidlo.get("cisloOrientacniPismeno") or "").strip()
    if cd is not None and co is not None:
        parts.append(f"{cd}/{co}{letter}")
    elif cd is not None:
        parts.append(str(cd))
    return " ".join(parts)


def _registry_entry(payload: Dict[str, Any]) -> str:
    for block in payload.get("dalsiUdaje") or []:
        if (block.get("datovyZdroj") or "").lower() != "vr":
            continue
        raw = block.get("spisovaZnacka")
        if isinstance(raw, str) and raw.strip():
            return format_registry_mark(raw.strip())
    return ""


def _map_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sidlo = payload.get("sidlo") or {}
    seat = (sidlo.get("textovaAdresa") or "").strip()
    zip_code = sidlo.get("psc")
    zip_text = str(zip_code).strip() if zip_code is not None else ""
    if zip_text and len(zip_text) < 5 and zip_text.isdigit():
        zip_text = zip_text.zfill(5)
    registrace = payload.get("seznamRegistraci") or {}
    vat_active = (registrace.get("stavZdrojeDph") or "").upper() == "AKTIVNI"
    return {
        "name": (payload.get("obchodniJmeno") or "").strip(),
        "seat": seat,
        "street": _street(sidlo),
        "city": (sidlo.get("nazevObce") or "").strip(),
        "zip": zip_text,
        "country": "CZE",
        "dic": (payload.get("dic") or "").strip() or None,
        "vat_payer": vat_active,
        "registry_entry": _registry_entry(payload),
    }


def lookup(ico: str) -> Optional[Dict[str, Any]]:
    """Return mapped ARES data or None on any failure (including invalid IČO)."""
    text = (ico or "").strip()
    if not validation.ico_ok(text):
        return None
    now = time.time()
    cached = _CACHE.get(text)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    data: Optional[Dict[str, Any]] = None
    try:
        response = requests.get(
            _API_URL.format(ico=text),
            timeout=_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
        if response.status_code == 404:
            data = None
        elif response.ok:
            data = _map_payload(response.json())
            if not data.get("name"):
                data = None
        else:
            data = None
    except Exception:
        data = None
    _CACHE[text] = (now, data)
    return data
