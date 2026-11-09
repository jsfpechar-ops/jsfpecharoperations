"""RÚIAN address suggestions for the property form (0884 D).

Sends only the typed address text to ČÚZK. Nothing is stored. Every failure
returns an empty list, so the plain address fields always work without this.
"""
from __future__ import annotations

import os
import time
from concurrent import futures
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import rate_limit

# Verified against the live ČÚZK service on 2026-11-09. Geocoder candidates carry
# only label and S-JTSK (wkid 102067) point; structure comes from RÚIAN layer queries.
# Override the geocoder URL with UBYHOST_RUIAN_URL; turn the feature off with
# UBYHOST_RUIAN_ENABLED=0.
_LAYER_BASE = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/Vyhledavaci_sluzba_nad_daty_RUIAN/MapServer"
_DEFAULT_URL = _LAYER_BASE + "/exts/GeocodeSOE/tables/1/findAddressCandidates"


def _find_url() -> str:
    return os.environ.get("UBYHOST_RUIAN_URL", "").strip() or _DEFAULT_URL

_TIMEOUT_SECONDS = 4
_USER_AGENT = "UbyHost"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_RATE_SCOPE = "ruian"
_RATE_LIMIT = 60
_RATE_WINDOW = 60 * 60
_MIN_CHARS = 3
_MAX_RESULTS = 6
_MIN_SCORE = 60
_SRID = 102067
_ADDRESS_TYPE = "AdresniMisto"
_ADDRESS_FIELDS = "kod,cislodomovni,cisloorientacni,cisloorientacnipismeno,psc,ulice,adresa"

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


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """JSON object from a GET, or ``{}`` on any error or non-ok response."""
    try:
        response = requests.get(
            url,
            params=params,
            timeout=_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
        if not response.ok:
            return {}
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _layer_query(layer: int, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attribute rows of one RÚIAN layer query (no geometry returned)."""
    payload = _get_json(f"{_LAYER_BASE}/{layer}/query", dict(params, returnGeometry="false", f="json"))
    features = payload.get("features") or []
    return [
        feature["attributes"]
        for feature in features
        if isinstance(feature, dict) and isinstance(feature.get("attributes"), dict)
    ]


def _first(rows: List[Dict[str, Any]], key: str) -> str:
    for row in rows:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _point_params(location: Any) -> Optional[Dict[str, Any]]:
    """Layer query geometry from a candidate's S-JTSK point, or None."""
    if not isinstance(location, dict):
        return None
    try:
        x = float(location["x"])
        y = float(location["y"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "geometry": f"{x},{y}",
        "geometryType": "esriGeometryPoint",
        "inSR": _SRID,
        "spatialRel": "esriSpatialRelIntersects",
    }


def _keep(candidate: Any) -> bool:
    """Geocoder filter: a labelled candidate, score at least 60, and an address point."""
    if not isinstance(candidate, dict) or not _text(candidate.get("address")):
        return False
    try:
        if float(candidate.get("score") or 0) < _MIN_SCORE:
            return False
    except (TypeError, ValueError):
        return False
    attributes = candidate.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
    return attributes.get("Type") in (None, _ADDRESS_TYPE)


def _resolve(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One geocoder candidate -> ``{label, fields}`` from RÚIAN layers, or None."""
    try:
        address = _text(candidate.get("address"))
        point = _point_params(candidate.get("location"))
        if not address or point is None:
            return None
        rows = _layer_query(1, dict(point, distance=2, units="esriSRUnit_Meter", outFields=_ADDRESS_FIELDS))
        row = next((r for r in rows if _text(r.get("adresa")) == address), None)
        if row is None:
            return None
        fields: Dict[str, str] = {}
        house_no = _text(row.get("cislodomovni"))
        if house_no:
            fields["addr_house_no"] = house_no
        orient_no = _text(row.get("cisloorientacni"))
        if orient_no:
            fields["addr_orient_no"] = orient_no + _text(row.get("cisloorientacnipismeno"))
        zip_code = _text(row.get("psc")).replace(" ", "")
        if zip_code:
            fields["addr_zip"] = zip_code
        if row.get("ulice") is not None:
            street = _first(_layer_query(4, {"where": f"kod={int(row['ulice'])}", "outFields": "nazev"}), "nazev")
            if street:
                fields["addr_street"] = street
        obec_rows = _layer_query(12, dict(point, outFields="nazev,okres"))
        obec = _first(obec_rows, "nazev")
        if obec:
            fields["addr_obec"] = obec
            okres = ""
            okres_code = _first(obec_rows, "okres")
            if okres_code:
                okres = _first(_layer_query(15, {"where": f"kod={int(okres_code)}", "outFields": "nazev"}), "nazev")
            if not okres and obec == "Praha":
                okres = "Hlavní město Praha"
            if okres:
                fields["addr_okres"] = okres
        # Narrow label use: only the middle segment of a 3-part label, only when it differs
        # from the obec name; no other label parsing.
        segments = [part.strip() for part in address.split(",")]
        if len(segments) == 3 and segments[1] and segments[1] != fields.get("addr_obec"):
            fields["addr_obec_cast"] = segments[1]
        if "addr_house_no" not in fields and "addr_street" not in fields:
            return None
        return {"label": address, "fields": fields}
    except Exception:
        return None


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
            _find_url(),
            params={"SingleLine": text, "outFields": "*", "maxLocations": _MAX_RESULTS, "f": "json"},
            timeout=_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
        if not response.ok:
            return []
        candidates = (response.json() or {}).get("candidates") or []
    except Exception:
        return []
    if not isinstance(candidates, list):
        candidates = []
    kept = [candidate for candidate in candidates if _keep(candidate)][:_MAX_RESULTS]
    resolved: Dict[int, Dict[str, Any]] = {}
    if kept:
        pool = futures.ThreadPoolExecutor(max_workers=_MAX_RESULTS)
        try:
            pending = {pool.submit(_resolve, candidate): index for index, candidate in enumerate(kept)}
            done, _ = futures.wait(pending, timeout=_TIMEOUT_SECONDS)
            for future in done:
                item = future.result() if future.exception() is None else None
                if item is not None:
                    resolved[pending[future]] = item
        finally:
            pool.shutdown(wait=False)
    results = [resolved[index] for index in sorted(resolved)]
    if len(_CACHE) > 1000:
        _CACHE.clear()
    _CACHE[key] = (now, results)
    return results
