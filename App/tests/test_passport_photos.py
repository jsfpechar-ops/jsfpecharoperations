"""Passport photo and PDF upload validation."""
import asyncio
import base64

import pytest

from app import passport_photos

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])

MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n"
    b"149\n"
    b"%%EOF\n"
)


@pytest.fixture(autouse=True)
def _cleanup_photos():
    guest_id = 999001
    passport_photos.delete_photo(guest_id)
    yield
    passport_photos.delete_photo(guest_id)


def test_validate_upload_accepts_png():
    assert passport_photos.validate_upload(PNG_BYTES, "image/png") == "image/png"


def test_validate_upload_accepts_pdf():
    assert passport_photos.validate_upload(MINIMAL_PDF, "application/pdf") == "application/pdf"


def test_validate_upload_rejects_bad_type():
    with pytest.raises(ValueError, match="JPEG"):
        passport_photos.validate_upload(b"not-a-real-file" * 8, "text/plain")


def test_validate_upload_rejects_oversize_image():
    huge = PNG_BYTES + b"x" * passport_photos.MAX_IMAGE_BYTES
    with pytest.raises(ValueError, match="too large"):
        passport_photos.validate_upload(huge, "image/png")


def test_validate_upload_rejects_oversize_pdf():
    huge = MINIMAL_PDF + b"x" * passport_photos.MAX_PDF_BYTES
    with pytest.raises(ValueError, match="too large"):
        passport_photos.validate_upload(huge, "application/pdf")


def test_validate_upload_rejects_fake_pdf():
    with pytest.raises(ValueError, match="valid PDF"):
        passport_photos.validate_upload(b"not-a-pdf" + b"x" * 56, "application/pdf")


def test_route_upload_reader_caps_memory_before_validation():
    class Upload:
        requested = None

        async def read(self, size):
            self.requested = size
            return b"x" * size

    upload = Upload()
    content = asyncio.run(passport_photos.read_upload_limited(upload))

    assert upload.requested == passport_photos.MAX_PDF_BYTES + 1
    assert len(content) == passport_photos.MAX_PDF_BYTES + 1


def test_save_photo_pdf_roundtrip():
    guest_id = 999001
    passport_photos.save_photo(guest_id, MINIMAL_PDF, "application/pdf")
    assert passport_photos.has_photo(guest_id)
    assert passport_photos.is_pdf_attachment(guest_id)
    payload = passport_photos.read_photo(guest_id)
    assert payload is not None
    content, media_type = payload
    assert media_type == "application/pdf"
    assert content.startswith(b"%PDF-")
