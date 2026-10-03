"""WP18: numbered migrations, RETURNING id, ON CONFLICT and null-safe comparisons.

None of this adds Postgres. It makes the later move mechanical: schema changes
are numbered files recorded in schema_migrations, ids come from RETURNING,
upserts use ON CONFLICT, and null-safe equality is one helper.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from app import codelists, config, db


# The migration files the app ships (WP19 on). Each test runs on a copy of
# them, so a test can add its own file with the next free number.
SHIPPED = db.migration_files()
LATEST = max([db.BASELINE_VERSION] + [version for version, _n, _p in SHIPPED])
NEXT = f"{LATEST + 1:04d}"


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "fresh.db")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path / "migrations")
    (tmp_path / "migrations").mkdir()
    for _version, _name, path in SHIPPED:
        (tmp_path / "migrations" / path.name).write_text(path.read_text(encoding="utf-8"))
    return tmp_path


def _schema(path: Path) -> dict:
    """Every table's columns and every index/trigger's SQL, schema_migrations aside."""
    conn = sqlite3.connect(str(path))
    try:
        out = {}
        for kind, name, sql in conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
            "AND name != 'schema_migrations' ORDER BY type, name"
        ):
            if kind == "table":
                out[name] = sorted(
                    (row[1], row[2], row[3], row[4], row[5])
                    for row in conn.execute(f"PRAGMA table_info({name})")
                )
            else:
                out[f"{kind}:{name}"] = sql
        return out
    finally:
        conn.close()


def _pre_wp18_database(path: Path) -> None:
    """A database as the release before WP18 left it: no schema_migrations."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        db._add_missing_columns(conn)
        conn.executescript(db.SCHEMA)
        db._add_missing_columns(conn)
        db._reset_reverted_stay_fee(conn)
        conn.execute(
            "INSERT INTO user_account (username, password_hash, created_at) "
            "VALUES ('pre-wp18', 'x', '2026-01-01T00:00:00+00:00')"
        )
    finally:
        conn.close()


def test_an_empty_database_is_created_at_the_baseline(fresh):
    db.init_db()
    assert db.schema_version() == LATEST
    tables = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"guest", "submission", "schema_migrations", "legal_acceptance"} <= tables
    db.init_db()
    rows = db.query("SELECT version, name FROM schema_migrations ORDER BY version")
    assert [(row["version"], row["name"]) for row in rows] == [(1, "baseline")] + [
        (version, name) for version, name, _path in SHIPPED
    ]


def test_an_existing_database_is_marked_at_the_current_version_unchanged(fresh):
    current = fresh / "fresh.db"
    _pre_wp18_database(current)
    before = _schema(current)
    assert db.schema_version() == 0, "the old release had no schema_migrations"

    db.init_db()

    assert db.schema_version() == LATEST
    after = _schema(current)
    # Marking the baseline changes nothing that was there; the shipped
    # migrations only add to it.
    assert {key: after.get(key) for key in before} == before
    assert db.query_one("SELECT username FROM user_account WHERE username = 'pre-wp18'")


def test_an_empty_and_an_upgraded_database_end_with_the_same_schema(fresh, tmp_path, monkeypatch):
    db.init_db()
    created = _schema(config.DB_PATH)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "upgraded.db")
    _pre_wp18_database(config.DB_PATH)
    db.init_db()
    assert _schema(config.DB_PATH) == created


def test_a_numbered_migration_is_applied_once_and_recorded(fresh):
    (fresh / "migrations" / f"{NEXT}_demo_column.sql").write_text(
        "-- a demo migration\n"
        "ALTER TABLE settings ADD COLUMN demo_note TEXT;\n"
        "CREATE INDEX IF NOT EXISTS idx_settings_demo ON settings (demo_note);\n"
    )
    db.init_db()
    db.init_db()
    assert db.schema_version() == LATEST + 1
    columns = [row["name"] for row in db.query("PRAGMA table_info(settings)")]
    assert columns.count("demo_note") == 1
    row = db.query_one("SELECT name FROM schema_migrations WHERE version = ?", (LATEST + 1,))
    assert row["name"] == "demo_column"


def test_an_existing_database_gets_later_migrations_on_top_of_the_baseline(fresh):
    _pre_wp18_database(config.DB_PATH)
    (fresh / "migrations" / f"{NEXT}_demo_column.sql").write_text(
        "ALTER TABLE settings ADD COLUMN demo_note TEXT;\n"
    )
    db.init_db()
    assert db.schema_version() == LATEST + 1
    assert db.query_one("SELECT username FROM user_account WHERE username = 'pre-wp18'")


def test_a_failing_migration_leaves_nothing_behind_and_is_not_recorded(fresh):
    db.init_db()
    (fresh / "migrations" / f"{NEXT}_broken.sql").write_text(
        "ALTER TABLE settings ADD COLUMN half_done TEXT;\n"
        "ALTER TABLE no_such_table ADD COLUMN x TEXT;\n"
    )
    with pytest.raises(sqlite3.OperationalError):
        db.init_db()
    assert db.schema_version() == LATEST
    columns = [row["name"] for row in db.query("PRAGMA table_info(settings)")]
    assert "half_done" not in columns


def test_a_migration_numbered_inside_the_baseline_is_refused(fresh):
    (fresh / "migrations" / "0001_too_low.sql").write_text("SELECT 1;\n")
    with pytest.raises(RuntimeError, match="baseline"):
        db.init_db()


def test_files_that_are_not_migrations_are_ignored(fresh):
    (fresh / "migrations" / ".gitkeep").write_text("")
    (fresh / "migrations" / "notes.txt").write_text("not sql")
    db.init_db()
    assert db.schema_version() == LATEST


# --- RETURNING, ON CONFLICT, null-safe comparison ----------------------------

def test_insert_returns_the_new_id_and_execute_the_row_count(fresh):
    db.init_db()
    first = db.insert("user_account", {"username": "a", "password_hash": "x",
                                       "created_at": db.utcnow()})
    second = db.insert("user_account", {"username": "b", "password_hash": "x",
                                        "created_at": db.utcnow()})
    assert second == first + 1
    assert db.query_one("SELECT username FROM user_account WHERE id = ?", (second,))["username"] == "b"
    assert db.insert("settings", {"key": "k", "value": "v"}) is None
    assert db.execute("UPDATE user_account SET display_name = 'x'") == 2


def test_the_send_claim_still_refuses_a_second_holder(fresh):
    db.init_db()
    sql = (
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES (?, ?, ?) "
        "ON CONFLICT (guest_id) DO NOTHING"
    )
    conn = db.connect()
    try:
        # No guest row is needed to test the conflict rule itself.
        conn.execute("PRAGMA foreign_keys = OFF")
        assert conn.execute(sql, (7, "first", 1.0)).rowcount == 1
        assert conn.execute(sql, (7, "second", 2.0)).rowcount == 0
        token = conn.execute("SELECT claim_token FROM submission_claim WHERE guest_id = 7").fetchone()
    finally:
        conn.close()
    assert token[0] == "first", "the claim that got there first keeps the guest"


def test_the_codelist_upsert_keeps_one_row_with_the_latest_values(fresh, monkeypatch):
    db.init_db()
    rows = [{"Kod": "CZE", "TextCZ": "Česko", "TextKratkyEN": "Czechia old"},
            {"Kod": "CZE", "TextCZ": "Česko", "TextKratkyEN": "Czechia"}]
    monkeypatch.setattr(codelists, "_code_and_texts", lambda kind, row: (
        row["Kod"], row["TextCZ"], row["TextKratkyEN"]))
    codelists.store("Staty", rows)
    stored = db.query("SELECT code, text_en FROM codelist WHERE kind = 'Staty'")
    assert [(row["code"], row["text_en"]) for row in stored] == [("CZE", "Czechia")]


def test_null_safe_eq_matches_null_the_way_is_did(fresh):
    db.init_db()
    now = db.utcnow()
    owned = db.insert("apartment", {"internal_name": "owned", "owner_user_id": None,
                                    "created_at": now})
    sql = f"SELECT id FROM apartment WHERE {db.null_safe_eq('owner_user_id')}"
    assert [row["id"] for row in db.query(sql, (None,))] == [owned]
    assert db.query(sql, (12345,)) == []
    assert db.null_safe_eq("a.owner_user_id") == "a.owner_user_id IS ?"


def test_no_sqlite_only_insert_variants_or_bare_is_comparisons_remain():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("INSERT OR IGNORE", "INSERT OR REPLACE", ".lastrowid"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
        # db.py defines the helper and explains it in prose.
        if path.name != "db.py" and re.search(r"[\w)] IS \?", text):
            offenders.append(f"{path.name}: x IS ? (use db.null_safe_eq)")
    assert offenders == []
