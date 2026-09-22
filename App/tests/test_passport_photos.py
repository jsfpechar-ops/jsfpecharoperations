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
        account_id = auth.create_account(
            "photo-admin",
            ARCHIVE_PASSWORD,
            "Photo admin",
            role="admin",
            must_change_password=False,
        )

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
        response = test_client.post(
            "/login",
            data={"username": "photo-admin", "password": ARCHIVE_PASSWORD},
            follow_redirects=False,
        )
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
