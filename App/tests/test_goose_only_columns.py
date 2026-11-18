from __future__ import annotations

import textwrap


import test_db_postgres as pgt
from app import db

PG_ONLY = pgt.pytestmark


def test_goose_only_columns_parsed_from_migrations():
    columns = db.goose_only_columns()
    assert ("submission", "cause", "TEXT") in columns
    assert ("submission", "error_code", "TEXT") in columns


@PG_ONLY
def test_temporary_goose_only_add_column_keeps_schema_current():
    db._goose_only_add_column_specs.cache_clear()
    probe = db.GOOSE_DIR / "99998_1660_probe.sql"
    probe.write_text(
        textwrap.dedent(
            """\
            -- +goose Up
            ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS probe_1660 TEXT;
            -- +goose Down
            ALTER TABLE site_booking DROP COLUMN IF EXISTS probe_1660;
            """
        ),
        encoding="utf-8",
    )
    try:
        db._goose_only_add_column_specs.cache_clear()
        conn = db.connect()
        try:
            conn.execute_native(
                "ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS probe_1660 TEXT"
            )
        finally:
            conn.close()
        status = db.postgres_schema_status()
        assert status["current"] is True
    finally:
        probe.unlink(missing_ok=True)
        conn = db.connect()
        try:
            conn.execute_native("ALTER TABLE site_booking DROP COLUMN IF EXISTS probe_1660")
        finally:
            conn.close()
        db._goose_only_add_column_specs.cache_clear()


@PG_ONLY
def test_hand_added_column_without_goose_file_is_a_mismatch():
    conn = db.connect()
    try:
        conn.execute_native("ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS orphan_1660 TEXT")
    finally:
        conn.close()
    try:
        status = db.postgres_schema_status()
        assert status["current"] is False
        assert status["column_mismatches"] >= 1
    finally:
        conn = db.connect()
        try:
            conn.execute_native("ALTER TABLE site_booking DROP COLUMN IF EXISTS orphan_1660")
        finally:
            conn.close()