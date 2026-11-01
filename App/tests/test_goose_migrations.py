from __future__ import annotations

import pytest

import test_db_postgres as pgt  # reuses the PostgreSQL skip guard, target checks and reset helper
from app import db

PG_ONLY = pgt.pytestmark


def _run(statement: str) -> None:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute_native(statement)
        conn.execute("COMMIT")
    finally:
        conn.close()


@pytest.fixture
def pg_goose():
    assert pgt.TARGET["is_test"] and pgt.TARGET["loopback"]
    db.close_connections()
    pgt._reset_public_schema()
    db.apply_postgresql_schema()
    yield
    db.close_connections()


def test_goose_files_start_at_the_baseline_with_unique_names():
    files = db.goose_files()
    assert files[0][0] == 1
    assert files[0][1] == "baseline"
    names = [name for _version, name, _path in files]
    assert len(names) == len(set(names))
    for _version, _name, path in files:
        assert "-- +goose Up" in path.read_text(encoding="utf-8")


def test_goose_statement_block_stays_whole():
    text = (
        "-- +goose Up\n"
        "CREATE TABLE a (id integer);\n"
        "-- +goose StatementBegin\n"
        "CREATE FUNCTION f() RETURNS int AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;\n"
        "-- +goose StatementEnd\n"
        "-- +goose Down\n"
        "DROP TABLE a;\n"
    )
    statements = db._goose_up_statements(text)
    assert len(statements) == 2
    assert statements[0] == "CREATE TABLE a (id integer);"
    assert statements[1].startswith("CREATE FUNCTION")
    assert statements[1].endswith("LANGUAGE plpgsql;")


@PG_ONLY
def test_baseline_is_recorded_and_nothing_is_pending(pg_goose):
    conn = db.connect()
    try:
        assert db.goose_pending(conn) == []
        assert 1 in db.goose_applied(conn)
    finally:
        conn.close()


@PG_ONLY
def test_a_missing_baseline_row_stops_validation_until_apply(pg_goose):
    _run("DELETE FROM goose_db_version WHERE version_id = 1")
    with pytest.raises(RuntimeError, match="goose migrations 1"):
        db.validate_postgres_schema()
    db.apply_postgresql_schema()
    conn = db.connect()
    try:
        assert 1 in db.goose_applied(conn)
    finally:
        conn.close()


@PG_ONLY
def test_a_table_outside_the_baseline_keeps_the_schema_current(pg_goose):
    before = db.postgres_schema_status()["extra_tables"]
    _run("CREATE TABLE zz_extra (id bigint)")
    status = db.postgres_schema_status()
    assert status["current"] is True
    assert status["extra_tables"] == before + 1


@PG_ONLY
def test_a_current_schema_without_goose_table_adopts_baseline(pg_goose):
    _run("DROP TABLE goose_db_version")
    # 00002 (poll indexes) is pending after adoption: the app refuses to start until it is applied.
    with pytest.raises(RuntimeError, match="goose migrations 2 are not applied"):
        db.validate_postgres_schema()
    conn = db.connect()
    try:
        applied = db.goose_applied(conn)
    finally:
        conn.close()
    assert 1 in applied and 2 not in applied
    db.apply_postgresql_schema()
    assert db.validate_postgres_schema()["goose_pending"] == []
