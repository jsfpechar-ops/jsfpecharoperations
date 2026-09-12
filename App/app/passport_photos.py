"""Temporary passport photos for host identity verification.

Photos are stored on disk only until the host confirms the data matches the
document, then deleted immediately (GDPR-safe). Only authenticated hosts can
read them via the admin route.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from app import config

PHOTOS_DIR = config.DATA_DIR / "passport_photos"
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _ensure_dir() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _paths_for(guest_id: int) -> list[Path]:
    return [PHOTOS_DIR / f"{guest_id}{ext}" for ext in ALLOWED_TYPES.values()]


def has_photo(guest_id: int) -> bool:
    return any(path.is_file() for path in _paths_for(guest_id))


def validate_upload(content: bytes, content_type: str) -> str:
    """Return the normalised MIME type or raise ValueError."""
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype not in ALLOWED_TYPES:
        raise ValueError("Upload a JPEG, PNG, or WebP photo of the passport ID page.")
    if len(content) > MAX_BYTES:
        raise ValueError("The photo is too large. Use a file under 5 MB.")
    if len(content) < 64:
        raise ValueError("The uploaded file looks empty.")
    return ctype


def save_photo(guest_id: int, content: bytes, content_type: str) -> None:
    """Replace any existing photo for this guest."""
    ctype = validate_upload(content, content_type)
    _ensure_dir()
    delete_photo(guest_id)
    target = PHOTOS_DIR / f"{guest_id}{ALLOWED_TYPES[ctype]}"
    target.write_bytes(content)
    try:
        target.chmod(0o600)
    except OSError:
        pass


def delete_photo(guest_id: int) -> None:
    for path in _paths_for(guest_id):
        if path.is_file():
            path.unlink()


def read_photo(guest_id: int) -> Optional[Tuple[bytes, str]]:
    for path in _paths_for(guest_id):
        if path.is_file():
            ext = path.suffix.lower()
            ctype = {
                ".jpg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(ext, "application/octet-stream")
            return path.read_bytes(), ctype
    return None
