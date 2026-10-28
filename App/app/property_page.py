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
