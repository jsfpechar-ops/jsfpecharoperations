"""Brief 0347: fetch a host's own Booking.com or Airbnb listing through Apify.

The pasted link is checked against a strict allowlist and rebuilt from its
parts, so nothing the host typed reaches an HTTP client. The worker runs one
Apify actor per queued row and stores a trimmed, size-capped copy of the text.
Brief 0348 reads it (``pending_for``) and calls ``mark_used``; ``purge`` drops
raw data after seven days at the latest. Listing text and the token are never
logged.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import requests

from . import config, db

log = logging.getLogger("ubyhost.guide_import")

# Apify's API host is a constant: the only URL this module ever opens.
APIFY_API = "https://api.apify.com/v2/acts/"
# Actor ids (owner~name) checked 2026-10-24 on apify.com; pay per result.
ACTORS = {
    "booking": "voyager~booking-scraper",
    "airbnb": "tri_angle~airbnb-rooms-urls-scraper",
}
MAX_URL_LENGTH = 2048
MAX_STORED_BYTES = 64 * 1024
MAX_TEXT = 4000
MAX_LIST_ITEMS = 80
MAX_ITEM_TEXT = 200
RAW_DAYS = 7
ROW_DAYS = 60
# Connect and read timeouts; the read side outlasts the actor timeout we ask
# Apify for, so Apify's own 408 arrives before ours.
HTTP_TIMEOUT = (10, 150)

_BOOKING_HOSTS = frozenset({"booking.com", "www.booking.com", "m.booking.com"})
_BOOKING_PATH = re.compile(r"^/hotel/([a-z]{2})/([a-z0-9][a-z0-9._-]{0,200})\.html$", re.IGNORECASE)
_AIRBNB_HOST = re.compile(
    r"^(?:www\.|m\.)?airbnb\.(?:com|cz|sk|de|at|pl|fr|it|es|nl|ch|hu|ie|ca|co\.uk|com\.au)$"
)
_AIRBNB_PATH = re.compile(r"^/rooms/(?:plus/)?([0-9]{1,20})/?$")


class GuideImportError(Exception):
    """A refusal the host sees; ``key`` is a host_i18n string."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


# --- the link -----------------------------------------------------------------


def normalise_url(raw: str) -> Dict[str, str]:
    """``{"source", "url"}`` for an allowed listing link, rebuilt from the matched
    parts only (fixed scheme and host, matched path); anything else is refused."""
    text = (raw or "").strip()
    if not text or len(text) > MAX_URL_LENGTH or not text.isascii():
        raise GuideImportError("flash.error.guide_import_link")
    if "@" in text or "\\" in text or any(c.isspace() for c in text):
        raise GuideImportError("flash.error.guide_import_link")
    parts = urlsplit(text)
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise GuideImportError("flash.error.guide_import_link")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or ":" in host or host.replace(".", "").isdigit():
        raise GuideImportError("flash.error.guide_import_link")
    path = parts.path or "/"
    if host in _BOOKING_HOSTS:
        match = _BOOKING_PATH.match(path)
        if not match:
            raise GuideImportError("flash.error.guide_import_booking_path")
        return {"source": "booking", "url": f"https://www.booking.com/hotel/{match.group(1).lower()}/{match.group(2)}.html"}
    if _AIRBNB_HOST.match(host):
        match = _AIRBNB_PATH.match(path)
        if not match:
            raise GuideImportError("flash.error.guide_import_airbnb_path")
        return {"source": "airbnb", "url": f"https://www.airbnb.com/rooms/{match.group(1)}"}
    raise GuideImportError("flash.error.guide_import_link")


# --- switches and budgets -----------------------------------------------------


def enabled() -> bool:
    return bool(config.APIFY_TOKEN)


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def used_sources(apartment_id: int) -> set:
    """Sources this property has imported. One import per listing per property, for good
    (owner, 2026-10-24): after it the host fills the rest by hand. A failed run does
    not use it up; the global run budget still counts it."""
    rows = db.query(
        "SELECT DISTINCT source FROM guide_import WHERE apartment_id = ? AND status != 'failed'",
        (apartment_id,),
    )
    return {r["source"] for r in rows}


def imports_left(apartment_id: int) -> int:
    return len(set(ACTORS) - used_sources(apartment_id))


def runs_this_month() -> int:
    row = db.query_one(
        "SELECT calls FROM lock_api_usage WHERE month = ? AND provider = 'apify'", (_month_key(),)
    )
    return int(row["calls"]) if row and row["calls"] is not None else 0


def _count_run() -> None:
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'apify', 1) "
        "ON CONFLICT (month, provider) DO UPDATE SET calls = calls + 1",
        (_month_key(),),
    )


def global_budget_left() -> bool:
    limit = config.APIFY_MONTHLY_RUNS
    return limit <= 0 or runs_this_month() < limit


# --- the queue ----------------------------------------------------------------


def request_import(apartment_id: int, raw_url: str) -> int:
    """Queue one import for a property the caller has checked; returns the row id."""
    if not enabled():
        raise GuideImportError("flash.error.guide_import_off")
    link = normalise_url(raw_url)
    if db.query_one(
        "SELECT id FROM guide_import WHERE apartment_id = ? AND status IN ('queued', 'running')",
        (apartment_id,),
    ):
        raise GuideImportError("flash.error.guide_import_busy")
    if link["source"] in used_sources(apartment_id):
        raise GuideImportError("flash.error.guide_import_limit")
    if not global_budget_left():
        raise GuideImportError("flash.error.guide_import_budget")
    return int(db.insert("guide_import", {
        "apartment_id": apartment_id, "source": link["source"], "url": link["url"],
        "status": "queued", "created_at": db.utcnow(),
    }) or 0)


def imports(apartment_id: int) -> List[Dict[str, Any]]:
    """Newest first, without the raw data."""
    rows = db.query(
        "SELECT id, source, url, status, error, created_at, finished_at FROM guide_import "
        "WHERE apartment_id = ? ORDER BY id DESC LIMIT 10",
        (apartment_id,),
    )
    return [dict(r) for r in rows]


def in_progress(apartment_id: int) -> bool:
    return any(r["status"] in ("queued", "running") for r in imports(apartment_id))


def pending_for(apartment_id: int) -> List[Dict[str, Any]]:
    """Handoff to brief 0348: fetched, unused imports with their data parsed."""
    rows = db.query(
        "SELECT id, source, url, raw_json, created_at FROM guide_import "
        "WHERE apartment_id = ? AND status = 'done' AND raw_json IS NOT NULL ORDER BY id",
        (apartment_id,),
    )
    out = []
    for r in rows:
        try:
            data = json.loads(r["raw_json"])
        except ValueError:
            continue
        out.append({"id": r["id"], "source": r["source"], "url": r["url"], "data": data})
    return out


def mark_used(import_id: int) -> None:
    """Brief 0348 calls this after drafting cards: the raw data goes at once."""
    db.execute(
        "UPDATE guide_import SET status = 'used', raw_json = NULL, used_at = ? WHERE id = ? AND status = 'done'",
        (db.utcnow(), import_id),
    )


# --- trimming -----------------------------------------------------------------

_TEXT_FIELDS = {
    "booking": ("name", "description", "checkIn", "checkOut"),
    "airbnb": ("title", "description", "subDescription", "propertyType", "roomType"),
}
_LIST_FIELDS = {
    "booking": (),
    "airbnb": ("amenities", "houseRules", "locationDescriptions", "highlights"),
}


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return " ".join(str(value).split())[:limit]


def _flatten(value: Any, out: List[str], depth: int = 0) -> None:
    """Collect the short strings of a nested list or dict (titles, rule lines)."""
    if len(out) >= MAX_LIST_ITEMS or depth > 6:
        return
    if isinstance(value, str):
        text = _text(value, MAX_ITEM_TEXT)
        if text and text not in out:
            out.append(text)
    elif isinstance(value, list):
        for item in value:
            _flatten(item, out, depth + 1)
    elif isinstance(value, dict):
        if value.get("available") is False:
            return
        for key in ("title", "content", "subtitle", "values", "additional", "general"):
            if key in value:
                _flatten(value[key], out, depth + 1)


def trim(source: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Named text fields, lists, address; size-capped."""
    if not isinstance(item, dict):
        return {}
    out: Dict[str, Any] = {"source": source}
    for key in _TEXT_FIELDS.get(source, ()):
        text = _text(item.get(key))
        if text:
            out[key] = text
    for key in _LIST_FIELDS.get(source, ()):
        lines: List[str] = []
        _flatten(item.get(key), lines)
        if lines:
            out[key] = lines
    address = item.get("address")
    if isinstance(address, dict):
        text = _text(address.get("full") or address.get("street"), 300)
        if text:
            out["address"] = text
    elif isinstance(address, str):
        out["address"] = _text(address, 300)
    encoded = json.dumps(out, ensure_ascii=False)
    while len(encoded.encode("utf-8")) > MAX_STORED_BYTES:
        for key, value in list(out.items()):
            if isinstance(value, list):
                out[key] = value[: max(1, len(value) // 2)]
            elif isinstance(value, str) and len(value) > 50:
                out[key] = value[: len(value) // 2]
        encoded = json.dumps(out, ensure_ascii=False)
    return out


# --- the worker side ----------------------------------------------------------


def _actor_input(source: str, url: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {"startUrls": [{"url": url}]}
    if source == "booking":
        body.update({"maxItems": 1, "language": "en-gb", "currency": "CZK"})
    return body


def _fetch(source: str, url: str) -> Dict[str, Any]:
    """One synchronous actor run. Raises GuideImportError with a short code."""
    actor = ACTORS[source]
    endpoint = f"{APIFY_API}{actor}/run-sync-get-dataset-items"
    params = {"timeout": config.APIFY_TIMEOUT, "maxItems": 1, "clean": "true", "format": "json"}
    headers = {"Authorization": f"Bearer {config.APIFY_TOKEN}", "Content-Type": "application/json"}
    try:
        response = requests.post(
            endpoint, params=params, headers=headers, timeout=HTTP_TIMEOUT,
            data=json.dumps(_actor_input(source, url)), allow_redirects=False,
        )
    except requests.RequestException:
        raise GuideImportError("network")
    if response.status_code == 408:
        raise GuideImportError("timeout")
    if response.status_code not in (200, 201):
        raise GuideImportError(f"http_{response.status_code}")
    if len(response.content) > 4 * 1024 * 1024:
        raise GuideImportError("too_large")
    try:
        items = response.json()
    except ValueError:
        raise GuideImportError("bad_json")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise GuideImportError("empty")
    return items[0]


def _run_one(row) -> None:
    import_id = row["id"]
    db.execute(
        "UPDATE guide_import SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
        (db.utcnow(), import_id),
    )
    _count_run()
    try:
        item = _fetch(row["source"], row["url"])
        data = trim(row["source"], item)
        if len(data) <= 1:
            raise GuideImportError("empty")
        db.execute(
            "UPDATE guide_import SET status = 'done', raw_json = ?, finished_at = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), db.utcnow(), import_id),
        )
        log.info("guide import id=%s source=%s done", import_id, row["source"])
    except GuideImportError as exc:
        db.execute(
            "UPDATE guide_import SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            (exc.key[:40], db.utcnow(), import_id),
        )
        log.warning("guide import id=%s source=%s failed kind=%s", import_id, row["source"], exc.key)


def process_queue(limit: int = 3) -> int:
    """Run queued imports, oldest first. Called by the worker every minute."""
    if not enabled():
        return 0
    rows = db.query(
        "SELECT id, apartment_id, source, url FROM guide_import WHERE status = 'queued' ORDER BY id LIMIT ?",
        (limit,),
    )
    done = 0
    for row in rows:
        if not global_budget_left():
            db.execute(
                "UPDATE guide_import SET status = 'failed', error = 'budget', finished_at = ? WHERE id = ?",
                (db.utcnow(), row["id"]),
            )
            continue
        _run_one(row)
        done += 1
    return done


# --- retention ----------------------------------------------------------------


def purge(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Raw data gone after RAW_DAYS; failed rows after ROW_DAYS. Other rows stay,
    without data, as the record that the listing was imported (one import for good)."""
    if owner_user_id is not None:
        return 0
    raw_cutoff = (today - timedelta(days=RAW_DAYS)).isoformat()
    row_cutoff = (today - timedelta(days=ROW_DAYS)).isoformat()
    stale = db.query_one(
        "SELECT COUNT(*) AS n FROM guide_import WHERE raw_json IS NOT NULL AND created_at < ?", (raw_cutoff,)
    )
    old = db.query_one(
        "SELECT COUNT(*) AS n FROM guide_import WHERE status = 'failed' AND created_at < ?", (row_cutoff,)
    )
    count = int(stale["n"] if stale else 0) + int(old["n"] if old else 0)
    if not dry_run and count:
        db.execute(
            "UPDATE guide_import SET raw_json = NULL, status = CASE WHEN status = 'done' THEN 'expired' ELSE status END "
            "WHERE raw_json IS NOT NULL AND created_at < ?",
            (raw_cutoff,),
        )
        db.execute("DELETE FROM guide_import WHERE status = 'failed' AND created_at < ?", (row_cutoff,))
    return count
