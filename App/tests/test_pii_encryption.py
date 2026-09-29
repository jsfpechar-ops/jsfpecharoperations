"""A guest's passport number must not sit in the clear in the database file.

A passport scan is deleted once the host has checked it, but the number typed
out of it is what the police register is actually built from, so it stays for
the six years the house book has to be produceable. It is stored encrypted, and
a value that will not decrypt has to stop the filing rather than become an
empty cDocN in a police report.
"""
from __future__ import annotations

import base64
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from starlette.testclient import TestClient

from app import claim, config, db, reporting
from app.main import app
from tests.conftest import complete_guest_claim

DOC = "ZZ9988776"
VISA = "VZ4455667"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "migrate_encrypt_doc_fields.py"
)


@pytest.fixture(scope="module")
def client():
    db.init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _no_leftovers():
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'pii-%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'PII Test'")


def _seed_stay(suffix: str = "a") -> tuple[dict, dict]:
    """An apartment and an active stay, ready for a guest to fill in."""
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "PII Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": f"pii-{suffix}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    start = date.today()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"pii-stay-{suffix}",
            "date_from": start.isoformat(),
            "date_to": (start + timedelta(days=3)).isoformat(),
            "status": "active",
            "declared_guests": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return apartment, reservation


def _save_guest(client, apartment: dict, reservation: dict, **overrides) -> dict:
    """The guest's own save path, end to end, then read the row back."""
    complete_guest_claim(
        client,
        apartment["permalink_token"],
        reservation["id"],
        party_size=1,
    )
    data = {
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": DOC,
        "visa_number": VISA,
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    response = client.post(
        f"/l/{apartment['permalink_token']}/{reservation['id']}/save",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.query_one(
        "SELECT * FROM guest WHERE reservation_id = ? ORDER BY id DESC",
        (reservation["id"],),
    )


def _raw_row(guest_id: int):
    """The stored columns, bypassing the app's decrypting query helpers."""
    conn = db.connect()
    try:
        return conn.execute(
            "SELECT doc_number, visa_number, doc_number_enc, visa_number_enc"
            " FROM guest WHERE id = ?",
            (guest_id,),
        ).fetchone()
    finally:
        conn.close()


def _raw_insert_guest(reservation_id: int, **overrides) -> int:
    """A row written the way the pre-encryption release wrote it."""
    now = db.utcnow()
    values = {
        "reservation_id": reservation_id,
        "surname": "Legacy",
        "first_name": "Lena",
        "birth_date": "01011980",
        "nationality": "GBR",
        "doc_number": DOC,
        "visa_number": VISA,
        "purpose": "10",
        "is_lead": 1,
        "entered_by": "host",
        "submit_state": reporting.PENDING,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    conn = db.connect()
    try:
        cur = conn.execute(
            f"INSERT INTO guest ({', '.join(values)})"
            f" VALUES ({', '.join('?' for _ in values)})",
            list(values.values()),
        )
        return int(cur.lastrowid)
    finally:
        conn.close()


def _load_backfill():
    spec = importlib.util.spec_from_file_location("migrate_encrypt_doc_fields", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- W2.2 -----------------------------------------------------------------

def test_a_guest_saved_by_the_form_reads_back_through_the_encrypted_column(client):
    apartment, reservation = _seed_stay()
    guest = _save_guest(client, apartment, reservation)

    assert guest["doc_number"] == DOC
    assert guest["visa_number"] == VISA

    stored = _raw_row(guest["id"])
    assert stored["doc_number"] is None, "the plaintext column must not hold the number"
    assert stored["visa_number"] is None
    assert stored["doc_number_enc"] and stored["doc_number_enc"] != DOC
    assert stored["visa_number_enc"] and stored["visa_number_enc"] != VISA


def test_the_database_file_does_not_contain_the_document_number(client):
    apartment, reservation = _seed_stay("b")
    guest = _save_guest(client, apartment, reservation)
    assert guest["doc_number"] == DOC

    conn = db.connect()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    raw = Path(config.DB_PATH).read_bytes()
    assert DOC.encode() not in raw
    assert VISA.encode() not in raw


def test_the_police_payload_still_carries_the_document_number(client):
    apartment, reservation = _seed_stay("c")
    guest = _save_guest(client, apartment, reservation)

    payload = reporting.guest_payload(guest, reservation)
    assert payload["cDocN"] == DOC
    assert payload["cVisN"] == VISA


def test_a_row_that_has_not_been_backfilled_yet_is_still_readable():
    _, reservation = _seed_stay("d")
    guest_id = _raw_insert_guest(reservation["id"])

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["doc_number"] == DOC
    assert guest["visa_number"] == VISA


def test_saving_a_guest_clears_a_stale_plaintext_copy():
    _, reservation = _seed_stay("e")
    guest_id = _raw_insert_guest(reservation["id"])

    db.update("guest", guest_id, {"doc_number": "ZZ1111111"})

    stored = _raw_row(guest_id)
    assert stored["doc_number"] is None
    assert db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))["doc_number"] == "ZZ1111111"


def test_the_backfill_encrypts_plaintext_rows_and_blanks_them():
    _, reservation = _seed_stay("f")
    backfill = _load_backfill()
    # The suite shares one database, so other tests may still have a row in the
    # clear. Measure this row's own contribution rather than the global total.
    before = backfill.migrate(dry_run=True)
    guest_id = _raw_insert_guest(reservation["id"])

    counts = backfill.migrate()

    assert counts["encrypted"] - before["encrypted"] == 2
    assert counts["blanked"] - before["blanked"] == 2
    stored = _raw_row(guest_id)
    assert stored["doc_number"] is None and stored["visa_number"] is None
    assert stored["doc_number_enc"] and stored["visa_number_enc"]
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert (guest["doc_number"], guest["visa_number"]) == (DOC, VISA)


def test_the_backfill_can_be_run_twice():
    _, reservation = _seed_stay("g")
    guest_id = _raw_insert_guest(reservation["id"])
    backfill = _load_backfill()

    backfill.migrate()
    second = backfill.migrate()

    assert second["encrypted"] == 0 and second["blanked"] == 0
    assert db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))["doc_number"] == DOC


def test_the_backfill_dry_run_writes_nothing():
    _, reservation = _seed_stay("h")
    guest_id = _raw_insert_guest(reservation["id"])
    backfill = _load_backfill()

    first = backfill.migrate(dry_run=True)
    second = backfill.migrate(dry_run=True)

    assert first == second
    stored = _raw_row(guest_id)
    assert stored["doc_number"] == DOC, "a dry run must leave the row alone"
    assert stored["doc_number_enc"] is None


def test_a_value_encrypted_with_a_different_key_raises_instead_of_reading_empty():
    _, reservation = _seed_stay("i")
    guest_id = _raw_insert_guest(reservation["id"])
    stranger = Fernet(Fernet.generate_key()).encrypt(DOC.encode()).decode("ascii")
    db.execute(
        "UPDATE guest SET doc_number = NULL, doc_number_enc = ? WHERE id = ?",
        (stranger, guest_id),
    )

    with pytest.raises(db.DecryptionError):
        db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))


def test_decrypt_field_raises_rather_than_returning_empty():
    stranger = Fernet(Fernet.generate_key()).encrypt(DOC.encode()).decode("ascii")
    with pytest.raises(db.DecryptionError):
        db.decrypt_field(stranger)


def test_decrypt_field_falls_back_to_the_plaintext_column():
    assert db.decrypt_field(None, DOC) == DOC
    assert db.decrypt_field(None, None) is None
    assert db.decrypt_field(db.encrypt_field(DOC), "stale") == DOC


def test_a_decrypted_row_still_answers_like_a_plain_database_row():
    """Decryption is invisible to callers: indexing, iteration and length match.

    Everything that reads a guest row was written against ``sqlite3.Row``, so
    the shim that carries the decrypted values has to behave the same way --
    including iterating to values rather than to column names, which is where a
    plain dict would have quietly diverged.
    """
    _, reservation = _seed_stay("j")
    guest_id = _raw_insert_guest(reservation["id"])
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert row["doc_number"] == DOC
    assert row[0] == guest_id, "integer indexing still counts columns"
    assert len(row) == len(row.keys())
    assert "doc_number" in row
    assert dict(row)["doc_number"] == DOC
    assert list(row)[0] == guest_id, "iteration yields values, not names"
    assert DOC in list(row)
    assert row[:2] == (guest_id, reservation["id"])

    plain = db.query_one("SELECT id, surname FROM guest WHERE id = ?", (guest_id,))
    assert not isinstance(plain, db._HydratedRow), "untouched tables pay nothing"


def test_an_unfilled_document_number_still_reads_back_as_none():
    """A column nobody filled in reads the same as it did before encryption."""
    _, reservation = _seed_stay("k")
    guest_id = _raw_insert_guest(
        reservation["id"], doc_number=None, visa_number=None
    )
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert row["doc_number"] is None
    assert row["visa_number"] is None


def test_an_unreadable_guest_row_does_not_stop_the_sweep_or_the_dashboard():
    """AR-24: one undecryptable row skips its own stay, not the whole job/page."""
    _, reservation = _seed_stay("m")
    guest_id = _raw_insert_guest(reservation["id"])
    db.execute(
        "UPDATE guest SET doc_number = NULL, doc_number_enc = ? WHERE id = ?",
        ("gAAAA-not-valid", guest_id),
    )

    # Both paths compute progress for the corrupted stay's reservation; neither
    # may let the decryption error escape to the caller.
    claim.sweep_reminders()
    reporting.dashboard_rows()
