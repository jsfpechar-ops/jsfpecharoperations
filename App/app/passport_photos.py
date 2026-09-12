"""Temporary passport photos for host identity verification.

Guests upload a photo, camera capture, or PDF (e.g. a multi-guest registration
form). Files stay on disk only until the host confirms the data matches the
document, then are deleted immediately (GDPR-safe). Only authenticated hosts can
read them via the admin route.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from app import config

PHOTOS_DIR = config.DATA_DIR / "passport_photos"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_PDF_TYPE = "application/pdf"
ALLOWED_TYPES = {**ALLOWED_IMAGE_TYPES, ALLOWED_PDF_TYPE: ".pdf"}
ALL_EXTENSIONS = tuple(sorted({ext for ext in ALLOWED_TYPES.values()}))


def _ensure_dir() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _paths_for(guest_id: int) -> list[Path]:
    return [PHOTOS_DIR / f"{guest_id}{ext}" for ext in ALL_EXTENSIONS]


def has_photo(guest_id: int) -> bool:
    return any(path.is_file() for path in _paths_for(guest_id))


def is_pdf_attachment(guest_id: int) -> bool:
    return (PHOTOS_DIR / f"{guest_id}.pdf").is_file()


def _looks_like_image(content: bytes, content_type: str) -> bool:
    if content_type in ("image/jpeg", "image/jpg") and content[:3] == b"\xff\xd8\xff":
        return True
    if content_type == "image/png" and content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if content_type == "image/webp" and len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    return False


def _looks_like_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF-")


def validate_upload(content: bytes, content_type: str) -> str:
    """Return the normalised MIME type or raise ValueError."""
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if ctype not in ALLOWED_TYPES:
        raise ValueError(
            "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF "
            "(for example a registration form with up to 11 guests)."
        )
    if len(content) < 64:
        raise ValueError("The uploaded file looks empty.")
    if ctype == ALLOWED_PDF_TYPE:
        if len(content) > MAX_PDF_BYTES:
            raise ValueError("The PDF is too large. Use a file under 15 MB.")
        if not _looks_like_pdf(content):
            raise ValueError("The file does not look like a valid PDF.")
        return ctype
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("The photo is too large. Use a file under 5 MB.")
    if not _looks_like_image(content, ctype):
        raise ValueError("The file does not look like a valid image.")
    return ctype


def save_photo(guest_id: int, content: bytes, content_type: str) -> None:
    """Replace any existing attachment for this guest."""
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
                ".pdf": ALLOWED_PDF_TYPE,
            }.get(ext, "application/octet-stream")
            return path.read_bytes(), ctype
    return None
