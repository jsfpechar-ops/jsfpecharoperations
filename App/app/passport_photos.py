"""Temporary passport photos for host identity verification.

Guests upload a photo, camera capture, or PDF (e.g. a multi-guest registration
form). Files stay on disk only until the host confirms the data matches the
document, then are deleted immediately. Only authenticated hosts can read them
via the admin route.

Verification is the happy path, not a guarantee: a host can simply never press
the button. ``purge_stale`` is the backstop that makes the promise true, and it
also clears files no guest row points at any more, which nothing else can reach.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

from app import config, db

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


# --- retention -----------------------------------------------------------
#
# A photo exists for one purpose: letting the host compare the form against the
# document before reporting. That purpose dies with the stay, so the file has
# to go even when the host never pressed Verify. The grace period is generous
# enough for a host who was away the week the guest checked out.
PHOTO_GRACE_DAYS = 30


def stale_cutoff(today: Optional[date] = None) -> date:
    return (today or date.today()) - timedelta(days=PHOTO_GRACE_DAYS)


def _orphan_ids() -> list[int]:
    """Files on disk that no guest row claims.

    Nothing in the app can offer to delete these, because every delete button
    is rendered from a guest row. Only a sweep can reach them.
    """
    if not PHOTOS_DIR.is_dir():
        return []
    found = set()
    for path in PHOTOS_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in ALL_EXTENSIONS:
            continue
        try:
            found.add(int(path.stem))
        except ValueError:
            continue
    if not found:
        return []
    marks = ", ".join("?" for _ in found)
    live = {
        int(row["id"])
        for row in db.query(f"SELECT id FROM guest WHERE id IN ({marks})", sorted(found))
    }
    return sorted(found - live)


def purge_stale(owner_user_id: Optional[int] = None, today: Optional[date] = None) -> int:
    """Delete photos whose stay is long over, plus any orphaned files.

    Clears ``passport_photo_at`` so the host stops being offered a photo that
    is no longer there, but never touches the rest of the guest row: that is a
    house book entry and has its own six-year duty.
    """
    rows = db.query(
        "SELECT g.id AS id, g.passport_photo_at AS marked FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE COALESCE(g.stay_to, r.date_to) < ? "
        "AND (? IS NULL OR a.owner_user_id = ?)",
        (stale_cutoff(today).isoformat(), owner_user_id, owner_user_id),
    )
    removed = 0
    for row in rows:
        guest_id = int(row["id"])
        if has_photo(guest_id):
            delete_photo(guest_id)
            removed += 1
        if row["marked"]:
            db.update("guest", guest_id, {"passport_photo_at": None})
    # Orphans belong to no workspace, so only the global sweep clears them.
    if owner_user_id is None:
        for guest_id in _orphan_ids():
            delete_photo(guest_id)
            removed += 1
    if removed:
        db.audit(
            "passport_photo_sweep",
            f"deleted {removed} passport image(s) with no remaining purpose",
            owner_user_id=owner_user_id,
        )
    return removed


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
