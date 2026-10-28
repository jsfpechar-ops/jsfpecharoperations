"""Property public pages: deterministic slugs + publication (brief 0430).

The slug is recomputed from the apartment row (name normalisation + a 4-char
hash of the id): no counter, no randomness, stable forever for a given name.
A rename moves the old slug to history so old links 301 to the new page;
the QR codes printed by 0345 keep working through the redirect.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, Optional

from . import db

_MAX_SLUG_NAME = 48
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def normalise_name(name: str) -> str:
    """ASCII-fold, lowercase, collapse separators, trim, cap length."""
    folded = unicodedata.normalize("NFKD", name or "")
    ascii_ = folded.encode("ascii", "ignore").decode("ascii").lower()
    parts = _SLUG_STRIP.split(ascii_)
    joined = "-".join(p for p in parts if p)
    return joined[:_MAX_SLUG_NAME].strip("-")


def slug_for(apartment_id: int, name: str) -> str:
    """name-xxxx: the deterministic slug for this apartment, forever."""
    suffix = hashlib.sha256(f"apartment:{apartment_id}".encode()).hexdigest()[:4]
    base = normalise_name(name) or "apartment"
    return f"{base}-{suffix}"


def ensure_slug(apartment_id: int) -> Dict[str, Any]:
    """Create or refresh the property_slug row; renames keep a 301 trail."""
    apartment = db.query_one(
        "SELECT id, internal_name FROM apartment WHERE id = ?", (apartment_id,)
    )
    if apartment is None:
        raise ValueError(f"apartment {apartment_id} does not exist")
    new_slug = slug_for(apartment_id, str(apartment["internal_name"] or ""))
    row = db.query_one(
        "SELECT * FROM property_slug WHERE apartment_id = ?", (apartment_id,)
    )
    now = db.utcnow()
    if row is None:
        db.insert(
            "property_slug",
            {
                "apartment_id": apartment_id,
                "slug": new_slug,
                "published": 0,
                "created_at": now,
                "updated_at": now,
            },
        )
    elif row["slug"] != new_slug:
        db.execute(
            "INSERT INTO property_slug_history (old_slug, apartment_id, created_at)"
            " VALUES (?, ?, ?)",
            (row["slug"], apartment_id, now),
        )
        db.execute(
            "UPDATE property_slug SET slug = ?, updated_at = ? WHERE apartment_id = ?",
            (new_slug, now, apartment_id),
        )
    return dict(account_row(apartment_id) or {})


def account_row(apartment_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM property_slug WHERE apartment_id = ?", (apartment_id,)
    )
    return dict(row) if row else None


def resolve(slug: str) -> Optional[Dict[str, Any]]:
    """(kind, data) resolution into one dict: history 301 first, then live.

    Returns {"redirect": <live slug>} for a history hit, the live row for a
    published page, {"missing": True} for an unpublished live slug, or None.
    """
    history = db.query_one(
        "SELECT apartment_id FROM property_slug_history WHERE old_slug = ?", (slug,)
    )
    if history is not None:
        live = db.query_one(
            "SELECT slug FROM property_slug WHERE apartment_id = ?",
            (history["apartment_id"],),
        )
        if live is not None:
            return {"redirect": live["slug"]}
    row = db.query_one("SELECT * FROM property_slug WHERE slug = ?", (slug,))
    if row is None:
        return None
    if not row["published"]:
        return {"missing": True, "apartment_id": row["apartment_id"]}
    return dict(row)


def publish(apartment_id: int, *, published: bool) -> None:
    ensure_slug(apartment_id)
    db.execute(
        "UPDATE property_slug SET published = ?, published_at = ?, updated_at = ?"
        " WHERE apartment_id = ?",
        (
            1 if published else 0,
            db.utcnow() if published else None,
            db.utcnow(),
            apartment_id,
        ),
    )


# --- page content (brief 0431: scrape prefill, no AI) ------------------------

import json as _json


def _page_row(apartment_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM property_page WHERE apartment_id = ?", (apartment_id,)
    )
    return dict(row) if row else None


def page_for(apartment_id: int) -> Dict[str, Any]:
    """The page row for this apartment, created empty on first use."""
    row = _page_row(apartment_id)
    if row is not None:
        return row
    now = db.utcnow()
    db.insert(
        "property_page",
        {"apartment_id": apartment_id, "created_at": now, "updated_at": now},
    )
    return _page_row(apartment_id)  # type: ignore[return-value]


def prefill_from_import(apartment_id: int, import_row: Dict[str, Any]) -> None:
    """Map import fields into page columns; empty fields only, never edits.

    Deterministic field mapping, no AI: the listing text lands verbatim in
    the named columns (already trimmed/capped by the 0347 import).
    """
    data = _json.loads(import_row["raw_json"] or "{}")
    page = page_for(apartment_id)
    now = db.utcnow()
    updates: Dict[str, Any] = {}
    if not page["description"]:
        text = data.get("description") or data.get("subDescription")
        if text:
            updates["description"] = str(text)
    if not page["checkin_text"] and data.get("checkIn"):
        updates["checkin_text"] = str(data["checkIn"])
    if not page["checkout_text"] and data.get("checkOut"):
        updates["checkout_text"] = str(data["checkOut"])
    if not page["amenities_json"] and isinstance(data.get("amenities"), list):
        updates["amenities_json"] = _json.dumps(data["amenities"], ensure_ascii=False)
    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        db.execute(
            f"UPDATE property_page SET {sets}, updated_at = ? WHERE apartment_id = ?",
            (*updates.values(), now, apartment_id),
        )


def save_page(apartment_id: int, *, description: str, amenities: list) -> None:
    """The host's review-screen save: overwrites, this is the host writing."""
    page_for(apartment_id)
    db.execute(
        "UPDATE property_page SET description = ?, amenities_json = ?, updated_at = ?"
        " WHERE apartment_id = ?",
        (
            description or None,
            _json.dumps(amenities, ensure_ascii=False) if amenities else None,
            db.utcnow(),
            apartment_id,
        ),
    )


def publish_page(apartment_id: int, *, published: bool) -> None:
    db.execute(
        "UPDATE property_page SET published = ?, published_at = ?, updated_at = ?"
        " WHERE apartment_id = ?",
        (1 if published else 0, db.utcnow() if published else None,
         db.utcnow(), apartment_id),
    )
    publish(apartment_id, published=published)


# --- OTA photos (brief 0432: download once, re-host, never hotlink) ------------

import os as _os
import secrets as _secrets
from pathlib import Path as _Path

import requests as _requests

from . import config as _config
from . import guide_photos as _guide_photos

MAX_PAGE_PHOTOS = 10
_PHOTO_TIMEOUT = (5, 30)


def photos_dir() -> _Path:
    d = _config.DATA_DIR / "property_photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_photo(content: bytes) -> str:
    """Re-encode + shrink through the 0343 pipeline (EXIF stripped), store,
    return the public path. Raises ValueError on type/size refusal."""
    from . import passport_photos

    if len(content) < 64 or len(content) > _guide_photos.MAX_UPLOAD_BYTES:
        raise ValueError("photo_size")
    try:
        clean = _guide_photos._shrink(passport_photos.reencode_image(content))
    except ValueError:
        raise ValueError("photo_type") from None
    name = _secrets.token_hex(16) + ".jpg"
    target = photos_dir() / name
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(clean)
    _os.replace(tmp, target)
    return f"/photos/property/{name}"


def download_listing_photos(apartment_id: int, urls: list) -> int:
    """Download the OTA listing's photos once (the host's own import run),
    re-host up to MAX_PAGE_PHOTOS of them. Returns the stored count."""
    stored = []
    page = page_for(apartment_id)
    already = _json.loads(page["photos_json"] or "[]")
    for url in [u for u in urls if isinstance(u, str) and u.startswith("https://")]:
        if len(already) + len(stored) >= MAX_PAGE_PHOTOS:
            break
        try:
            response = _requests.get(url, timeout=_PHOTO_TIMEOUT)
            if response.status_code != 200:
                continue
            path = store_photo(response.content)
        except (ValueError, _requests.RequestException):
            continue
        stored.append(path)
    if stored:
        merged = already + stored
        db.execute(
            "UPDATE property_page SET photos_json = ?, updated_at = ? WHERE apartment_id = ?",
            (_json.dumps(merged[:MAX_PAGE_PHOTOS], ensure_ascii=False),
             db.utcnow(), apartment_id),
        )
    return len(stored)


def delete_photo(apartment_id: int, path: str) -> None:
    page = _page_row(apartment_id)
    if page is None:
        return
    photos = _json.loads(page["photos_json"] or "[]")
    if path not in photos:
        return
    photos.remove(path)
    db.execute(
        "UPDATE property_page SET photos_json = ?, updated_at = ? WHERE apartment_id = ?",
        (_json.dumps(photos, ensure_ascii=False), db.utcnow(), apartment_id),
    )
    name = path.rsplit("/", 1)[-1]
    target = photos_dir() / name
    if target.is_file():
        target.unlink()


# --- sitemap / search visibility / preview (brief 0433) -----------------------


def published_pages() -> list:
    """Published + search-visible pages for the sitemap."""
    return [
        dict(r)
        for r in db.query(
            "SELECT ps.slug, pp.published_at, pp.hide_from_search"
            " FROM property_slug ps JOIN property_page pp ON pp.apartment_id = ps.apartment_id"
            " WHERE ps.published = 1 AND COALESCE(pp.hide_from_search, 0) = 0"
            " ORDER BY ps.slug"
        )
    ]
