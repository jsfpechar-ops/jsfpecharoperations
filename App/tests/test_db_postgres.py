"""PostgreSQL 16+ integration tests for the 0455 runtime and verified transfer.

These tests exercise a real PostgreSQL server, so they need their own pytest
process configured the way a PostgreSQL deployment is. The actual application
setting is used, as the app reads it once at import time::

    UBYHOST_DATABASE_URL='postgresql://ubyhost@127.0.0.1:55432/ubyhost_test?sslmode=require' \
        .venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x

The session fixture refuses to touch any target that is not loopback/Unix
socket with a database name containing ``test``, and it rebuilds the ``public``
schema from scratch at session start so a previous or aborted run cannot mask a
failure. Under the default SQLite test environment every test in this module
skips with an explicit reason; that is the only backend-only skip in the DB row.

No assertion, report or error message may contain a DSN, a password or a real
guest value: the fixtures are synthetic and the reports are checked for it.

Two backend facts the transfer tests rely on, both asserted rather than assumed:

* Typed digests order rows with ``ORDER BY`` on every column. SQLite sorts NULLs
  FIRST and PostgreSQL sorts them LAST, which would be backend-dependent for
  nullable leading columns. ``test_transfer_digest_order_is_null_stable_across_backends``
  proves that every frozen-schema table's primary key is a leading, NOT NULL
  prefix of its column order, so a row comparison is always decided before a
  NULL could be compared; the transfer's single ORDER BY stays deterministic on
  both backends without changing application SQL.
* PostgreSQL 16+ clusters are initialised with ``--no-locale`` (C), matching
  SQLite's ASCII-only LIKE/lower folding. No test here assumes Unicode case
  folding or locale-dependent collation: every LIKE/ILIKE assertion is ASCII
  only, and values with non-ASCII text are compared exactly, never folded.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Either name selects PostgreSQL mode; the app itself reads the first one. The
# extra name keeps the fixture contract of the 0455 brief usable too.
_PG_URL = os.environ.get("UBYHOST_DATABASE_URL") or os.environ.get(
    "UBYHOST_TEST_DATABASE_URL"
)
if _PG_URL and not os.environ.get("UBYHOST_DATABASE_URL"):
    os.environ["UBYHOST_DATABASE_URL"] = _PG_URL
    os.environ.pop("UBYHOST_DB", None)

from app import config, db  # noqa: E402

pytestmark = pytest.mark.skipif(
    not _PG_URL,
    reason=(
        "PostgreSQL integration tests need UBYHOST_DATABASE_URL (or "
        "UBYHOST_TEST_DATABASE_URL) for a disposable target whose database name "
        "contains 'test'; this pytest process runs the SQLite row"
    ),
)

# Unix-socket layout from the 0455 brief (PostgreSQL 16+).
SOCKET_DIR = "/tmp/pgsock18"
SOCKET_PORT = 55432

UNICODE_VALUE = "Žluťoučký kůň 🐎"
FORBIDDEN_IN_REPORT = (
    "PASSPORT-SENTINEL",
    "WS-PASSWORD-SENTINEL",
    "TOTP-SENTINEL",
    "Žluťoučký",
    "transfer-a@example.test",
    "snapshot-test-secret-key",
    "postgresql://",
    "supersecretpw",
)
SNAPSHOT_SECRET = (
    "snapshot-test-secret-key-0123456789" "0123456789" "0123456789"
)


# --- target safety and environment -----------------------------------------


def _parse_target(url: str) -> dict:
    """The connection identity needed for the fixture's safety checks."""
    try:
        parts = urlsplit(url)
        netloc_port = parts.port
    except ValueError:
        pytest.fail("UBYHOST_DATABASE_URL is not a parseable URL; refusing to run")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    hostname = (parts.hostname or "").lower()
    socket_dir = query.get("host") or ""
    database = parts.path.strip("/")
    port = netloc_port or int(query["port"]) if query.get("port") else netloc_port
    loopback = hostname in {"127.0.0.1", "localhost", "::1"} or (
        not hostname and socket_dir.startswith("/")
    )
    return {
        "hostname": hostname,
        "socket_dir": socket_dir,
        "port": port,
        "database": database,
        "loopback": loopback,
        "is_test": "test" in database.lower(),
    }


TARGET = _parse_target(_PG_URL) if _PG_URL else None


def _psycopg_connect(url: str):
    import psycopg

    return psycopg.connect(url, autocommit=True)


def _reset_public_schema() -> None:
    """Empty target, exactly the isolated destination the transfer requires."""
    with _psycopg_connect(_PG_URL) as conn:
        conn.execute("SET client_min_messages = warning")
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


def _public_relation_count() -> int:
    with _psycopg_connect(_PG_URL) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public'"
        ).fetchone()
    return int(row[0])


@pytest.fixture(scope="session", autouse=True)
def pg_runtime():
    """Prove the target is disposable, rebuild the schema, and hand it over."""
    if not TARGET["loopback"]:
        pytest.fail(
            "refusing PostgreSQL tests: the target must be loopback or a Unix "
            f"socket (hostname={TARGET['hostname']!r}, socket={TARGET['socket_dir']!r})"
        )
    if not TARGET["is_test"]:
        pytest.fail(
            "refusing PostgreSQL tests: the database name must contain 'test' "
            f"(database={TARGET['database']!r})"
        )
    db.close_connections()
    _reset_public_schema()
    status = db.apply_postgresql_schema()
    try:
        yield status
    finally:
        db.close_connections()


# --- helpers for subprocess contracts --------------------------------------


def _base_env() -> dict:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "UBYHOST_DB",
            "UBYHOST_DATABASE_URL",
            "UBYHOST_TEST_DATABASE_URL",
            "UBYHOST_DATA_DIR",
        }
    }
    return env


def _run_python(code: str, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _pg_env(data_dir: Path) -> dict:
    env = _base_env()
    env["UBYHOST_DATABASE_URL"] = _PG_URL
    env["UBYHOST_DATA_DIR"] = str(data_dir)
    return env


def _sqlite_env(source: Path, data_dir: Path) -> dict:
    env = _base_env()
    env["UBYHOST_DB"] = str(source)
    env["UBYHOST_DATA_DIR"] = str(data_dir)
    env["UBYHOST_SECRET_KEY"] = SNAPSHOT_SECRET
    return env


def _run_transfer(
    source: Path,
    report: Path,
    *,
    verify_only: bool = False,
    data_dir: Path | None = None,
    expect_database: str | None = None,
) -> subprocess.CompletedProcess:
    directory = data_dir or (report.parent / "pg-data")
    directory.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "scripts/sqlite_to_postgres.py",
        "--source",
        str(source),
        "--report",
        str(report),
        "--expect-database",
        expect_database or TARGET["database"],
    ]
    if verify_only:
        command.append("--verify-only")
    return subprocess.run(
        command,
        cwd=str(PROJECT_DIR),
        env=_pg_env(directory),
        capture_output=True,
        text=True,
        timeout=180,
    )


# --- a. full schema apply + validate ---------------------------------------


def test_full_schema_apply_and_validate_on_postgres(pg_runtime):
    assert config.DB_BACKEND == "postgresql"
    status = db.postgres_schema_status()
    assert status["current"] is True
    assert status["actual_version"] == db.expected_schema_version() == 33
    assert status["expected_tables"] == status["actual_tables"] == 67
    assert status["missing_tables"] == status["extra_tables"] == 0
    assert status["column_mismatches"] == 0
    assert status["missing_indexes"] == 0
    assert status["missing_triggers"] == status["extra_triggers"] == 0
    assert status["database"] == TARGET["database"]

    validated = db.validate_postgres_schema()
    assert validated["current"] is True
    assert validated["database"] == TARGET["database"]

    connection = db.connect()
    try:
        version = int(connection.execute_native("SHOW server_version_num").fetchone()[0])
        triggers = {
            row["name"]
            for row in connection.execute_native(
                "SELECT t.tgname AS name FROM pg_trigger t "
                "JOIN pg_class c ON c.oid = t.tgrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() AND NOT t.tgisinternal"
            ).fetchall()
        }
        database = connection.execute_native("SELECT current_database() AS name").fetchone()["name"]
    finally:
        connection.close()
    assert version >= 160000, f"PostgreSQL {version} is older than the required 16"
    assert triggers == {
        "invoice_issued_guard",
        "invoice_note_guard",
        "invoice_delete_guard",
        "invoice_item_insert_guard",
        "invoice_item_update_guard",
        "invoice_item_delete_guard",
    }
    assert database == TARGET["database"]

    history = db.query("SELECT version, name FROM schema_migrations ORDER BY version")
    assert history[0]["version"] == 1 and history[0]["name"] == "baseline"
    assert [row["version"] for row in history] == list(range(1, 34))


def test_schema_apply_and_validate_are_idempotent_on_postgres(pg_runtime):
    before = db.postgres_schema_status()
    apply_status = db.apply_postgresql_schema()
    after = db.postgres_schema_status()
    for key in (
        "actual_version",
        "actual_tables",
        "missing_tables",
        "extra_tables",
        "column_mismatches",
        "missing_indexes",
        "missing_triggers",
        "extra_triggers",
    ):
        assert apply_status[key] == before[key] == after[key], key
    assert after["current"] is True
    assert db.schema_version() == 33
    connection = db.connect()
    try:
        trigger_count = connection.execute_native(
            "SELECT COUNT(*) AS n FROM pg_trigger WHERE NOT tgisinternal"
        ).fetchone()["n"]
    finally:
        connection.close()
    assert trigger_count == 6
    assert db.query_one("SELECT COUNT(*) AS n FROM schema_migrations")["n"] == 33


def test_pg_schema_cli_reports_and_applies_the_current_schema(pg_runtime, tmp_path):
    env = _pg_env(tmp_path / "cli-data")
    expected_database = TARGET["database"]
    base = [sys.executable, "scripts/pg_schema.py"]
    plan = subprocess.run(
        [*base, "plan", "--expect-database", expected_database],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert plan.returncode == 0, plan.stderr[-1000:]
    assert "schema version 33 is planned" in plan.stdout

    apply = subprocess.run(
        [*base, "apply", "--expect-database", expected_database],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert apply.returncode == 0, apply.stderr[-1000:]
    assert "version=33" in apply.stdout and "tables=67" in apply.stdout

    wrong = subprocess.run(
        [*base, "check", "--expect-database", "definitely-not-this-database"],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert wrong.returncode == 1
    assert "does not match --expect-database" in wrong.stderr
    combined = wrong.stdout + wrong.stderr
    assert "postgresql://" not in combined
    assert "ubyhost@127.0.0.1" not in combined


# --- b. placeholder lexer --------------------------------------------------


def _adapter():
    from app import db_postgres

    return db_postgres


def test_placeholder_lexer_preserves_literals_identifiers_and_comments():
    adapter = _adapter()
    # A question mark or percent inside a string literal stays literal.
    converted, params = adapter.adapt_sql("SELECT 'a?b%c' AS v", ())
    assert converted == "SELECT 'a?b%%c' AS v"
    assert params == ()
    assert "%s" not in converted
    # Quoted identifiers are identifiers, not binds and not SQL keywords.
    converted, _ = adapter.adapt_sql('SELECT "odd?%col" FROM t', ())
    assert converted == 'SELECT "odd?%%col" FROM t'
    assert "%s" not in converted
    # Line comment.
    converted, _ = adapter.adapt_sql("SELECT 1 -- literal ? and %\n", ())
    assert converted == "SELECT 1 -- literal ? and %%\n"
    # Block comment, including a nested block comment.
    block = "SELECT /* outer ? % /* nested ? % */ still ? % */ 1"
    converted, params = adapter.adapt_sql(block, ())
    assert converted == block.replace("%", "%%")
    assert params == () and "%s" not in converted
    # Dollar quoting.
    dollar = "SELECT $$ a?b%c $$, $tag$ ? % $tag$"
    converted, _ = adapter.adapt_sql(dollar, ())
    assert converted == "SELECT $$ a?b%%c $$, $tag$ ? %% $tag$"
    # Real binds become psycopg markers, in order.
    assert adapter.adapt_sql("SELECT ? + ?", (1, 2)) == ("SELECT %s + %s", (1, 2))
    assert adapter.adapt_sql("SELECT ? IS NULL", (None,)) == (
        "SELECT %s::text IS NULL",
        (None,),
    )
    # SQLite LIKE case folding is preserved for bare LIKE, never for a literal.
    assert adapter.adapt_sql("SELECT name LIKE ? FROM t", ("a",))[0] == (
        "SELECT name ILIKE %s FROM t"
    )
    assert adapter.adapt_sql("SELECT name NOT LIKE ? FROM t", ("a",))[0] == (
        "SELECT name NOT ILIKE %s FROM t"
    )
    assert adapter.adapt_sql("SELECT 'LIKE ? %' AS v", ())[0] == (
        "SELECT 'LIKE ? %%' AS v"
    )
    assert adapter.adapt_sql('SELECT "like" FROM t', ())[0] == 'SELECT "like" FROM t'
    # No params means psycopg is handed no query grammar at all.
    assert adapter.adapt_sql("SELECT ?", None) == ("SELECT ?", None)
    with pytest.raises(ValueError, match="bind markers"):
        adapter.adapt_sql("SELECT ?", ())


def test_bound_punctuation_comments_and_like_execute_on_postgres(pg_runtime):
    assert db.query_one("SELECT 'a?b%c' AS v", ())["v"] == "a?b%c"
    assert (
        db.query_one('SELECT q."odd?%col" AS v FROM (SELECT 7 AS "odd?%col") AS q')
    )["v"] == 7
    assert db.query_one("SELECT 5 AS v -- literal ? and %\n")["v"] == 5
    assert db.query_one("SELECT /* outer ? % /* nested ? */ still */ 6 AS v")["v"] == 6
    row = db.query_one("SELECT ? AS a, ? AS b, ? AS c", (1, "Δ", None))
    assert (row["a"], row["b"], row["c"]) == (1, "Δ", None)
    # SQLite LIKE folded ASCII case; the adapter keeps that behaviour. The C
    # locale of the PostgreSQL 16+ cluster matches this, so only ASCII folding is asserted
    # here; no test below assumes Unicode case folding.
    assert db.query_one("SELECT 'ABC' LIKE ? AS v", ("abc",))["v"] is True
    assert db.query_one("SELECT 'AbC' LIKE ? AS v", ("a%",))["v"] is True
    assert db.query_one("SELECT 'abc' ILIKE ? AS v", ("ABC",))["v"] is True
    # Literal percent signs in patterns still mean "wildcard", not a bind.
    assert db.query_one("SELECT '100%' LIKE '100%' AS v", ())["v"] is True
    assert db.query_one("SELECT 'a_b' LIKE ? AS v", ("a_b",))["v"] is True
    # Injection-shaped input is data, never SQL.
    injection = "x'; DROP TABLE settings; -- Δ?%"
    assert db.query_one("SELECT ? AS v", (injection,))["v"] == injection
    assert db.query_one("SELECT COUNT(*) AS n FROM settings")["n"] >= 0


# --- c. read-only export transaction ---------------------------------------


def test_readonly_cursor_is_repeatable_read_read_only_and_write_refusing(pg_runtime):
    from psycopg import errors as pg_errors

    with pytest.raises(Exception) as info:
        with db.readonly_cursor() as cur:
            assert cur.execute("SHOW transaction_isolation").fetchone()[0] == "repeatable read"
            assert cur.execute("SHOW transaction_read_only").fetchone()[0] == "on"
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ("readonly-write-probe", "x"),
            )
    assert isinstance(info.value, pg_errors.ReadOnlySqlTransaction)
    assert getattr(info.value, "sqlstate", None) == "25006"
    assert (
        db.query_one("SELECT COUNT(*) AS n FROM settings WHERE key = ?", ("readonly-write-probe",))[
            "n"
        ]
        == 0
    )


def test_readonly_cursor_keeps_one_snapshot_under_a_concurrent_commit(pg_runtime):
    key = "readonly-snapshot-probe"
    db.set_setting(key, "before")
    try:
        with db.readonly_cursor() as cur:
            first = cur.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            assert first["value"] == "before"
            writer = db.connect()
            try:
                writer.execute("UPDATE settings SET value = ? WHERE key = ?", ("after", key))
            finally:
                writer.close()
            # A write committed after the snapshot started is invisible here.
            second = cur.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            assert second["value"] == "before"
        assert db.get_setting(key) == "after"
    finally:
        db.execute("DELETE FROM settings WHERE key = ?", (key,))


# --- d. integrity mapping and helper contract ------------------------------


def test_integrity_errors_map_to_the_postgres_driver(pg_runtime):
    key = "integrity-probe"
    db.execute("DELETE FROM settings WHERE key IN (?, ?)", (key, "integrity-probe-after"))
    db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, "first"))
    try:
        with pytest.raises(Exception) as info:
            db.insert("settings", {"key": key, "value": "second"})
        exc = info.value
        assert isinstance(exc, db.integrity_errors())
        # No sqlite3 exception type may leak from the tested PostgreSQL path.
        assert not isinstance(exc, sqlite3.IntegrityError)
        assert db.is_unique_violation(exc) is True
        assert getattr(exc, "sqlstate", None) == "23505"
        # The failed helper left the connection usable.
        assert db.get_setting(key) == "first"
        db.set_setting("integrity-probe-after", "still-works")
        assert db.get_setting("integrity-probe-after") == "still-works"
    finally:
        db.execute(
            "DELETE FROM settings WHERE key IN (?, ?)", (key, "integrity-probe-after")
        )


def test_row_access_returning_rowcount_and_transaction_rollback(pg_runtime):
    username = "helper-contract-probe"
    db.execute("DELETE FROM user_account WHERE username = ?", (username,))
    account_id = db.insert(
        "user_account",
        {"username": username, "password_hash": "x", "created_at": db.utcnow()},
    )
    assert isinstance(account_id, int) and account_id > 0
    row = db.query_one(
        "SELECT id, username, display_name FROM user_account WHERE id = ?", (account_id,)
    )
    assert row[0] == account_id
    assert row["username"] == username
    assert row["display_name"] is None
    assert "username" in row.keys()
    assert len(row) == 3
    assert db.is_decrypted(row) is False
    assert (
        db.execute(
            "UPDATE user_account SET display_name = ? WHERE id = ?", ("shown", account_id)
        )
        == 1
    )
    with pytest.raises(RuntimeError, match="boom"):
        with db.immediate() as cur:
            db.update_in(cur, "user_account", account_id, {"display_name": "rolled-back"})
            raise RuntimeError("boom")
    assert (
        db.query_one(
            "SELECT display_name FROM user_account WHERE id = ?", (account_id,)
        )["display_name"]
        == "shown"
    )
    db.execute("DELETE FROM user_account WHERE id = ?", (account_id,))


# --- e. encrypted field round trip -----------------------------------------


def test_encrypted_fields_round_trip_through_db_helpers(pg_runtime):
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "encrypted-roundtrip-probe", "created_at": now},
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "ical",
            "uid": "encrypted-roundtrip-uid",
            "date_from": "2026-03-01",
            "date_to": "2026-03-02",
            "created_at": now,
            "updated_at": now,
        },
    )
    plaintext = "PASSPORT-ROUNDTRIP-Δ-?%"
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Kůň",
            "first_name": "Žofie",
            "doc_number": plaintext,
            "birth_date": "1990-01-02",
            "created_at": now,
            "updated_at": now,
        },
    )

    raw = db.connect()
    try:
        stored = raw.execute(
            "SELECT doc_number, doc_number_enc, birth_date, birth_date_enc "
            "FROM guest WHERE id = ?",
            (guest_id,),
        ).fetchone()
        raw_request = raw.execute(
            "SELECT request_xml, request_xml_enc FROM submission WHERE id = ?",
            (
                db.insert(
                    "submission",
                    {
                        "apartment_id": apartment_id,
                        "created_at": now,
                        "request_xml": "<request>?%Δ</request>",
                    },
                ),
            ),
        ).fetchone()
    finally:
        raw.close()

    # The plaintext columns stay empty; the stored ciphertext is not the value.
    assert stored["doc_number"] is None
    token = stored["doc_number_enc"]
    assert isinstance(token, str)
    assert token.startswith("gAAAAA")
    assert token != plaintext and plaintext not in token
    assert stored["birth_date"] is None
    assert stored["birth_date_enc"] not in (None, "1990-01-02")
    assert raw_request["request_xml"] is None
    assert "<request>" not in (raw_request["request_xml_enc"] or "")

    hydrated = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert db.is_decrypted(hydrated) is True
    assert hydrated["doc_number"] == plaintext
    assert hydrated["birth_date"] == "1990-01-02"
    assert hydrated["doc_number_enc"] == token
    assert hydrated["doc_number"] != hydrated["doc_number_enc"]

    fresh_plaintext = "PASSPORT-ROUNDTRIP-UPDATED-Δ"
    db.update("guest", guest_id, {"doc_number": fresh_plaintext})
    updated = db.query_one(
        "SELECT doc_number, doc_number_enc FROM guest WHERE id = ?", (guest_id,)
    )
    assert updated["doc_number"] == fresh_plaintext
    assert updated["doc_number_enc"] != token
    assert fresh_plaintext not in updated["doc_number_enc"]

    submission_row = db.query_one(
        "SELECT request_xml, request_xml_enc FROM submission WHERE apartment_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (apartment_id,),
    )
    assert submission_row["request_xml"] == "<request>?%Δ</request>"
    assert "<request>" not in submission_row["request_xml_enc"]


# --- f. writer serialisation and bounded locking ---------------------------


def test_concurrent_writers_serialise_without_duplicates(pg_runtime):
    prefix = "writer-probe"
    db.execute("DELETE FROM user_account WHERE username LIKE ?", (prefix + "%",))

    def write(worker: int) -> list[int]:
        return [
            db.insert(
                "user_account",
                {
                    "username": f"{prefix}-{worker}-{index}",
                    "password_hash": "x",
                    "created_at": db.utcnow(),
                },
            )
            for index in range(8)
        ]

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            batches = list(pool.map(write, range(4)))
        ids = [row_id for batch in batches for row_id in batch]
        assert len(ids) == 32
        assert len(set(ids)) == 32, "concurrent writers reused an identity"
        rows = db.query(
            "SELECT id, username FROM user_account WHERE username LIKE ?",
            (prefix + "%",),
        )
        assert len(rows) == 32
        assert len({row["username"] for row in rows}) == 32
        assert sorted(ids) == sorted(row["id"] for row in rows)
    finally:
        db.execute("DELETE FROM user_account WHERE username LIKE ?", (prefix + "%",))


def test_writer_lock_wait_is_bounded_and_recovers(pg_runtime, monkeypatch):
    from psycopg import errors as pg_errors

    from app import db_postgres

    monkeypatch.setattr(db_postgres, "LOCK_TIMEOUT", "250ms")
    holder = db.connect()
    holder.acquire_writer_session_lock()
    started = time.monotonic()
    try:
        with pytest.raises(Exception) as info:
            with db.immediate() as cur:
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("writer-lock-timeout-probe", "x"),
                )
        elapsed = time.monotonic() - started
        assert isinstance(info.value, pg_errors.LockNotAvailable)
        assert getattr(info.value, "sqlstate", None) == "55P03"
        assert 0.05 <= elapsed < 10, f"writer lock refusal took {elapsed:.2f}s"
        # The refused write left nothing behind.
        assert db.get_setting("writer-lock-timeout-probe") is None
    finally:
        holder.release_writer_session_lock()
        holder.close()
    # A later write after the holder released succeeds (no blind retry by the app).
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        ("writer-lock-timeout-probe", "retry"),
    )
    assert db.get_setting("writer-lock-timeout-probe") == "retry"
    db.execute("DELETE FROM settings WHERE key = ?", ("writer-lock-timeout-probe",))


def test_writer_lock_timeout_surfaces_as_lock_not_available_through_every_helper(
    pg_runtime, monkeypatch
):
    """Regression for 0455: a 55P03 lock timeout must not be masked by db.py.

    The adapter opens a transaction before taking the writer advisory lock. If
    lock acquisition fails, that transaction used to be left open, so
    ``db._helper_conn`` replaced psycopg's ``LockNotAvailable`` with its own
    "left a transaction open" RuntimeError. The adapter now rolls back and
    re-raises the driver error unchanged; this test pins that for the helper
    path, ``executemany``, a cursor-level ``BEGIN IMMEDIATE`` and
    ``db.immediate()``, and proves the connections stay reusable.
    """
    from psycopg import errors as pg_errors

    from app import db_postgres

    monkeypatch.setattr(db_postgres, "LOCK_TIMEOUT", "250ms")
    probe_key = "lock-not-available-probe"
    db.execute("DELETE FROM settings WHERE key = ?", (probe_key,))
    holder = db.connect()
    holder.acquire_writer_session_lock()

    def expect_lock_timeout(call):
        started = time.monotonic()
        with pytest.raises(pg_errors.LockNotAvailable) as info:
            call()
        elapsed = time.monotonic() - started
        assert getattr(info.value, "sqlstate", None) == "55P03"
        # Never db.py's "a database helper left a transaction open" RuntimeError.
        assert not isinstance(info.value, RuntimeError)
        assert "left a transaction open" not in str(info.value)
        assert elapsed < 10, f"lock wait was not bounded ({elapsed:.2f}s)"
        return info.value

    try:
        # db.execute: the original psycopg error must reach the caller.
        expect_lock_timeout(
            lambda: db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (probe_key, "execute"),
            )
        )
        assert db._thread_conn().in_transaction is False
        assert db.get_setting(probe_key) is None

        # Connection-level executemany.
        many_connection = db.connect()
        try:
            expect_lock_timeout(
                lambda: many_connection.executemany(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    [(probe_key, "many")],
                )
            )
            assert many_connection.in_transaction is False
            assert (
                many_connection.execute(
                    "SELECT COUNT(*) AS n FROM settings WHERE key = ?", (probe_key,)
                ).fetchone()["n"]
                == 0
            )
        finally:
            many_connection.close()

        # Cursor-level BEGIN IMMEDIATE, the building block of db.immediate().
        begin_connection = db.connect()
        try:
            cursor = begin_connection.cursor()
            try:
                expect_lock_timeout(lambda: cursor.execute("BEGIN IMMEDIATE"))
                assert begin_connection.in_transaction is False
            finally:
                cursor.close()
        finally:
            begin_connection.close()

        # db.immediate() keeps raising LockNotAvailable as before.
        def immediate_write():
            with db.immediate() as cur:
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    (probe_key, "immediate"),
                )

        expect_lock_timeout(immediate_write)
        assert db._thread_conn().in_transaction is False
        assert db.get_setting(probe_key) is None
    finally:
        holder.release_writer_session_lock()
        holder.close()

    # After the lock is released every path works again; no blind retry is needed.
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)", (probe_key, "retry")
    )
    try:
        assert db.get_setting(probe_key) == "retry"
    finally:
        db.execute("DELETE FROM settings WHERE key = ?", (probe_key,))


# --- g/h. SQLite -> PostgreSQL transfer and reconciliation ------------------


_SNAPSHOT_BUILDER = '''
import sqlite3

from app import db

NOW = "2026-02-03T04:05:06+00:00"
BIN = bytes((0, 1, 2)) + b"ubyhost" + bytes((255, 254))

db.init_db()


def raw(sql, params=()):
    db.execute(sql, params)


raw("INSERT INTO settings (key, value) VALUES (?, ?)", ("transfer.unicode", "\\u017dlu\\u0165ou\\u010dk\\u00fd k\\u016f\\u0148 \\U0001f40e"))
raw("INSERT INTO settings (key, value) VALUES (?, ?)", ("transfer.null", None))
for uid, username, display, email in (
    (100, "transfer-user-a", "\\u017dofie \\u2603", "transfer-a@example.test"),
    (101, "transfer-user-b", None, None),
):
    raw(
        "INSERT INTO user_account (id, username, display_name, password_hash, role, active,"
        " must_change_password, session_version, created_at, email, totp_enabled)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, username, display, "hash-not-a-secret", "host", 1, 0, 1, NOW, email, 0),
    )
raw(
    "UPDATE user_account SET totp_secret_enc = ? WHERE id = 100",
    (db.encrypt_secret("TOTP-SENTINEL"),),
)
raw(
    "INSERT INTO legal_entity (id, name, vat_status, invoice_due_days, owner_user_id,"
    " created_at, business_type, invoice_next_number, invoice_next_number_year)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (300, "\\u017dofie s.r.o. \\u2603", "non_payer", 14, 100, NOW, "individual", 7, 2026),
)
raw(
    "INSERT INTO apartment (id, legal_entity_id, data_controller_entity_id, owner_user_id,"
    " internal_name, uby_ws_password_enc, automation_mode, submit_after_hours,"
    " permalink_window_days, permalink_reachback_days, default_purpose,"
    " passport_photo_policy, stay_fee_rate_czk, stay_fee_cadence, active, created_at,"
    " permalink_pin, leon_enabled)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (400, 300, 300, 100, "P\\u0159\\u00edstav \\U0001f3e0", db.encrypt_secret("WS-PASSWORD-SENTINEL"),
     "scheduled", 24, 2, 365, "10", "off", 50, "monthly", 1, NOW, "1234", 0),
)
raw(
    "INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status,"
    " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (450, 400, "ical", "res-uid-\\u0394", "2026-02-10", "2026-02-12", "active", NOW, NOW),
)
db.insert(
    "guest",
    {
        "id": 480,
        "reservation_id": 450,
        "surname": "\\u017dlu\\u0165ou\\u010dk\\u00fd",
        "first_name": "K\\u016f\\u0148",
        "nationality": "CZE",
        "doc_number": "PASSPORT-SENTINEL-\\u0394",
        "birth_date": "1990-01-02",
        "created_at": NOW,
        "updated_at": NOW,
    },
)
db.insert(
    "submission",
    {
        "id": 490,
        "apartment_id": 400,
        "created_at": NOW,
        "mode": "auto",
        "state": "done",
        "request_xml": "<request>?%\\u0394</request>",
    },
)
raw(
    "INSERT INTO stay_fee_filing (id, apartment_id, period_key, version, cadence, rate_czk,"
    " liable_days, exempt_days, total_due_czk, total_collected_czk, created_at,"
    " pdf_enc, csv_enc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (520, 400, "2026-01", 1, "monthly", 50, 10, 0, 500, 500, NOW, BIN, BIN + b"csv"),
)
raw(
    "INSERT INTO invoice_sequence (legal_entity_id, year, last_no) VALUES (?, ?, ?)",
    (300, 2026, 7),
)
raw(
    "INSERT INTO invoice (id, legal_entity_id, apartment_id, owner_user_id, kind, seq_year,"
    " seq_no, number, vs, lang, currency, vat_status, issue_date, seller_name, seller_seat,"
    " buyer_name, total_haler, created_at, pdf_blob)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (500, 300, 400, 100, "invoice", 2026, 7, "2026-0007", "20260007", "cs", "CZK",
     "non_payer", "2026-02-03", "\\u017dofie s.r.o. \\u2603", "Praha", "K\\u016f\\u0148",
     123450, NOW, BIN),
)
raw(
    "INSERT INTO invoice_item (id, invoice_id, position, kind, description, quantity, unit,"
    " gross_haler) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (600, 500, 1, "accommodation", "Pobyt \\U0001f6cf", 1, "noc", 123450),
)
raw(
    "INSERT INTO codelist (kind, code, text_cs, text_en, extra, fetched_at)"
    " VALUES (?, ?, ?, ?, ?, ?)",
    ("Staty", "CZE", "\\u010cesko \\u2603", None, None, NOW),
)
raw(
    "INSERT INTO rate_limit_event (id, scope, key, at) VALUES (?, ?, ?, ?)",
    (700, "transfer", "synthetic-\\u0394", 1700000000.125),
)
raw(
    "INSERT INTO audit (id, at, actor, action, detail, owner_user_id, actor_user_id)"
    " VALUES (?, ?, ?, ?, ?, ?, ?)",
    (710, NOW, "host", "transfer.synthetic", None, 100, 100),
)
raw(
    "INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at,"
    " method, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (720, 100, "terms", "1", NOW, "clickwrap", None, "pytest/\\u0394"),
)
raw(
    "INSERT INTO billing_month_snapshot (owner_user_id, month, status, created_at)"
    " VALUES (?, ?, ?, ?)",
    (100, "2026-01", "paid", NOW),
)

conn = db.connect()
try:
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchone() is None
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert len(tables) == 67, len(tables)
finally:
    conn.close()
'''


def _source_tables_and_counts(source: Path) -> tuple[set[str], dict[str, int]]:
    conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
        counts = {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
    finally:
        conn.close()
    return tables, counts


def _table_columns(connection, table: str) -> list[str]:
    rows = connection.execute_native(
        "SELECT column_name AS name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    return [row["name"] for row in rows]


def _select_full_row(connection, table: str, where: str, params: tuple):
    columns = _table_columns(connection, table)
    quoted = ", ".join(f'"{column}"' for column in columns)
    row = connection.execute(
        f'SELECT {quoted} FROM "{table}" WHERE {where}', params
    ).fetchone()
    assert row is not None, f"missing fixture row in {table}"
    return columns, tuple(row)


def _insert_full_row(connection, table: str, columns: list[str], values: tuple) -> None:
    quoted = ", ".join(f'"{column}"' for column in columns)
    marks = ", ".join("?" for _ in columns)
    connection.execute(f'INSERT INTO "{table}" ({quoted}) VALUES ({marks})', list(values))


@pytest.fixture(scope="module")
def transfer_workspace(tmp_path_factory, pg_runtime):
    """A synthetic all-table SQLite snapshot copied into a reset PostgreSQL target."""
    root = tmp_path_factory.mktemp("pg-transfer")
    source = root / "source.sqlite"
    sqlite_data = root / "sqlite-data"
    sqlite_data.mkdir()
    built = subprocess.run(
        [sys.executable, "-c", _SNAPSHOT_BUILDER],
        cwd=str(PROJECT_DIR),
        env=_sqlite_env(source, sqlite_data),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert built.returncode == 0, built.stderr[-2000:]
    db.close_connections()
    _reset_public_schema()
    assert _public_relation_count() == 0
    report = root / "copy-report.json"
    copy = _run_transfer(source, report)
    assert copy.returncode == 0, copy.stderr[-2000:]
    assert "copied-and-verified OK: tables=67" in copy.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    return {
        "root": root,
        "source": source,
        "report": report,
        "payload": payload,
        "copy_run": copy,
    }


def test_transfer_copies_and_verifies_every_table(transfer_workspace):
    payload = transfer_workspace["payload"]
    tables, counts = _source_tables_and_counts(transfer_workspace["source"])
    assert payload["report_version"] == 1
    assert payload["mode"] == "copied-and-verified"
    assert payload["table_count"] == 67
    assert set(payload["tables"]) == tables
    assert set(tables) == set(db._expected_sqlite_columns())
    assert all(entry["match"] for entry in payload["tables"].values())
    for table, entry in payload["tables"].items():
        assert set(entry) == {
            "rows",
            "source_sha256",
            "target_rows",
            "target_sha256",
            "match",
        }
        assert entry["rows"] == counts[table]
        assert entry["target_rows"] == counts[table]
        assert entry["source_sha256"] == entry["target_sha256"]
    # The sentinel-bearing tables carry rows; the rest of the schema is copied too.
    assert payload["tables"]["user_account"]["rows"] == 2
    assert payload["tables"]["guest"]["rows"] == 1
    assert payload["tables"]["submission"]["rows"] == 1
    assert payload["tables"]["invoice"]["rows"] == 1
    assert payload["tables"]["invoice_item"]["rows"] == 1
    assert payload["tables"]["stay_fee_filing"]["rows"] == 1
    assert payload["tables"]["rate_limit_event"]["rows"] == 1
    assert payload["tables"]["schema_migrations"]["rows"] == 33
    assert sum(1 for entry in payload["tables"].values() if entry["rows"] == 0) >= 40


def test_transfer_report_contains_no_raw_values_or_secrets(transfer_workspace):
    text = transfer_workspace["report"].read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_IN_REPORT:
        assert forbidden not in text, f"report leaked {forbidden!r}"
    combined = transfer_workspace["copy_run"].stdout + transfer_workspace["copy_run"].stderr
    assert str(transfer_workspace["source"]) not in combined
    assert "postgresql://" not in combined
    assert transfer_workspace["payload"]["source_identity"] == {
        "path_name": "source.sqlite",
        "schema_version": 33,
    }
    assert transfer_workspace["payload"]["target_database"] == TARGET["database"]


def test_transfer_verify_only_reconciles_typed_hashes(transfer_workspace):
    report = transfer_workspace["root"] / "verify-report.json"
    result = _run_transfer(transfer_workspace["source"], report, verify_only=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "verify-only OK: tables=67" in result.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    copy_payload = transfer_workspace["payload"]
    assert payload["mode"] == "verify-only"
    assert payload["table_count"] == 67
    assert all(entry["match"] for entry in payload["tables"].values())
    for table, entry in payload["tables"].items():
        assert entry["source_sha256"] == copy_payload["tables"][table]["source_sha256"]
        assert entry["target_sha256"] == copy_payload["tables"][table]["source_sha256"]
    for forbidden in FORBIDDEN_IN_REPORT:
        assert forbidden not in report.read_text(encoding="utf-8")


def test_transfer_digest_order_is_null_stable_across_backends(pg_runtime):
    """The transfer's typed digest is deterministic despite NULL ordering.

    ``sqlite_to_postgres.table_digest`` hashes rows read with ``ORDER BY`` every
    column on the source and on the target. SQLite orders NULLs FIRST on ASC
    while PostgreSQL orders them LAST, so a nullable leading column would make
    the two machines hash the same rows in a different order. The frozen schema
    avoids that: this test proves every table's primary key is a leading,
    NOT NULL prefix of its column order, so distinct rows are always compared on
    a unique key before any nullable tie-breaker. Application SQL is unchanged.
    """
    null_order_sqlite = [
        row[0]
        for row in sqlite3.connect(":memory:").execute(
            "SELECT 1 AS v UNION ALL SELECT NULL ORDER BY v"
        )
    ]
    null_order_postgres = [
        row[0] for row in db.query("SELECT * FROM (VALUES (1), (NULL)) AS t(v) ORDER BY v")
    ]
    assert null_order_sqlite == [None, 1]
    assert null_order_postgres == [1, None]
    assert null_order_sqlite != null_order_postgres, (
        "backend NULL placement still differs; the schema prefix invariant is load-bearing"
    )

    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(db.SCHEMA)
        for table, column, declaration in db.ADDED_COLUMNS:
            names = {
                row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            if column not in names:
                connection.execute(
                    f'ALTER TABLE "{table}" ADD COLUMN {column} {declaration}'
                )
        connection.executescript(db._MIGRATIONS_TABLE)
        for _version, _name, path in db.migration_files():
            connection.executescript(path.read_text(encoding="utf-8"))
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        assert len(tables) == 67
        for table in tables:
            info = list(connection.execute(f'PRAGMA table_info("{table}")'))
            ordered = [row[1] for row in info]
            key = [row[1] for row in info if row[5]]
            assert key, f"{table} has no primary key to order by"
            assert ordered[: len(key)] == key, (
                f"{table}: primary key {key} is not the leading ORDER BY prefix "
                f"{ordered[: len(key)]}"
            )
            assert all(row[3] or row[5] for row in info[: len(key)]), (
                f"{table}: a nullable column sits in the leading key prefix"
            )
    finally:
        connection.close()


def test_transfer_restores_sequences_above_imported_ids(transfer_workspace):
    maximum = db.query_one("SELECT MAX(id) AS m FROM user_account")["m"]
    assert maximum == 101
    new_id = db.insert(
        "user_account",
        {
            "username": "post-transfer-sequence-probe",
            "password_hash": "x",
            "created_at": db.utcnow(),
        },
    )
    try:
        assert new_id > maximum
        assert (
            db.query_one("SELECT username FROM user_account WHERE id = ?", (new_id,))[
                "username"
            ]
            == "post-transfer-sequence-probe"
        )
    finally:
        db.execute("DELETE FROM user_account WHERE id = ?", (new_id,))
    # Empty-table semantics: a table with no imported rows starts its identity at 1.
    alert_id = db.insert(
        "alert",
        {
            "level": "info",
            "kind": "sequence-probe",
            "message": "m",
            "created_at": db.utcnow(),
            "dedupe_key": "sequence-probe",
        },
    )
    try:
        assert alert_id == 1
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))


def test_transfer_refuses_a_non_empty_destination(transfer_workspace):
    report = transfer_workspace["root"] / "refused-copy.json"
    result = _run_transfer(transfer_workspace["source"], report)
    assert result.returncode == 1
    assert "destination is not an empty isolated target" in result.stderr
    assert not report.exists()
    combined = result.stdout + result.stderr
    assert "PASSPORT-SENTINEL" not in combined
    assert "postgresql://" not in combined
    # The populated target is untouched and still reconciles.
    verify = _run_transfer(
        transfer_workspace["source"],
        transfer_workspace["root"] / "after-refusal-verify.json",
        verify_only=True,
    )
    assert verify.returncode == 0, verify.stderr[-1000:]


def test_verify_only_detects_a_tampered_value_with_matching_row_counts(transfer_workspace):
    root = transfer_workspace["root"]
    report = root / "verify-before-tamper.json"
    assert _run_transfer(transfer_workspace["source"], report, verify_only=True).returncode == 0
    before_bytes = report.read_bytes()

    connection = db.connect()
    try:
        connection.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            ("tampered-value", "transfer.unicode"),
        )
    finally:
        connection.close()
    try:
        _, counts = _source_tables_and_counts(transfer_workspace["source"])
        target_count = db.query_one("SELECT COUNT(*) AS n FROM settings")["n"]
        assert target_count == counts["settings"], "row counts still agree; only a value changed"
        tampered = _run_transfer(transfer_workspace["source"], report, verify_only=True)
        assert tampered.returncode == 1
        assert "typed hash mismatch at settings" in tampered.stderr
        assert report.read_bytes() == before_bytes, (
            "a failed verification must keep the prior successful report"
        )
    finally:
        repair = db.connect()
        try:
            repair.execute(
                "UPDATE settings SET value = ? WHERE key = ?",
                (UNICODE_VALUE, "transfer.unicode"),
            )
        finally:
            repair.close()
    assert _run_transfer(
        transfer_workspace["source"], root / "after-value-repair.json", verify_only=True
    ).returncode == 0


def test_verify_only_detects_a_missing_row(transfer_workspace):
    root = transfer_workspace["root"]
    connection = db.connect()
    try:
        columns, values = _select_full_row(connection, "user_account", "id = ?", (101,))
        connection.execute('DELETE FROM "user_account" WHERE id = ?', (101,))
    finally:
        connection.close()
    try:
        missing = _run_transfer(
            transfer_workspace["source"], root / "missing-row-verify.json", verify_only=True
        )
        assert missing.returncode == 1
        assert "typed hash mismatch at user_account" in missing.stderr
    finally:
        restore = db.connect()
        try:
            _insert_full_row(restore, "user_account", columns, values)
        finally:
            restore.close()
    assert _run_transfer(
        transfer_workspace["source"], root / "after-row-repair.json", verify_only=True
    ).returncode == 0


def test_transfer_refuses_source_schema_drift(transfer_workspace):
    root = transfer_workspace["root"]
    drifted = root / "drifted-source.sqlite"
    shutil.copy2(transfer_workspace["source"], drifted)
    connection = sqlite3.connect(drifted)
    try:
        connection.execute("ALTER TABLE settings ADD COLUMN drift_column TEXT")
        connection.commit()
    finally:
        connection.close()
    report = root / "drift-report.json"
    result = _run_transfer(drifted, report)
    assert result.returncode == 1
    assert "source schema drift at settings (extra: ['drift_column'], missing: [])" in result.stderr
    assert not report.exists()
    # The populated target is untouched.
    verify = _run_transfer(
        transfer_workspace["source"], root / "after-drift-verify.json", verify_only=True
    )
    assert verify.returncode == 0, verify.stderr[-1000:]


def test_transfer_skips_litestream_tables(transfer_workspace):
    root = transfer_workspace["root"]
    source = root / "litestream-source.sqlite"
    shutil.copy2(transfer_workspace["source"], source)
    connection = sqlite3.connect(source)
    try:
        connection.execute("CREATE TABLE _litestream_seq (id INTEGER PRIMARY KEY, seq INTEGER)")
        connection.execute("INSERT INTO _litestream_seq (id, seq) VALUES (1, 42)")
        connection.execute("CREATE TABLE _litestream_lock (id INTEGER)")
        connection.commit()
    finally:
        connection.close()
    _reset_public_schema()
    report = root / "litestream-report.json"
    copy = _run_transfer(source, report)
    assert copy.returncode == 0, copy.stderr[-2000:]
    assert "copied-and-verified OK: tables=67" in copy.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert not [name for name in payload["tables"] if name.startswith("_litestream")]
    with _psycopg_connect(_PG_URL) as conn:
        row = conn.execute("SELECT to_regclass('public._litestream_seq')").fetchone()
    assert row[0] is None


def test_transfer_accepts_a_different_column_order(transfer_workspace):
    root = transfer_workspace["root"]
    source = root / "column-order-source.sqlite"
    shutil.copy2(transfer_workspace["source"], source)
    connection = sqlite3.connect(source)
    try:
        saved = connection.execute("SELECT id, guest_message FROM apartment").fetchall()
        connection.execute("ALTER TABLE apartment DROP COLUMN guest_message")
        connection.execute("ALTER TABLE apartment ADD COLUMN guest_message TEXT")
        connection.executemany(
            "UPDATE apartment SET guest_message = ? WHERE id = ?",
            [(message, row_id) for row_id, message in saved],
        )
        connection.commit()
        names = [row[1] for row in connection.execute("PRAGMA table_info(apartment)")]
    finally:
        connection.close()
    assert names[-1] == "guest_message"
    _reset_public_schema()
    report = root / "column-order-report.json"
    copy = _run_transfer(source, report)
    assert copy.returncode == 0, copy.stderr[-2000:]
    assert "copied-and-verified OK" in copy.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["tables"]["apartment"]["match"] is True


def test_transfer_names_an_unknown_table(transfer_workspace):
    root = transfer_workspace["root"]
    unknown = root / "unknown-source.sqlite"
    shutil.copy2(transfer_workspace["source"], unknown)
    connection = sqlite3.connect(unknown)
    try:
        connection.execute("CREATE TABLE legacy_stuff (id INTEGER)")
        connection.commit()
    finally:
        connection.close()
    report = root / "unknown-report.json"
    result = _run_transfer(unknown, report)
    assert result.returncode == 1
    assert "extra: ['legacy_stuff']" in result.stderr
    assert not report.exists()


def test_transfer_refuses_an_unsupported_source_schema_version(transfer_workspace):
    root = transfer_workspace["root"]
    stale = root / "stale-source.sqlite"
    shutil.copy2(transfer_workspace["source"], stale)
    connection = sqlite3.connect(stale)
    try:
        connection.execute("DELETE FROM schema_migrations WHERE version = 33")
        connection.commit()
    finally:
        connection.close()
    result = _run_transfer(stale, root / "stale-report.json")
    assert result.returncode == 1
    assert "source schema version is unsupported" in result.stderr
    verify = _run_transfer(
        transfer_workspace["source"], root / "after-stale-verify.json", verify_only=True
    )
    assert verify.returncode == 0, verify.stderr[-1000:]


def test_constraint_violation_rolls_back_and_target_is_reusable(transfer_workspace):
    root = transfer_workspace["root"]
    duplicate = root / "duplicate-email-source.sqlite"
    shutil.copy2(transfer_workspace["source"], duplicate)
    connection = sqlite3.connect(duplicate)
    try:
        connection.execute("DROP INDEX idx_user_account_email")
        connection.execute(
            "INSERT INTO user_account (id, username, password_hash, role, active,"
            " must_change_password, session_version, created_at, email, totp_enabled)"
            " VALUES (102, 'dup-email-user', 'x', 'host', 1, 0, 1,"
            " '2026-02-03T04:05:06+00:00', 'transfer-a@example.test', 0)"
        )
        connection.commit()
    finally:
        connection.close()

    # The destination is reset so the violation happens inside the copy transaction.
    db.close_connections()
    _reset_public_schema()
    assert _public_relation_count() == 0
    result = _run_transfer(duplicate, root / "constraint-report.json")
    assert result.returncode == 1
    # Sanitised target-failure text: operation/table plus category and SQLSTATE,
    # never the offending value psycopg puts in its DETAIL.
    assert "copying table user_account" in result.stderr
    assert "unique constraint violation (sqlstate 23505)" in result.stderr
    for leaked in (
        "transfer-a@example.test",
        "dup-email-user",
        "Key (email)",
        "DETAIL",
        "duplicate key value violates unique constraint",
        "postgresql://",
        "ubyhost@127.0.0.1",
        "PASSPORT-SENTINEL",
    ):
        assert leaked not in result.stderr, f"transfer stderr leaked {leaked!r}"
    assert not (root / "constraint-report.json").exists()
    # A failed transfer rolls back its schema and rows and stays reusable.
    assert _public_relation_count() == 0
    retry = _run_transfer(transfer_workspace["source"], root / "retry-report.json")
    assert retry.returncode == 0, retry.stderr[-2000:]
    verify = _run_transfer(
        transfer_workspace["source"], root / "retry-verify.json", verify_only=True
    )
    assert verify.returncode == 0, verify.stderr[-1000:]
    # The successful report published after recovery is value-free too.
    success_text = (root / "retry-report.json").read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_IN_REPORT:
        assert forbidden not in success_text, f"success report leaked {forbidden!r}"
    assert "transfer-a@example.test" not in success_text


def test_transfer_refuses_report_path_collisions(transfer_workspace):
    source = transfer_workspace["source"]
    before_bytes = source.read_bytes()
    aliased = _run_transfer(source, source)
    assert aliased.returncode == 1
    # A path that resolves to the source is refused either way.
    assert "report path" in aliased.stderr and "SQLite source" in aliased.stderr
    sidecar = _run_transfer(source, Path(str(source) + "-wal"))
    assert sidecar.returncode == 1
    assert "conflicts with the SQLite source or sidecar" in sidecar.stderr
    assert source.read_bytes() == before_bytes, "the transfer must never mutate its source"


# --- i. database configuration contract (no server) ------------------------

_CONFIG_PROBE = """
import json
from app import config
print(json.dumps({
    "backend": config.DB_BACKEND,
    "target": config._DATABASE_TARGET,
    "fingerprint": config._database_target_fingerprint(config.DATABASE_URL),
    "label": config.database_label(),
}))
"""

_SQLITE_PROBE = """
import json
from app import config
print(json.dumps({
    "backend": config.DB_BACKEND,
    "url": config.DATABASE_URL,
    "path": str(config.DB_PATH),
}))
"""


def _probe_with_url(url: str, code: str = _CONFIG_PROBE) -> subprocess.CompletedProcess:
    env = _base_env()
    env["UBYHOST_DATABASE_URL"] = url
    return _run_python(code, env)


def test_tcp_url_contract_is_unchanged_and_fingerprint_excludes_credentials():
    database = TARGET["database"]
    parsed = _parse_target(_PG_URL)
    port = parsed["port"] or 5432
    first = _probe_with_url(f"postgresql://ubyhost:supersecretpw@127.0.0.1:{port}/{database}?sslmode=verify-full")
    assert first.returncode == 0, first.stderr[-1000:]
    payload = json.loads(first.stdout)
    assert payload["backend"] == "postgresql"
    assert payload["label"] == "postgresql"
    assert payload["target"] == {
        "scheme": "postgresql",
        "hostname": "127.0.0.1",
        "socket_dir": None,
        "port": port,
        "database": database,
        "schema": "public",
    }
    assert "supersecretpw" not in first.stdout + first.stderr

    second = _probe_with_url(f"postgresql://someone:anotherpw@127.0.0.1:{port}/{database}?sslmode=verify-full")
    assert second.returncode == 0
    other = json.loads(second.stdout)
    assert other["fingerprint"] == payload["fingerprint"], (
        "credentials must not change the database target fingerprint"
    )
    assert other["target"]["hostname"] == "127.0.0.1"


@pytest.mark.parametrize("query", ["", "?sslmode=disable", "?sslmode=prefer"])
def test_remote_tcp_url_without_verified_tls_is_rejected(query):
    result = _probe_with_url(f"postgresql://postgres:x@db.example.com/ubyhost{query}")
    assert result.returncode != 0
    assert "sslmode=verify-full (or require)" in result.stderr


def test_loopback_tcp_url_without_tls_is_accepted():
    result = _probe_with_url("postgresql://postgres:x@localhost:5432/ubyhost_test")
    assert result.returncode == 0, result.stderr[-1000:]


def test_connect_sets_timeouts_and_keeps_url_options(monkeypatch):
    import psycopg

    from app import db_postgres

    seen = {}

    class _Cursor:
        def fetchone(self):
            return ("UTF8",)

    class _Raw:
        def execute(self, *args, **kwargs):
            return _Cursor()

        def close(self):
            pass

    def fake_connect(conninfo, **kwargs):
        seen.update(kwargs)
        return _Raw()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    db_postgres.connect(
        f"postgresql://ubyhost@127.0.0.1:55432/{TARGET['database']}"
        "?sslmode=verify-full&options=-c%20search_path%3Dapp"
    )
    assert seen["connect_timeout"] == 10
    assert seen["options"] == "-c search_path=app -c statement_timeout=60000"


def test_socket_url_forms_are_accepted_and_connect():
    database = TARGET["database"]
    for url in (
        f"postgresql://ubyhost@/{database}?host={SOCKET_DIR}&port={SOCKET_PORT}",
        f"postgresql://ubyhost@/{database}?host=%2Ftmp%2Fpgsock18&port={SOCKET_PORT}",
    ):
        target = config._postgres_target(url)
        assert target["socket_dir"] == SOCKET_DIR
        assert target["port"] == SOCKET_PORT
    if config._postgres_target(_PG_URL)["socket_dir"]:
        row = db.query_one("SELECT current_setting('server_version_num') AS version")
        assert int(row["version"]) >= 160000


def test_socket_target_fingerprint_includes_the_socket_directory_only():
    database = TARGET["database"]
    first = _probe_with_url(
        f"postgresql://ubyhost@/{database}?host={SOCKET_DIR}&port={SOCKET_PORT}"
    )
    second = _probe_with_url(
        f"postgresql://ubyhost@/{database}?host=/tmp/another-socket-dir&port={SOCKET_PORT}"
    )
    credentialed = _probe_with_url(
        f"postgresql://someone:anotherpw@/{database}?host={SOCKET_DIR}&port={SOCKET_PORT}"
    )
    for result in (first, second, credentialed):
        assert result.returncode == 0, result.stderr[-1000:]
    left = json.loads(first.stdout)
    right = json.loads(second.stdout)
    with_credentials = json.loads(credentialed.stdout)
    assert left["target"]["socket_dir"] == SOCKET_DIR
    assert left["fingerprint"] != right["fingerprint"], "socket directory is part of identity"
    assert left["fingerprint"] == with_credentials["fingerprint"]
    assert "anotherpw" not in credentialed.stdout + credentialed.stderr


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("postgresql://ubyhost@127.0.0.1:55432", "must name exactly one database"),
        ("postgresql://ubyhost@/ubyhost_test?host=relative/sock", "absolute socket directory"),
        ("postgresql://ubyhost@/ubyhost_test?host=&port=55432", "absolute socket directory"),
        (
            "postgresql://ubyhost@127.0.0.1:55432/ubyhost_test?host=/tmp/pgsock18",
            "both a hostname and a host parameter",
        ),
        (
            "postgresql://ubyhost@127.0.0.1:55432/ubyhost_test?port=5433",
            "contradictory port settings",
        ),
        (
            "postgresql://ubyhost@127.0.0.1:55432/ubyhost_test?host=/tmp/a&host=/tmp/b",
            "duplicate query parameter",
        ),
        ("postgresql://ubyhost@/ubyhost_test?host=/tmp/pgsock18&port=abc", "port parameter must be numeric"),
        ("postgresql://ubyhost@/ubyhost_test?host=/tmp/pgsock18&port=70000", "port parameter must be numeric"),
        ("postgresql://ubyhost@127.0.0.1:55432/ubyhost_test#fragment", "must not contain a fragment"),
        ("mysql://ubyhost@127.0.0.1:55432/ubyhost_test", "postgres or postgresql scheme"),
        ("postgresql://127.0.0.1:notaport/ubyhost_test", "valid PostgreSQL URL with a database name"),
    ],
)
def test_malformed_database_urls_are_rejected(url, message):
    result = _probe_with_url(url)
    assert result.returncode != 0
    assert message in result.stderr
    combined = result.stdout + result.stderr
    assert "supersecret" not in combined
    assert "postgresql://" not in combined or "UBYHOST_DATABASE_URL" in combined


def test_empty_url_and_dual_database_settings_are_rejected():
    env = _base_env()
    env["UBYHOST_DATABASE_URL"] = ""
    empty = _run_python(_CONFIG_PROBE, env)
    assert empty.returncode != 0
    assert "UBYHOST_DATABASE_URL must not be empty" in empty.stderr

    env = _base_env()
    env["UBYHOST_DB"] = "/tmp/ubyhost-sqlite-test.db"
    env["UBYHOST_DATABASE_URL"] = _PG_URL
    dual = _run_python(_CONFIG_PROBE, env)
    assert dual.returncode != 0
    assert "Set only one of UBYHOST_DB or UBYHOST_DATABASE_URL" in dual.stderr
    combined = dual.stdout + dual.stderr
    assert "postgresql://" not in combined


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ubyhost:leak-check-pw@127.0.0.1:55432/ubyhost_test?port=5433",
        "postgresql://ubyhost:leak-check-pw@127.0.0.1:55432/ubyhost_test?host=/tmp/x",
        "postgresql://ubyhost:leak-check-pw@127.0.0.1:55432/ubyhost_test#fragment",
        "postgresql://ubyhost:leak-check-pw@/ubyhost_test?host=relative",
    ],
)
def test_configuration_errors_never_echo_credentials(url):
    result = _probe_with_url(url)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "leak-check-pw" not in combined
    assert "postgresql://ubyhost" not in combined


def test_sqlite_default_contract_is_unchanged_without_a_database_url(tmp_path):
    env = _base_env()
    env["UBYHOST_DB"] = str(tmp_path / "sqlite-contract.db")
    result = _run_python(_SQLITE_PROBE, env)
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["backend"] == "sqlite"
    assert payload["url"] is None
    assert payload["path"].endswith("sqlite-contract.db")
