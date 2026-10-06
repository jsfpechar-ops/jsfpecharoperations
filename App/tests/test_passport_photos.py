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


# --- W2.3: archiving must not leave the passport scan behind --------------
#
# Archiving keeps the guest row and only hides it, so the scan was outliving
# the check it existed for. Deleting a guest already removed the file; this is
# the same promise on the other path out of the house book.

ARCHIVE_GUEST_SUFFIX = "archive-photo"
ARCHIVE_PASSWORD = "Correct-Horse-Battery-123"


def _archive_guest_id():
    from app import db

    row = db.query_one(
        "SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id"
        " JOIN apartment a ON a.id = r.apartment_id"
        " WHERE a.permalink_token = ? ORDER BY g.id DESC",
        (f"photo-{ARCHIVE_GUEST_SUFFIX}",),
    )
    return row["id"] if row else None


@pytest.fixture(scope="module")
def host(mock_ubyport):
    """A logged-in administrator, plus a stay owned by them."""
    from fastapi.testclient import TestClient

    from app import auth, db
    from app.main import app

    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = 'photo-admin'")
    if account:
        account_id = account["id"]
    else:
        account_id = auth.create_account("photo-admin@example.test", "Photo admin", role="admin", username="photo-admin")

    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": account_id,
            "internal_name": "Photo flat",
            "city_en": "Prague",
            "permalink_token": f"photo-{ARCHIVE_GUEST_SUFFIX}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"photo-{ARCHIVE_GUEST_SUFFIX}",
            "date_from": "2030-01-01",
            "date_to": "2030-01-04",
            "status": "active",
            "declared_guests": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Archived",
            "first_name": "Anna",
            "nationality": "GBR",
            "doc_number": "AA1112223",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "submit_state": "pending",
            "created_at": now,
            "updated_at": now,
        },
    )

    with TestClient(app) as test_client:
        response = login_as(test_client, "photo-admin", follow_redirects=False)
        assert response.status_code == 303
        yield test_client, guest_id

    passport_photos.delete_photo(guest_id)
    db.execute("DELETE FROM guest WHERE id = ?", (guest_id,))
    db.execute("DELETE FROM reservation WHERE id = ?", (reservation_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    # The archive action writes audit and alert rows that name the account.
    for table in ("apartment", "legal_entity", "alert", "audit"):
        db.execute(
            f"UPDATE {table} SET owner_user_id = NULL WHERE owner_user_id = ?",
            (account_id,),
        )
    db.execute("DELETE FROM user_account WHERE id = ?", (account_id,))


def test_archiving_a_guest_deletes_the_passport_scan(host):
    client, guest_id = host
    passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
    assert passport_photos.has_photo(guest_id), "the scan should be on disk first"

    response = client.post(
        f"/guests/{guest_id}/archive",
        data={"return_to": "/housebook"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert not passport_photos.has_photo(guest_id), (
        "archiving hides the record but the scan it was checked against must go"
    )


# --- WP08: images are re-encoded, attachments always download ---------------

import io  # noqa: E402

from PIL import Image  # noqa: E402
from tests.conftest import login_as

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _jpeg(size=(40, 20), color=(10, 120, 200), exif=None) -> bytes:
    out = io.BytesIO()
    image = Image.new("RGB", size, color)
    kwargs = {"format": "JPEG", "quality": 95}
    if exif is not None:
        kwargs["exif"] = exif.tobytes()
    image.save(out, **kwargs)
    return out.getvalue()


def _exif_with_gps_and_orientation(orientation=None) -> "Image.Exif":
    exif = Image.Exif()
    exif[0x010F] = "PlaceholderCam"  # Make
    exif[0x0131] = "placeholder-firmware"  # Software
    if orientation is not None:
        exif[ORIENTATION] = orientation
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (50.0, 5.0, 0.0)
    gps[3] = "E"
    gps[4] = (14.0, 25.0, 0.0)
    return exif


def test_reencode_strips_exif_and_gps():
    original = _jpeg(exif=_exif_with_gps_and_orientation())
    with Image.open(io.BytesIO(original)) as probe:
        assert probe.getexif().get_ifd(GPS_IFD), "fixture must carry GPS to prove anything"

    clean, ctype = passport_photos.prepare_upload(original, "image/jpeg")

    assert ctype == "image/jpeg"
    with Image.open(io.BytesIO(clean)) as image:
        assert image.format == "JPEG"
        assert not image.getexif(), "no EXIF tag may survive"
        assert "exif" not in image.info
        assert "icc_profile" not in image.info
    assert b"PlaceholderCam" not in clean
    assert b"Exif\x00\x00" not in clean


def test_reencode_applies_exif_orientation():
    # Orientation 6: the camera was turned, the viewer must rotate 90 degrees.
    original = _jpeg(size=(40, 20), exif=_exif_with_gps_and_orientation(orientation=6))

    clean, _ = passport_photos.prepare_upload(original, "image/jpeg")

    with Image.open(io.BytesIO(clean)) as image:
        assert image.size == (20, 40), "the pixels are turned, not just the tag dropped"
        assert ORIENTATION not in image.getexif()


def test_reencode_keeps_resolution():
    clean, _ = passport_photos.prepare_upload(_jpeg(size=(1200, 800)), "image/jpeg")
    with Image.open(io.BytesIO(clean)) as image:
        assert image.size == (1200, 800)


def test_trailing_payload_after_image_is_dropped():
    payload = b"<script>alert(1)</script>" * 4
    clean, _ = passport_photos.prepare_upload(_jpeg() + payload, "image/jpeg")
    assert payload not in clean


def test_truncated_image_is_rejected():
    whole = _jpeg(size=(400, 300))
    truncated = whole[: len(whole) // 2]
    with pytest.raises(ValueError, match="valid image"):
        passport_photos.prepare_upload(truncated, "image/jpeg")


def test_image_with_right_magic_but_garbage_body_is_rejected():
    fake = b"\x89PNG\r\n\x1a\n" + b"\x00garbage" * 20
    with pytest.raises(ValueError, match="valid image"):
        passport_photos.prepare_upload(fake, "image/png")


def test_pixel_bomb_is_rejected_before_decoding():
    # 10000 x 5000 one-bit pixels compress to a few kilobytes of PNG but would
    # decode to 50 MP, above the per-upload bound.
    out = io.BytesIO()
    Image.new("1", (10_000, 5_000), 0).save(out, format="PNG", optimize=True)
    bomb = out.getvalue()
    assert len(bomb) < passport_photos.MAX_IMAGE_BYTES
    with pytest.raises(ValueError, match="too many pixels"):
        passport_photos.prepare_upload(bomb, "image/png")


def test_pixel_bomb_message_has_czech_translation():
    from app.routes.guest import CS_PASSPORT_UPLOAD_MESSAGES

    try:
        passport_photos.reencode_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 60)
    except ValueError as exc:
        assert str(exc) in CS_PASSPORT_UPLOAD_MESSAGES
    bomb_message = (
        "The photo has too many pixels. Take it again at the normal camera setting."
    )
    assert CS_PASSPORT_UPLOAD_MESSAGES[bomb_message].startswith("Fotografie má")


def test_transparent_png_is_stored_as_jpeg():
    out = io.BytesIO()
    Image.new("RGBA", (30, 30), (255, 0, 0, 0)).save(out, format="PNG")
    guest_id = 999001
    passport_photos.save_photo(guest_id, out.getvalue(), "image/png")

    stored = list(passport_photos.PHOTOS_DIR.glob(f"{guest_id}.*"))
    assert [p.name for p in stored] == [f"{guest_id}.jpg.enc"]
    content, media_type = passport_photos.read_photo(guest_id)
    assert media_type == "image/jpeg"
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.getpixel((5, 5))[0] > 240, "transparency becomes white, not black"


def test_webp_upload_is_stored_as_jpeg():
    out = io.BytesIO()
    Image.new("RGB", (16, 16), (0, 200, 0)).save(out, format="WEBP")
    guest_id = 999001
    passport_photos.save_photo(guest_id, out.getvalue(), "image/webp")
    assert (passport_photos.PHOTOS_DIR / f"{guest_id}.jpg.enc").is_file()
    assert not (passport_photos.PHOTOS_DIR / f"{guest_id}.webp.enc").exists()


def test_pdf_is_still_accepted_unchanged():
    content, ctype = passport_photos.prepare_upload(MINIMAL_PDF, "application/pdf")
    assert ctype == "application/pdf"
    assert content == MINIMAL_PDF


def test_image_download_is_an_attachment_with_nosniff(host):
    from app import db

    client, guest_id = host
    passport_photos.save_photo(guest_id, _jpeg(exif=_exif_with_gps_and_orientation()), "image/jpeg")
    # The archive test above shares this guest and leaves it archived; only a
    # guest-entered record offers its photo to the host.
    db.update(
        "guest",
        guest_id,
        {"passport_photo_at": db.utcnow(), "archived_at": None, "entered_by": "guest"},
    )

    response = client.get(f"/guests/{guest_id}/passport-photo")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="passport-{guest_id}.jpg"'
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "sandbox" in response.headers["content-security-policy"]
    with Image.open(io.BytesIO(response.content)) as image:
        assert not image.getexif()

    # The host still sees the re-encoded photo inline on the guest page.
    page = client.get(f"/guests/{guest_id}")
    assert page.status_code == 200
    assert f'<img src="/guests/{guest_id}/passport-photo"' in page.text


def test_pdf_download_is_an_attachment_and_never_framed(host):
    from app import db

    client, guest_id = host
    passport_photos.save_photo(guest_id, MINIMAL_PDF, "application/pdf")
    # The archive test above shares this guest and leaves it archived; only a
    # guest-entered record offers its photo to the host.
    db.update(
        "guest",
        guest_id,
        {"passport_photo_at": db.utcnow(), "archived_at": None, "entered_by": "guest"},
    )

    response = client.get(f"/guests/{guest_id}/passport-photo")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="passport-{guest_id}.pdf"'
    )
    assert response.headers["x-content-type-options"] == "nosniff"

    page = client.get(f"/guests/{guest_id}")
    assert page.status_code == 200
    assert "<iframe" not in page.text
    assert f'href="/guests/{guest_id}/passport-photo" download' in page.text
    assert "Stáhnout PDF pasu" in page.text or "Download the passport PDF" in page.text
