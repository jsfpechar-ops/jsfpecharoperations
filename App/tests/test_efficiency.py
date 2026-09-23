"""W5.3: the efficiency work, and the behaviour it was not allowed to change.

Every item here is a behaviour-preserving change, so the tests come in two
shapes: one that measures the work the old code did (a query, a pragma, a
second validation pass) and one that pins the behaviour that work produced, so
making it cheaper cannot quietly make it different.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import config, db, demo, reporting

PROJECT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _leave_the_shared_database_as_it_was():
    """Remove the rows these tests seed into the session-wide database.

    ``test_endtoend.py`` attaches its apartment to whichever legal entity comes
    back first, so a leftover row here fails its ownership check and takes the
    whole end-to-end path down with it.
    """
    yield
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'tok-eff-%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name LIKE 'Eff %'")


class _CountingConnection:
    """A connection that records the statements a migration pass runs."""

    def __init__(self, conn):
        self._conn = conn
        self.statements = []

    def execute(self, sql, *args):
        self.statements.append(sql)
        return self._conn.execute(sql, *args)


# --- item 1: the schema check is no longer on the query path --------------


def test_connect_no_longer_migrates_the_schema(monkeypatch, tmp_path):
    """Opening a connection must not rewrite the schema any more."""
    # The shared database is left initialised for the module cleanup below.
    db.init_db()
    database = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE apartment (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "internal_name TEXT NOT NULL, permalink_token TEXT, "
        "automation_mode TEXT NOT NULL DEFAULT 'scheduled', created_at TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "DB_PATH", database)
    opened = db.connect()
    try:
        columns = {row["name"] for row in opened.execute("PRAGMA table_info(apartment)")}
    finally:
        opened.close()
    assert "owner_user_id" not in columns, "connect() is still migrating on every connection"

    db.init_db()
    migrated = {row["name"] for row in db.query("PRAGMA table_info(apartment)")}
    assert "owner_user_id" in migrated, "init_db() stopped migrating a legacy database"

    # Put the real database back before the module cleanup runs: it must not be
    # asked to delete rows from this throwaway file.
    monkeypatch.undo()


def test_the_schema_check_pragmas_each_table_once():
    db.init_db()
    conn = db.connect()
    try:
        counting = _CountingConnection(conn)
        db._add_missing_columns(counting)
    finally:
        conn.close()

    pragmas = [sql for sql in counting.statements if sql.startswith("PRAGMA table_info")]
    tables = {table for table, _column, _decl in db.ADDED_COLUMNS}
    assert len(pragmas) == len(tables)
    assert len(db.ADDED_COLUMNS) > len(tables), "fixture is pointless without repeats"
    assert not [sql for sql in counting.statements if sql.startswith("ALTER TABLE")]


# --- item 3: the indexes --------------------------------------------------


def test_the_queue_indexes_exist_and_the_dead_one_is_gone():
    db.init_db()
    names = {
        row["name"]
        for row in db.query("SELECT name FROM sqlite_master WHERE type = 'index'")
    }
    assert {"idx_submission_apartment", "idx_audit_owner", "idx_outbox_state_attempt"} <= names
    assert "idx_guest_state" not in names


# --- item 4: the stay is fetched once, not once per guest -----------------


def _seed_stay_with_guests(count: int, token: str):
    db.init_db()
    now, today = db.utcnow(), date.today()
    entity_id = db.insert(
        "legal_entity", {"name": f"Eff {token}", "seat": "Praha", "created_at": now}
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Efficiency Flat",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": "manual",
            "submit_after_hours": 24,
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
            "uid": f"eff-{token}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": count,
            "created_at": now,
            "updated_at": now,
        },
    )
    for index in range(count):
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": f"Guest{index}",
                "first_name": "Anna",
                "birth_date": "01011990",
                "nationality": "DEU",
                "doc_number": f"P{index}123456",
                "res_street": "Street 1",
                "res_city": "Berlin",
                "res_country": "DEU",
                "purpose": "10",
                "is_lead": 1 if index == 0 else 0,
                "entered_by": "host",
                "signature_png": "imported",
                "submit_state": reporting.PENDING,
                "created_at": now,
                "updated_at": now,
            },
        )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return apartment, reservation


def test_collect_sendable_does_not_look_the_stay_up_again_per_guest(monkeypatch):
    apartment, reservation = _seed_stay_with_guests(3, "tok-eff-collect")
    seen = []
    original = db.query_one

    def spy(sql, params=()):
        seen.append(sql)
        return original(sql, params)

    monkeypatch.setattr(db, "query_one", spy)
    # ignore_automation is what the host's bulk send passes; without it the
    # manual apartment is correctly not due for the unattended sweep.
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)

    assert len(pairs) == 3
    assert not [
        sql for sql in seen if "FROM reservation WHERE id" in sql
    ], "the stay is still fetched once per guest"


def test_collect_sendable_hands_back_the_stay_not_the_guest():
    """``g.*, r.*`` would make reservation["id"] the guest's id.

    Both tables have id, created_at and archived_at, and a duplicated column
    name resolves to the first one, so a caller reading the stay's id would be
    handed the guest's. This is the trap the single-query rewrite had to avoid.
    """
    apartment, reservation = _seed_stay_with_guests(2, "tok-eff-ids")
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)

    assert len(pairs) == 2
    for guest, stay in pairs:
        assert stay["id"] == reservation["id"]
        assert guest["id"] != stay["id"]
        assert stay["date_from"] == reservation["date_from"]
        assert stay["date_to"] == reservation["date_to"]
        assert stay["apartment_id"] == apartment["id"]
        assert guest["reservation_id"] == reservation["id"]
        assert guest["surname"].startswith("Guest"), "guest fields stopped hydrating"


# --- item 5: the ready count is derived, not recomputed -------------------


def test_count_sendable_stays_is_gone():
    assert not hasattr(reporting, "count_sendable_stays")


# --- item 6: one validation pass per guest --------------------------------


def test_reservation_progress_validates_each_guest_once(monkeypatch):
    apartment, reservation = _seed_stay_with_guests(3, "tok-eff-progress")
    incomplete = db.query(
        "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (reservation["id"],)
    )[2]["id"]
    db.update("guest", incomplete, {"surname": "", "first_name": ""})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))

    calls = []
    original = reporting.guest_is_complete

    def spy(guest, stay):
        calls.append(guest["id"])
        return original(guest, stay)

    monkeypatch.setattr(reporting, "guest_is_complete", spy)
    progress = reporting.reservation_progress(reservation)

    assert len(calls) == 3, "a guest is still validated twice per row"
    assert sorted(calls) == sorted({guest_id for guest_id in calls})
    assert progress["filled"] == 2
    assert [guest["id"] for guest in progress["incomplete"]] == [incomplete]
    assert progress["status"] == "incomplete"


# --- item 7: the demo lookup short-circuits -------------------------------


def test_the_demo_lookup_is_skipped_off_the_mock_environment(monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "prod")
    calls = []
    monkeypatch.setattr(db, "query_one", lambda *args, **kwargs: calls.append(args) or None)

    assert demo.is_demo_apartment({"internal_name": "Flat", "legal_entity_id": 1}) is False
    assert calls == [], "a legal_entity query per dashboard row on a real deployment"


def test_a_demo_apartment_is_still_recognised_in_the_mock_environment(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    assert demo.is_demo_apartment(
        {"internal_name": demo.DEMO_APARTMENT, "legal_entity_id": 1}
    ) is True
    assert demo.is_demo_apartment({"internal_name": "Flat", "legal_entity_id": 1}) is False

    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity", {"name": demo.DEMO_CONTROLLER, "seat": "Praha", "created_at": now}
    )
    try:
        assert demo.is_demo_apartment(
            {"internal_name": "Flat", "legal_entity_id": entity_id}
        ) is True
    finally:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))


# --- item 8: no side effects at import time -------------------------------


def test_importing_config_writes_nothing_to_disk(tmp_path):
    data_dir = tmp_path / "not-created-yet"
    env = dict(os.environ)
    env["UBYHOST_DATA_DIR"] = str(data_dir)
    env.pop("UBYHOST_SECRET_KEY", None)
    env["PYTHONPATH"] = str(PROJECT_DIR)

    result = subprocess.run(
        [sys.executable, "-c", "import app.config as c; print(hasattr(c, 'SECRET_KEY'))"],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", "the secret is still loaded at import"
    assert not data_dir.exists(), "importing config still creates the data directory"


def test_the_data_directory_and_secret_are_created_on_demand(monkeypatch, tmp_path):
    fresh = tmp_path / "fresh"
    monkeypatch.setattr(config, "DATA_DIR", fresh)
    monkeypatch.setattr(config, "_SECRET_FILE", fresh / "secret_key")
    monkeypatch.setattr(config, "_SECRET_KEY", None)
    monkeypatch.delenv("UBYHOST_SECRET_KEY", raising=False)

    assert not fresh.exists()
    assert config.ensure_data_dir() == fresh
    assert fresh.is_dir()

    key = config.secret_key()
    assert len(key) >= 32
    assert (fresh / "secret_key").read_text().strip() == key
    assert config.secret_key() == key, "the key has to be stable within a process"


def test_the_wsa_header_flag_is_read_when_it_is_used(monkeypatch):
    from app.ubyport import client as ubyport_client

    monkeypatch.setenv("UBYHOST_SOAP_WSA_HEADER", "0")
    assert ubyport_client.include_wsa_header() is False
    monkeypatch.setenv("UBYHOST_SOAP_WSA_HEADER", "1")
    assert ubyport_client.include_wsa_header() is True
    monkeypatch.setenv("UBYHOST_SOAP_WSA_HEADER", "no")
    assert ubyport_client.include_wsa_header() is False
