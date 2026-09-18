"""Production-style upgrade coverage for databases created before PIN support."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app import config, db, scheduler
from app.main import app


def test_older_apartment_schema_migrates_and_serves_pages(monkeypatch, tmp_path):
    database = tmp_path / "ubyhost-old.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute(
        """
        CREATE TABLE apartment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            legal_entity_id INTEGER,
            internal_name TEXT NOT NULL,
            city_en TEXT,
            addr_okres TEXT,
            addr_obec TEXT,
            addr_obec_cast TEXT,
            addr_street TEXT,
            addr_house_no TEXT,
            addr_orient_no TEXT,
            addr_zip TEXT,
            uby_idub TEXT,
            uby_mark TEXT,
            uby_name TEXT,
            uby_contact TEXT,
            uby_ws_user TEXT,
            uby_ws_password_enc TEXT,
            automation_mode TEXT NOT NULL DEFAULT 'scheduled',
            submit_after_hours INTEGER NOT NULL DEFAULT 24,
            permalink_token TEXT UNIQUE,
            permalink_window_days INTEGER NOT NULL DEFAULT 3,
            default_purpose TEXT NOT NULL DEFAULT '10',
            checkin_info TEXT,
            checkout_info TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO apartment "
        "(internal_name, permalink_token, automation_mode, created_at) "
        "VALUES ('Legacy flat', 'legacy-token', 'manual', '2025-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "DB_PATH", database)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN", False)
    monkeypatch.setattr(scheduler, "start", lambda: None)
    monkeypatch.setattr(scheduler, "shutdown", lambda: None)

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/apartments").status_code == 200

    columns = {row["name"] for row in db.query("PRAGMA table_info(apartment)")}
    assert {"owner_user_id", "permalink_pin", "archived_at", "guest_message"} <= columns
    assert db.query_one("SELECT permalink_pin FROM apartment")["permalink_pin"]
    assert db.query_one(
        "SELECT 1 AS present FROM sqlite_master "
        "WHERE type = 'table' AND name = 'submission_claim'"
    )
    assert db.query_one(
        "SELECT 1 AS present FROM sqlite_master "
        "WHERE type = 'table' AND name = 'reservation_claim'"
    )
    claim_columns = {
        row["name"] for row in db.query("PRAGMA table_info(reservation_claim)")
    }
    assert "guest_access_reopened_at" in claim_columns
    assert db.query_one(
        "SELECT 1 AS present FROM sqlite_master "
        "WHERE type = 'table' AND name = 'email_outbox'"
    )
