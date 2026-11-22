"""Retention step entry_codes (brief 1662)."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from app import db, retention

PREFIX = "ec1662-"


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    _ensure_entry_code_columns()
    yield
    _purge()


def _purge():
    db.init_db()
    owners = [
        r["id"]
        for r in db.query(
            "SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)
        )
    ]
    for owner in owners:
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


_counter = 0


def _ensure_entry_code_columns() -> None:
    """SQLite-only shim; PostgreSQL gets 00022 / runtime columns from init_db."""
    if getattr(db.config, "DB_BACKEND", "sqlite") == "postgresql":
        return
    for col, decl in (
        ("entry_code_enc", "TEXT"),
        ("entry_code_label", "TEXT"),
        ("entry_code_until", "TEXT"),
        ("guide_external_url", "TEXT"),
    ):
        try:
            db.execute(f"ALTER TABLE apartment ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass


def _owner() -> int:
    global _counter
    _counter += 1
    return db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "password_hash": "x",
            "created_at": db.utcnow(),
        },
    )


def _apartment(owner: int, **extra) -> int:
    row = {
        "internal_name": "EC flat",
        "created_at": db.utcnow(),
        "owner_user_id": owner,
        **extra,
    }
    return db.insert("apartment", row)


def test_expired_entry_code_wiped_after_one_day():
    owner = _owner()
    apt = _apartment(
        owner,
        entry_code_enc="enc-expired",
        entry_code_until=(date.today() - timedelta(days=5)).isoformat(),
    )
    today = date.today()
    assert retention._entry_code_step(today, dry_run=True, owner_user_id=None) == 1
    assert db.query_one("SELECT entry_code_enc FROM apartment WHERE id = ?", (apt,))["entry_code_enc"] == "enc-expired"
    assert retention._entry_code_step(today, dry_run=False, owner_user_id=None) == 1
    assert db.query_one("SELECT entry_code_enc FROM apartment WHERE id = ?", (apt,))["entry_code_enc"] is None


def test_open_ended_entry_code_kept():
    owner = _owner()
    apt = _apartment(owner, entry_code_enc="enc-open", entry_code_until=None)
    today = date.today()
    assert retention._entry_code_step(today, dry_run=False, owner_user_id=None) == 0
    assert db.query_one("SELECT entry_code_enc FROM apartment WHERE id = ?", (apt,))["entry_code_enc"] == "enc-open"


def test_archived_entry_code_wiped():
    owner = _owner()
    archived_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    apt = _apartment(owner, entry_code_enc="enc-archived", archived_at=archived_at)
    today = date.today()
    assert retention._entry_code_step(today, dry_run=False, owner_user_id=None) == 1
    assert db.query_one("SELECT entry_code_enc FROM apartment WHERE id = ?", (apt,))["entry_code_enc"] is None


def test_owner_scoped_run_skips_entry_codes():
    owner = _owner()
    _apartment(
        owner,
        entry_code_enc="enc-expired",
        entry_code_until=(date.today() - timedelta(days=5)).isoformat(),
    )
    assert retention._entry_code_step(date.today(), dry_run=False, owner_user_id=owner) == 0

def _ensure_entry_code_table() -> None:
    if getattr(db.config, "DB_BACKEND", "sqlite") == "postgresql":
        return
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS apartment_entry_code (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 3),
            code_type TEXT NOT NULL,
            custom_label TEXT,
            code_enc TEXT NOT NULL,
            valid_until TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (apartment_id, position)
        )
        """
    )


def _insert_table_code(apt: int, position: int, enc: str, until: str | None) -> None:
    db.execute(
        "INSERT INTO apartment_entry_code "
        "(apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at) "
        "VALUES (?, ?, 'gate', NULL, ?, ?, ?, ?)",
        (apt, position, enc, until, db.utcnow(), db.utcnow()),
    )


def test_table_expired_row_deleted():
    _ensure_entry_code_table()
    owner = _owner()
    apt = _apartment(owner)
    _insert_table_code(apt, 1, "enc-table-expired", (date.today() - timedelta(days=5)).isoformat())
    _insert_table_code(apt, 2, "enc-table-open", None)
    today = date.today()
    assert retention._entry_code_step(today, dry_run=True, owner_user_id=None) == 1
    assert db.query_one("SELECT code_enc FROM apartment_entry_code WHERE apartment_id = ? AND position = 1", (apt,))["code_enc"] == "enc-table-expired"
    assert retention._entry_code_step(today, dry_run=False, owner_user_id=None) == 1
    assert db.query_one("SELECT code_enc FROM apartment_entry_code WHERE apartment_id = ? AND position = 2", (apt,))["code_enc"] == "enc-table-open"


def test_table_archived_apartment_row_deleted():
    _ensure_entry_code_table()
    owner = _owner()
    archived_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    apt = _apartment(owner, archived_at=archived_at)
    _insert_table_code(apt, 1, "enc-table-archived", None)
    assert retention._entry_code_step(date.today(), dry_run=False, owner_user_id=None) == 1
    assert db.query("SELECT 1 FROM apartment_entry_code WHERE apartment_id = ?", (apt,)) == []


def test_table_future_and_open_kept():
    _ensure_entry_code_table()
    owner = _owner()
    apt = _apartment(owner)
    _insert_table_code(apt, 1, "enc-future", (date.today() + timedelta(days=30)).isoformat())
    _insert_table_code(apt, 2, "enc-open", None)
    assert retention._entry_code_step(date.today(), dry_run=False, owner_user_id=None) == 0
    rows = db.query("SELECT position, code_enc FROM apartment_entry_code WHERE apartment_id = ? ORDER BY position", (apt,))
    assert [r["code_enc"] for r in rows] == ["enc-future", "enc-open"]
