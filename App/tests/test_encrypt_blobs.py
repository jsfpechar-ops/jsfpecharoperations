"""BE-12: signatures and passport attachments are encrypted at rest.

A stolen volume or a copied data directory should not yield a valid image, PDF or
signature. Reads decrypt; a wrong key raises rather than returning empty.
"""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest

from app import db, passport_photos, reporting

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "migrate_encrypt_signatures.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("migrate_encrypt_signatures", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _purge():
    """Leave the shared test database as it was found.

    The suite shares one database, and ``test_endtoend`` reads
    ``SELECT * FROM apartment``: a leaked property of ours would shadow its own.
    """
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE internal_name = 'Blob flat'"):
        apartment_id = row["id"]
        for reservation in db.query(
            "SELECT id FROM reservation WHERE apartment_id = ?", (apartment_id,)
        ):
            for guest in db.query(
                "SELECT id FROM guest WHERE reservation_id = ?", (reservation["id"],)
            ):
                passport_photos.delete_photo(guest["id"])
            db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM legal_entity WHERE name = 'Blob entity' AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)"
    )


@pytest.fixture(autouse=True)
def _database():
    _purge()
    yield
    _purge()

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)
SIGNATURE = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode()


def _raw(sql, params=()):
    conn = db.connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _seed_guest() -> int:
    db.init_db()
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "Blob entity", "created_at": now})
    apartment = db.insert(
        "apartment",
        {"legal_entity_id": entity, "internal_name": "Blob flat", "created_at": now},
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": f"blob-{now}",
            "date_from": "2026-01-01",
            "date_to": "2026-01-03",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return db.insert(
        "guest",
        {
            "reservation_id": reservation,
            "surname": "Blob",
            "first_name": "Test",
            "created_at": now,
            "updated_at": now,
        },
    )


def test_a_saved_attachment_is_encrypted_on_disk_and_round_trips():
    guest_id = _seed_guest()
    passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
    try:
        encrypted = passport_photos.PHOTOS_DIR / f"{guest_id}.png.enc"
        assert encrypted.is_file()
        plain = passport_photos.PHOTOS_DIR / f"{guest_id}.png"
        assert not plain.exists()
        # The bytes on disk are not a PNG any more.
        assert not encrypted.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        content, media_type = passport_photos.read_photo(guest_id)
        assert content == PNG_BYTES
        assert media_type == "image/png"
        assert passport_photos.has_photo(guest_id)
    finally:
        passport_photos.delete_photo(guest_id)


def test_a_tampered_attachment_raises_instead_of_reading_empty():
    guest_id = _seed_guest()
    passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
    target = passport_photos.PHOTOS_DIR / f"{guest_id}.png.enc"
    try:
        target.write_bytes(b"not a fernet token")
        with pytest.raises(db.DecryptionError):
            passport_photos.read_photo(guest_id)
    finally:
        passport_photos.delete_photo(guest_id)


def test_a_drawn_signature_is_written_encrypted_and_reads_back():
    guest_id = _seed_guest()
    db.update("guest", guest_id, {"signature_png": SIGNATURE})

    raw = _raw("SELECT signature_png, signature_png_enc FROM guest WHERE id = ?", (guest_id,))[0]
    assert raw["signature_png"] is None, "the plaintext column must be blanked"
    assert raw["signature_png_enc"]

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["signature_png"] == SIGNATURE
    assert reporting.guest_has_signature(guest) is True


def test_the_migration_encrypts_existing_signatures_and_files():
    migration = _migration()

    guest_id = _seed_guest()
    # Write a plaintext signature and a plaintext file, as the old release did.
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE guest SET signature_png = ? WHERE id = ?", (SIGNATURE, guest_id)
        )
    finally:
        conn.close()
    passport_photos._ensure_dir()
    plain_file = passport_photos.PHOTOS_DIR / f"{guest_id}.png"
    plain_file.write_bytes(PNG_BYTES)
    try:
        assert migration.remaining()["plaintext_signatures"] >= 1
        counts = migration.migrate_signatures()
        files = migration.migrate_passport_files()
        assert counts["encrypted"] >= 1
        assert files["encrypted"] >= 1

        raw = _raw("SELECT signature_png, signature_png_enc FROM guest WHERE id = ?", (guest_id,))[0]
        assert raw["signature_png"] is None and raw["signature_png_enc"]
        assert not plain_file.exists()
        assert (passport_photos.PHOTOS_DIR / f"{guest_id}.png.enc").is_file()
        assert passport_photos.read_photo(guest_id)[0] == PNG_BYTES
        assert migration.remaining()["plaintext_signatures"] == 0
    finally:
        passport_photos.delete_photo(guest_id)
