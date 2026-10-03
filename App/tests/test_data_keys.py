"""WP16: a data-encryption key of its own, and more fields encrypted at rest.

The Fernet key used to be the SHA-256 of the session secret, so rotating the
session secret made every encrypted field unreadable. UBYHOST_DATA_KEYS now
holds the data keys (first one encrypts, all of them decrypt) and the old
derived key stays as the last decryption key until scripts/reencrypt.py has
moved everything across.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app import config, db, mail, passport_photos, stay_fee

TOOL_PATH = Path(__file__).resolve().parent.parent / "scripts" / "reencrypt.py"
NEW_KEY = Fernet.generate_key().decode("ascii")
NEWER_KEY = Fernet.generate_key().decode("ascii")
BIRTH = "24121990"
STREET = "Ukázková 12"
CITY = "Demoville"
DOC = "ZZ1234567"
REQUEST = "<request><cDocN>ZZ1234567</cDocN><cDate>24121990</cDate></request>"


def _tool():
    spec = importlib.util.spec_from_file_location("reencrypt_tool", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    # dataclasses look their module up in sys.modules while the class is built.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _legacy() -> Fernet:
    digest = hashlib.sha256(config.secret_key().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@pytest.fixture
def keys(monkeypatch):
    """Start from the pre-WP16 state: no data keys, legacy key on."""
    monkeypatch.delenv("UBYHOST_DATA_KEYS", raising=False)
    monkeypatch.delenv("UBYHOST_DATA_KEY_LEGACY", raising=False)
    return monkeypatch


@pytest.fixture
def scratch_db(tmp_path, monkeypatch, keys):
    """A database of its own, so re-encrypting it cannot touch other tests' rows."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "scratch.db")
    monkeypatch.setattr(passport_photos, "PHOTOS_DIR", tmp_path / "passport_photos")
    db.init_db()
    return tmp_path


def _seed(owner_name: str = "wp16-owner") -> dict:
    now = db.utcnow()
    owner = db.insert("user_account", {
        "username": owner_name, "password_hash": "x", "created_at": now,
        "totp_secret_enc": db.encrypt_secret("TOTPSECRETDEMO"),
    })
    apartment = db.insert("apartment", {
        "internal_name": "Demo flat", "owner_user_id": owner, "created_at": now,
        "uby_ws_password_enc": db.encrypt_secret("demo-password"),
    })
    reservation = db.insert("reservation", {
        "apartment_id": apartment, "uid": f"wp16-{owner_name}", "date_from": "2026-08-10",
        "date_to": "2026-08-14", "created_at": now, "updated_at": now,
    })
    guest = db.insert("guest", {
        "reservation_id": reservation, "surname": "NOVAK", "first_name": "JOSEF",
        "birth_date": BIRTH, "doc_number": DOC, "res_street": STREET, "res_city": CITY,
        "res_country": "DEU", "created_at": now, "updated_at": now,
    })
    submission = db.insert("submission", {
        "apartment_id": apartment, "created_at": now, "state": "ok",
        "request_xml": REQUEST, "response_xml": "<response/>",
    })
    outbox = db.insert("email_outbox", {
        "idempotency_key": f"wp16-{owner_name}", "kind": "claim", "state": "queued",
        "payload": json.dumps({"text": "x", mail.CLAIM_SECRET_KEY: db.encrypt_field("claim-s")}),
        "created_at": now, "updated_at": now,
    })
    return {"owner": owner, "apartment": apartment, "reservation": reservation,
            "guest": guest, "submission": submission, "outbox": outbox}


def _raw(sql: str, params=()):
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _read_back(ids: dict) -> dict:
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (ids["guest"],))
    submission = db.query_one("SELECT * FROM submission WHERE id = ?", (ids["submission"],))
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (ids["owner"],))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (ids["apartment"],))
    outbox = db.query_one("SELECT payload FROM email_outbox WHERE id = ?", (ids["outbox"],))
    return {
        "birth_date": guest["birth_date"], "res_street": guest["res_street"],
        "res_city": guest["res_city"], "res_country": guest["res_country"],
        "doc_number": guest["doc_number"], "request_xml": submission["request_xml"],
        "totp": db.decrypt_secret(account["totp_secret_enc"]),
        "password": db.decrypt_secret(apartment["uby_ws_password_enc"]),
        "claim": db.decrypt_field(json.loads(outbox["payload"])[mail.CLAIM_SECRET_KEY]),
    }


EXPECTED = {
    "birth_date": BIRTH, "res_street": STREET, "res_city": CITY, "res_country": "DEU",
    "doc_number": DOC, "request_xml": REQUEST, "totp": "TOTPSECRETDEMO",
    "password": "demo-password", "claim": "claim-s",
}


# --- keys --------------------------------------------------------------------

def test_without_data_keys_the_legacy_derived_key_is_used(keys):
    token = db.encrypt_field("hello")
    assert _legacy().decrypt(token.encode()).decode() == "hello"


def test_old_data_stays_readable_after_a_new_key_is_added(keys):
    old = db.encrypt_field("hello")
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    assert db.decrypt_field(old) == "hello"
    fresh = db.encrypt_field("hello")
    assert Fernet(NEW_KEY.encode()).decrypt(fresh.encode()).decode() == "hello"
    assert db.token_is_current(fresh) and not db.token_is_current(old)


def test_a_second_key_reads_the_first_keys_data(keys):
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    first = db.encrypt_field("hello")
    keys.setenv("UBYHOST_DATA_KEYS", f"{NEWER_KEY},{NEW_KEY}")
    assert db.decrypt_field(first) == "hello"
    assert Fernet(NEWER_KEY.encode()).decrypt(db.encrypt_field("x").encode()) == b"x"


def test_rotating_the_session_secret_no_longer_affects_encrypted_data(keys):
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    token = db.encrypt_field(DOC)
    blob = db.encrypt_blob(b"%PDF-1.4 demo")
    secret = db.encrypt_secret("demo-password")
    keys.setattr(config, "_SECRET_KEY", "a-completely-different-session-secret-0123456789")
    assert db.decrypt_field(token) == DOC
    assert db.decrypt_blob(blob) == b"%PDF-1.4 demo"
    assert db.decrypt_secret(secret) == "demo-password"
    keys.setenv("UBYHOST_DATA_KEY_LEGACY", "0")
    assert db.decrypt_field(token) == DOC


def test_with_the_legacy_key_switched_off_legacy_tokens_no_longer_read(keys):
    old = db.encrypt_field(DOC)
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    keys.setenv("UBYHOST_DATA_KEY_LEGACY", "0")
    with pytest.raises(db.DecryptionError):
        db.decrypt_field(old)


def test_a_malformed_data_key_stops_startup_without_echoing_it(keys):
    keys.setenv("UBYHOST_DATA_KEYS", "not-a-fernet-key-SECRETVALUE")
    with pytest.raises(db.DataKeyError) as caught:
        db.check_data_keys()
    assert "SECRETVALUE" not in str(caught.value)
    assert "entry 1" in str(caught.value)


def test_legacy_off_without_any_data_key_is_refused(keys):
    keys.setenv("UBYHOST_DATA_KEY_LEGACY", "0")
    with pytest.raises(db.DataKeyError):
        db.check_data_keys()


# --- newly encrypted fields --------------------------------------------------

def test_birth_date_address_and_request_xml_are_stored_encrypted(scratch_db):
    ids = _seed()
    raw_guest = _raw("SELECT * FROM guest WHERE id = ?", (ids["guest"],))
    for name in ("birth_date", "res_street", "res_city"):
        assert raw_guest[name] is None, f"{name} is still stored in the clear"
        assert db.decrypt_field(raw_guest[f"{name}_enc"]) == EXPECTED[name]
    assert raw_guest["res_country"] == "DEU", "the country code stays plain, like nationality"
    raw_sub = _raw("SELECT * FROM submission WHERE id = ?", (ids["submission"],))
    assert raw_sub["request_xml"] is None
    assert db.decrypt_field(raw_sub["request_xml_enc"]) == REQUEST
    assert raw_sub["response_xml"] == "<response/>"
    assert _read_back(ids) == EXPECTED
    data = Path(config.DB_PATH).read_bytes()
    for plain in (BIRTH, STREET, "ZZ1234567"):
        assert plain.encode() not in data


def test_a_row_saved_before_wp16_still_reads_from_its_plaintext_column(scratch_db):
    ids = _seed()
    db.execute(
        "UPDATE guest SET birth_date = ?, birth_date_enc = NULL WHERE id = ?", (BIRTH, ids["guest"])
    )
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (ids["guest"],))
    assert guest["birth_date"] == BIRTH


def test_stay_fee_age_rule_is_unchanged_with_an_encrypted_birth_date(scratch_db):
    """A child exempt by age stays exempt when the birth date comes from *_enc."""
    ids = _seed()
    now = db.utcnow()
    db.update("apartment", ids["apartment"], {
        "stay_fee_rate_czk": 50, "stay_fee_cadence": "monthly", "stay_fee_vs": "1234567890",
    })
    child = db.insert("guest", {
        "reservation_id": ids["reservation"], "surname": "NOVAK", "first_name": "ANNA",
        "birth_date": "01012015", "nationality": "DEU", "created_at": now, "updated_at": now,
    })
    assert _raw("SELECT birth_date FROM guest WHERE id = ?", (child,))["birth_date"] is None
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (ids["reservation"],))
    first, last = date(2026, 8, 1), date(2026, 8, 31)
    stored = db.query_one("SELECT * FROM guest WHERE id = ?", (child,))
    plain = dict(stored)
    plain["birth_date"] = "01012015"
    assert stay_fee.guest_period(stored, reservation, first, last) == stay_fee.guest_period(
        plain, reservation, first, last
    )
    share = stay_fee.guest_period(stored, reservation, first, last)
    assert share["exempt_nights"] == 4 and share["liable_nights"] == 0
    adult = db.query_one("SELECT * FROM guest WHERE id = ?", (ids["guest"],))
    assert stay_fee.guest_period(adult, reservation, first, last)["liable_nights"] == 4


def test_the_payload_purge_clears_the_encrypted_envelope(scratch_db):
    from app import reporting

    ids = _seed()
    db.execute(
        "UPDATE submission SET created_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
        (ids["submission"],),
    )
    assert reporting.purge_submission_payloads() == 1
    raw_sub = _raw("SELECT * FROM submission WHERE id = ?", (ids["submission"],))
    assert raw_sub["request_xml_enc"] is None and raw_sub["request_xml"] is None


# --- scripts/reencrypt.py ------------------------------------------------------

def _backup(tmp_path: Path, age_hours: float = 0) -> Path:
    path = tmp_path / "backup.db"
    path.write_bytes(b"SQLite format 3\x00demo")
    stamp = time.time() - age_hours * 3600
    os.utime(path, (stamp, stamp))
    return path


def _photo(guest_id: int, token: bytes) -> Path:
    passport_photos.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    path = passport_photos.PHOTOS_DIR / f"{guest_id}.jpg{passport_photos.ENC_SUFFIX}"
    path.write_bytes(token)
    return path


def test_reencrypt_moves_everything_to_the_new_key_and_values_stay_equal(scratch_db, keys):
    tool = _tool()
    ids = _seed()
    photo = _photo(ids["guest"], db.encrypt_blob(b"\xff\xd8\xff demo image"))
    # A row saved before WP16: plaintext only.
    other = db.insert("guest", {
        "reservation_id": ids["reservation"], "surname": "B", "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    })
    db.execute("UPDATE guest SET birth_date = ?, res_city = ? WHERE id = ?", (BIRTH, CITY, other))

    filing = db.insert("stay_fee_filing", {
        "apartment_id": ids["apartment"], "period_key": "2026-08", "cadence": "monthly",
        "rate_czk": 50, "liable_days": 4, "exempt_days": 0, "total_due_czk": 200,
        "total_collected_czk": 200, "pdf_enc": db.encrypt_blob(b"%PDF-1.4 filing"),
        "csv_enc": db.encrypt_blob(b"a;b"), "payload_enc": db.encrypt_field("{}"),
        "created_at": db.utcnow(),
    })

    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    backup = _backup(scratch_db)
    assert tool.main(["--backup", str(backup), "--batch-size", "1"]) == 0

    keys.setenv("UBYHOST_DATA_KEY_LEGACY", "0")
    assert _read_back(ids) == EXPECTED
    assert db.decrypt_blob(photo.read_bytes()) == b"\xff\xd8\xff demo image"
    sealed = _raw("SELECT pdf_enc, csv_enc, payload_enc FROM stay_fee_filing WHERE id = ?", (filing,))
    assert isinstance(sealed["pdf_enc"], bytes), "a BLOB stays a BLOB"
    assert db.decrypt_blob(sealed["pdf_enc"]) == b"%PDF-1.4 filing"
    assert db.decrypt_blob(sealed["csv_enc"]) == b"a;b"
    assert db.decrypt_field(sealed["payload_enc"]) == "{}"
    migrated = db.query_one("SELECT * FROM guest WHERE id = ?", (other,))
    assert (migrated["birth_date"], migrated["res_city"]) == (BIRTH, CITY)
    assert _raw("SELECT birth_date FROM guest WHERE id = ?", (other,))["birth_date"] is None
    assert tool.main(["--check"]) == 0


def test_reencrypt_is_resumable_and_a_second_run_changes_nothing(scratch_db, keys):
    tool = _tool()
    ids = _seed()
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    first = tool.run(dry_run=False, batch_size=2)
    assert first.targets["guest.doc_number_enc"].rotated == 1
    before = _raw("SELECT doc_number_enc FROM guest WHERE id = ?", (ids["guest"],))[0]
    second = tool.run(dry_run=False, batch_size=2)
    assert second.pending == 0
    assert second.targets["guest.doc_number_enc"].current == 1
    after = _raw("SELECT doc_number_enc FROM guest WHERE id = ?", (ids["guest"],))[0]
    assert before == after, "a value already under the current key is not rewritten"


def test_reencrypt_dry_run_counts_and_writes_nothing(scratch_db, keys):
    tool = _tool()
    ids = _seed()
    before = _raw("SELECT doc_number_enc, birth_date_enc FROM guest WHERE id = ?", (ids["guest"],))
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    assert tool.main(["--check"]) == 1
    report = tool.run(dry_run=True)
    assert report.targets["guest.doc_number_enc"].rotated == 1
    assert report.targets["apartment.uby_ws_password_enc"].rotated == 1
    assert report.targets["submission.request_xml_enc"].rotated == 1
    after = _raw("SELECT doc_number_enc, birth_date_enc FROM guest WHERE id = ?", (ids["guest"],))
    assert tuple(before) == tuple(after)


def test_reencrypt_refuses_to_write_without_a_fresh_backup(scratch_db, keys):
    tool = _tool()
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    with pytest.raises(SystemExit, match="--backup"):
        tool.main([])
    with pytest.raises(SystemExit, match="does not exist"):
        tool.main(["--backup", str(scratch_db / "missing.db")])
    with pytest.raises(SystemExit, match="hours old"):
        tool.main(["--backup", str(_backup(scratch_db, age_hours=30))])
    with pytest.raises(SystemExit, match="live database"):
        tool.main(["--backup", str(config.DB_PATH)])


def test_reencrypt_refuses_to_write_without_a_new_key(scratch_db, keys):
    tool = _tool()
    with pytest.raises(SystemExit, match="UBYHOST_DATA_KEYS is not set"):
        tool.main(["--backup", str(_backup(scratch_db))])


def test_reencrypt_leaves_an_unreadable_value_alone_and_fails(scratch_db, keys):
    tool = _tool()
    ids = _seed()
    stranger = Fernet(Fernet.generate_key()).encrypt(b"x").decode()
    db.execute("UPDATE guest SET visa_number_enc = ? WHERE id = ?", (stranger, ids["guest"]))
    keys.setenv("UBYHOST_DATA_KEYS", NEW_KEY)
    assert tool.main(["--backup", str(_backup(scratch_db))]) == 2
    assert _raw("SELECT visa_number_enc FROM guest WHERE id = ?", (ids["guest"],))[0] == stranger


def test_rollback_new_fields_puts_them_back_in_plaintext(scratch_db, keys):
    tool = _tool()
    ids = _seed()
    report = tool.rollback_new_fields(dry_run=False)
    assert report.targets["guest.birth_date"].restored == 1
    raw_guest = _raw("SELECT * FROM guest WHERE id = ?", (ids["guest"],))
    assert (raw_guest["birth_date"], raw_guest["res_street"], raw_guest["res_city"]) == (
        BIRTH, STREET, CITY,
    )
    assert raw_guest["birth_date_enc"] is None
    assert raw_guest["doc_number_enc"], "fields encrypted before WP16 are left alone"
    raw_sub = _raw("SELECT * FROM submission WHERE id = ?", (ids["submission"],))
    assert raw_sub["request_xml"] == REQUEST and raw_sub["request_xml_enc"] is None
