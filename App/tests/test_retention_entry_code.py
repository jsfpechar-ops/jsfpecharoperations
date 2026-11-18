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