"""0293: photos on guest guide cards ("this is the boiler, press this button").

A photo is decoded and saved again as a fresh JPEG (``passport_photos.reencode_image``),
so no EXIF location or camera data survives, then shrunk to ``MAX_SIDE``. Files
live in ``DATA_DIR/guide_photos`` under a random name; the ``guide_photo`` row
ties a file to its card. Guides are host-written and meant for guests, so the
files are not encrypted. ``purge_orphans`` removes files whose row is gone
(a deleted card or property cascades the rows, not the files).
"""
from __future__ import annotations

import io
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from . import config, db, passport_photos
from .guest_guide import GuideError

PHOTOS_DIR = config.DATA_DIR / "guide_photos"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PER_ITEM = 6
MAX_SIDE = 1600
JPEG_QUALITY = 82
ALLOWED_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/webp")


def _dir() -> Path:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    return PHOTOS_DIR


def _shrink(content: bytes) -> bytes:
    with Image.open(io.BytesIO(content)) as image:
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def photos(apartment_id: int, item_id: int) -> List[Dict[str, Any]]:
    """The card's photos in upload order; empty for a card of another property."""
    rows = db.query(
        "SELECT p.* FROM guide_photo p JOIN guide_item i ON i.id = p.item_id "
        "WHERE p.item_id = ? AND i.apartment_id = ? ORDER BY p.sort_order, p.id",
        (item_id, apartment_id),
    )
    return [dict(row) for row in rows]


def get(apartment_id: int, item_id: int, photo_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT p.* FROM guide_photo p JOIN guide_item i ON i.id = p.item_id "
        "WHERE p.id = ? AND p.item_id = ? AND i.apartment_id = ?",
        (photo_id, item_id, apartment_id),
    )
    return dict(row) if row else None


def path_for(photo: Dict[str, Any]) -> Path:
    return PHOTOS_DIR / photo["file_name"]


def add(apartment_id: int, item_id: int, content: bytes, content_type: str) -> int:
    """Store one photo on the card; raises GuideError with a flash key."""
    if not db.query_one(
        "SELECT id FROM guide_item WHERE id = ? AND apartment_id = ?", (item_id, apartment_id)
    ):
        raise GuideError("flash.error.guide_no_such_item")
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype not in ALLOWED_TYPES or len(content) < 64:
        raise GuideError("flash.error.guide_photo_type")
    if len(content) > MAX_UPLOAD_BYTES:
        raise GuideError("flash.error.guide_photo_size")
    existing = photos(apartment_id, item_id)
    if len(existing) >= MAX_PER_ITEM:
        raise GuideError("flash.error.guide_photo_limit")
    try:
        clean = _shrink(passport_photos.reencode_image(content))
    except ValueError:
        raise GuideError("flash.error.guide_photo_type") from None
    name = secrets.token_hex(16) + ".jpg"
    target = _dir() / name
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(clean)
    os.replace(tmp, target)
    order = max((p["sort_order"] for p in existing), default=0) + 1
    return db.insert(
        "guide_photo",
        {"item_id": item_id, "file_name": name, "sort_order": order, "created_at": db.utcnow()},
    )


def delete(apartment_id: int, item_id: int, photo_id: int) -> bool:
    photo = get(apartment_id, item_id, photo_id)
    if not photo:
        return False
    db.execute("DELETE FROM guide_photo WHERE id = ?", (photo_id,))
    path_for(photo).unlink(missing_ok=True)
    return True


def purge_orphans() -> int:
    """Delete stored files no ``guide_photo`` row names any more; the count removed.

    A file younger than an hour is left alone: ``add`` writes the file before
    its row, so a sweep in between must not take it.
    """
    if not PHOTOS_DIR.is_dir():
        return 0
    known = {row["file_name"] for row in db.query("SELECT file_name FROM guide_photo")}
    cutoff = time.time() - 3600
    removed = 0
    for path in PHOTOS_DIR.iterdir():
        if path.is_file() and path.name not in known and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
