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

import io
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageOps

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
# WP08: every accepted image is decoded and saved again as a fresh JPEG, so no
# metadata (EXIF GPS, camera serial, comments) and no trailing payload survives.
# The bound is per upload and checked from the header before any pixel is
# decoded. 40 MP takes a full-resolution 24 MP phone photo with room to spare;
# anything larger in under 5 MB is far more likely a decompression bomb.
MAX_IMAGE_PIXELS = 40_000_000
STORED_IMAGE_TYPE = "image/jpeg"
JPEG_QUALITY = 90
_DECODABLE_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
# BE-12: stored files are Fernet-encrypted and carry this suffix. A plaintext
# file is a legacy one the migration has not reached yet; reads accept both.
ENC_SUFFIX = ".enc"


def _ensure_dir() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _paths_for(guest_id: int) -> list[Path]:
    paths: list[Path] = []
    for ext in ALL_EXTENSIONS:
        paths.append(PHOTOS_DIR / f"{guest_id}{ext}{ENC_SUFFIX}")
        paths.append(PHOTOS_DIR / f"{guest_id}{ext}")
    return paths


def _ctype_for(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": ALLOWED_PDF_TYPE,
    }.get(ext.lower(), "application/octet-stream")


def has_photo(guest_id: int) -> bool:
    return any(path.is_file() for path in _paths_for(guest_id))


def is_pdf_attachment(guest_id: int) -> bool:
    return any(
        (PHOTOS_DIR / f"{guest_id}.pdf{suffix}").is_file()
        for suffix in ("", ENC_SUFFIX)
    )


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


def _flatten(image: Image.Image) -> Image.Image:
    """An RGB copy, transparency composited on white (a scan has no alpha)."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def reencode_image(content: bytes) -> bytes:
    """Decode an uploaded image and return a clean JPEG of the same picture.

    EXIF orientation is applied to the pixels, then every piece of metadata is
    dropped: the new file is written from pixels only. Raises ValueError for
    anything Pillow cannot fully decode, and for images over MAX_IMAGE_PIXELS.
    """
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in _DECODABLE_FORMATS:
                raise ValueError("The file does not look like a valid image.")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "The photo has too many pixels. Take it again at the normal camera setting."
                )
            # Animated PNG or WebP: the first frame is the document.
            image.seek(0)
            image.load()
            upright = ImageOps.exif_transpose(image)
            clean = _flatten(upright)
            out = io.BytesIO()
            # No exif=, no icc_profile=: the JPEG carries pixels and nothing else.
            clean.save(out, format="JPEG", quality=JPEG_QUALITY)
    except ValueError:
        raise
    except Image.DecompressionBombError:
        raise ValueError(
            "The photo has too many pixels. Take it again at the normal camera setting."
        ) from None
    except Exception:
        # Truncated, corrupt or otherwise undecodable: never stored.
        raise ValueError("The file does not look like a valid image.") from None
    return out.getvalue()


def prepare_upload(content: bytes, content_type: str) -> Tuple[bytes, str]:
    """Validate an upload and return the bytes and MIME type to store.

    PDFs pass through unchanged after the magic-byte and size checks; images
    come back re-encoded as JPEG. CPU-bound for a large photo, so async routes
    should run it in a thread.
    """
    ctype = validate_upload(content, content_type)
    if ctype == ALLOWED_PDF_TYPE:
        return content, ctype
    return reencode_image(content), STORED_IMAGE_TYPE


async def read_upload_limited(upload) -> bytes:
    """Read at most the largest accepted upload plus its rejection byte."""
    return await upload.read(MAX_PDF_BYTES + 1)


def save_photo(
    guest_id: int, content: bytes, content_type: str, *, prepared: bool = False
) -> None:
    """Replace any existing attachment for this guest, encrypted at rest (BE-12).

    ``prepared=True`` means the bytes already came out of ``prepare_upload``,
    so an image is not decoded and compressed a second time.
    """
    if prepared:
        # Not validate_upload again: a re-encoded JPEG may legitimately be
        # larger than the 5 MB the original upload was held to.
        ctype = content_type
        if ctype not in (STORED_IMAGE_TYPE, ALLOWED_PDF_TYPE):
            raise ValueError("prepared uploads are JPEG or PDF")
    else:
        content, ctype = prepare_upload(content, content_type)
    _ensure_dir()
    delete_photo(guest_id)
    target = PHOTOS_DIR / f"{guest_id}{ALLOWED_TYPES[ctype]}{ENC_SUFFIX}"
    target.write_bytes(db.encrypt_blob(content))
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
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(ENC_SUFFIX):
            name = name[: -len(ENC_SUFFIX)]
        if Path(name).suffix.lower() not in ALL_EXTENSIONS:
            continue
        try:
            found.add(int(Path(name).stem))
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
        # date() rather than the raw column: a stay_to that is not a date (an
        # old row saved before the form refused them) is NULL here and falls
        # back to the booking, instead of comparing as text - where "garbage"
        # sorts after every cutoff and would keep the photo forever.
        "WHERE COALESCE(date(g.stay_to), date(r.date_to)) < ? "
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


def download_filename(guest_id: int, media_type: str) -> str:
    """A neutral file name for the download: no guest name in browser history."""
    ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        ALLOWED_PDF_TYPE: ".pdf",
    }.get(media_type, ".bin")
    return f"passport-{guest_id}{ext}"


def read_photo(guest_id: int) -> Optional[Tuple[bytes, str]]:
    """The decrypted attachment, preferring an encrypted file over a legacy one."""
    for ext in ALL_EXTENSIONS:
        encrypted = PHOTOS_DIR / f"{guest_id}{ext}{ENC_SUFFIX}"
        if encrypted.is_file():
            return db.decrypt_blob(encrypted.read_bytes()), _ctype_for(ext)
        legacy = PHOTOS_DIR / f"{guest_id}{ext}"
        if legacy.is_file():
            return legacy.read_bytes(), _ctype_for(ext)
    return None
