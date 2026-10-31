#!/usr/bin/env python3
"""Copy a read-only SQLite snapshot into an isolated empty PostgreSQL database."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402
from app import db_postgres  # noqa: E402

REPORT_VERSION = 1

# Enough SQLSTATE context for an operator without echoing a psycopg message,
# whose DETAIL may contain offending row values (for example a guest e-mail).
_SQLSTATE_CATEGORIES = {
    "23502": "not-null constraint violation",
    "23503": "foreign-key constraint violation",
    "23505": "unique constraint violation",
    "23514": "check constraint violation",
}
_SQLSTATE_CLASSES = {
    "08": "connection failure",
    "22": "invalid data value",
    "23": "integrity constraint violation",
    "40": "transaction conflict",
    "42": "SQL syntax or access rule violation",
    "55": "object or lock not available",
}


def _target_failure(exc: BaseException, table: str | None = None) -> RuntimeError:
    """A safe message: operation, table and SQLSTATE only.

    psycopg embeds offending values in ``str(exc)`` (``DETAIL: Key (email)=...``),
    so target-write failures are never surfaced verbatim.
    """
    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    sqlstate = str(sqlstate) if sqlstate else ""
    category = _SQLSTATE_CATEGORIES.get(sqlstate)
    if category is None:
        category = _SQLSTATE_CLASSES.get(sqlstate[:2], "database error") if sqlstate else "database error"
    where = f"copying table {table}" if table else "writing the PostgreSQL target"
    suffix = f" (sqlstate {sqlstate})" if sqlstate else ""
    return RuntimeError(f"{where} failed: {category}{suffix}")


@contextlib.contextmanager
def _sanitized_target_errors(table: str | None = None):
    """Re-raise target failures without psycopg messages or exception chaining."""
    try:
        yield
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise _target_failure(exc, table) from None


def _failure_text(exc: BaseException) -> str:
    """A stderr-safe error text even if a psycopg error escaped a boundary."""
    if getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None):
        return str(_target_failure(exc))
    return str(exc)


def _source_protected_paths(path: Path) -> set[Path]:
    resolved = path.expanduser().resolve(strict=False)
    return {p.resolve(strict=False) for base in (path.expanduser(), resolved)
            for p in (base, *(Path(f"{base}{suffix}") for suffix in ("-wal", "-shm", "-journal")))}


def validate_report_path(report: Path, source: Path) -> Path:
    target = report.expanduser().resolve(strict=False)
    for protected in _source_protected_paths(source):
        if target == protected:
            raise ValueError("report path conflicts with the SQLite source or sidecar")
        if target.exists() and source.exists() and os.path.samefile(target, source):
            raise ValueError("report path aliases the SQLite source")
    return target


def snapshot_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ValueError("source snapshot must be an existing SQLite file")
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    conn.execute("SELECT name FROM sqlite_master ORDER BY name").fetchall()  # pins snapshot
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("source SQLite integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("source SQLite foreign-key check failed")
    return conn


def app_tables(source: sqlite3.Connection) -> list[str]:
    return [r[0] for r in source.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def typed_value(value: Any) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        return b"I" + str(value).encode("ascii") + b";"
    if isinstance(value, float):
        return b"F" + value.hex().encode("ascii") + b";"
    if isinstance(value, str):
        return b"T" + value.encode("utf-8") + b"\0"
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return b"B" + str(len(raw)).encode("ascii") + b":" + raw
    raise TypeError(f"unsupported SQLite value type: {type(value).__name__}")


def table_digest(conn, table: str, columns: list[str], *, postgres: bool) -> tuple[int, str]:
    quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
    order = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
    sql = f'SELECT {quoted} FROM "{table}" ORDER BY {order}'
    rows = conn.execute_native(sql).fetchall() if postgres else conn.execute(sql).fetchall()
    digest = hashlib.sha256()
    for row in rows:
        digest.update(b"R")
        for value in row:
            item = typed_value(value)
            digest.update(len(item).to_bytes(8, "big"))
            digest.update(item)
    return len(rows), digest.hexdigest()


def schema_version(source: sqlite3.Connection) -> int:
    names = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "schema_migrations" not in names:
        raise ValueError("source schema has no migration history")
    rows = source.execute("SELECT version FROM schema_migrations").fetchall()
    return max((int(r[0]) for r in rows), default=0)


def _table_columns(source: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in source.execute(f'PRAGMA table_info("{table}")')]


def _postgres_empty(conn) -> bool:
    return not conn.execute_native(
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=current_schema() LIMIT 1"
    ).fetchone()


def _preflight_values(source: sqlite3.Connection, table: str) -> None:
    for info in source.execute(f'PRAGMA table_info("{table}")'):
        name, decl = info[1], info[2]
        kind = (decl or "").upper().split("(", 1)[0].strip()
        # SQLite's dynamic typing is retained only where PostgreSQL can accept
        # the exact stored representation. Never stringify/coerce bad values.
        expected = {"INTEGER": "integer", "REAL": ("integer", "real"), "TEXT": "text", "BLOB": "blob"}.get(kind)
        if expected is None:
            continue
        allowed = (expected,) if isinstance(expected, str) else expected
        for (value,) in source.execute(
            f'SELECT "{name}" FROM "{table}" WHERE "{name}" IS NOT NULL'
        ):
            actual = ("integer" if isinstance(value, int) else "real" if isinstance(value, float)
                      else "text" if isinstance(value, str) else "blob" if isinstance(value, bytes)
                      else "unsupported")
            if actual not in allowed:
                raise ValueError(f"source type drift at {table}.{name} ({actual})")


def _validate_pg_values(source: sqlite3.Connection, table: str) -> None:
    # Narrow source SQLite values before sending them to strict PostgreSQL types.
    _preflight_values(source, table)


def _write_report(payload: dict[str, Any], path: Path, source: Path) -> None:
    path = validate_report_path(path, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp = Path(name)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        replaced = True
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if not replaced:
            temp.unlink(missing_ok=True)


def _expected_db(name: str) -> None:
    if config.DB_BACKEND != "postgresql":
        raise RuntimeError("Set UBYHOST_DATABASE_URL to select PostgreSQL.")
    if db.current_database_name() != name:
        raise RuntimeError("Connected database does not match --expect-database.")
    if db.current_postgres_schema_name() != "public":
        raise RuntimeError("PostgreSQL transfer requires the public schema.")
    marker_path = config.DATABASE_AUTHORITY_FILE
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("database") != name or marker.get("schema") != "public":
            raise RuntimeError("PostgreSQL target does not match the durable authority marker.")


def reconcile(source: sqlite3.Connection, target, tables: list[str]) -> dict[str, Any]:
    summary = {}
    for table in tables:
        columns = _table_columns(source, table)
        src_count, src_hash = table_digest(source, table, columns, postgres=False)
        with _sanitized_target_errors(table):
            target_columns = [row["name"] for row in target.execute_native(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                (table,),
            ).fetchall()]
            if columns != target_columns:
                raise ValueError(f"column mismatch at {table}")
            dst_count, dst_hash = table_digest(target, table, columns, postgres=True)
        summary[table] = {"rows": src_count, "source_sha256": src_hash,
                          "target_rows": dst_count, "target_sha256": dst_hash,
                          "match": src_count == dst_count and src_hash == dst_hash}
        if not summary[table]["match"]:
            raise ValueError(f"typed hash mismatch at {table}")
    return summary


def transfer(source_path: Path, report_path: Path, expected_database: str, verify_only: bool) -> dict[str, Any]:
    report_path = validate_report_path(report_path, source_path)
    source = snapshot_connection(source_path)
    target = None
    committed = False
    try:
        actual_version = schema_version(source)
        if actual_version != db.expected_schema_version():
            raise ValueError("source schema version is unsupported")
        tables = app_tables(source)
        expected = db._expected_sqlite_columns()
        if set(tables) != set(expected):
            raise ValueError("source table set differs from the supported application schema")
        for table in tables:
            if _table_columns(source, table) != [c[0] for c in expected[table]]:
                raise ValueError(f"source schema drift at {table}")
            _validate_pg_values(source, table)
        _expected_db(expected_database)
        target = db.connect()
        with _sanitized_target_errors():
            target.acquire_writer_session_lock()
            target.execute("BEGIN IMMEDIATE")
        try:
            if verify_only:
                with _sanitized_target_errors():
                    status = db.postgres_schema_status(target)
                if not status["current"]:
                    raise ValueError("target schema is not current")
            else:
                with _sanitized_target_errors():
                    if not _postgres_empty(target):
                        raise ValueError("destination is not an empty isolated target")
                    db.bootstrap_empty_postgresql_schema(target)
                    # Foreign keys are declared deferrable to support self-links;
                    # application unique constraints remain immediate for ON CONFLICT.
                    target.execute("SET CONSTRAINTS ALL DEFERRED")
                order = db.table_copy_order(source, tables)
                for table in order:
                    columns = _table_columns(source, table)
                    quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
                    marks = ", ".join("?" for _ in columns)
                    sql = f'INSERT INTO "{table}" ({quoted}) VALUES ({marks})'
                    cursor = source.execute(f'SELECT {quoted} FROM "{table}"')
                    with _sanitized_target_errors(table):
                        while True:
                            rows = cursor.fetchmany(500)
                            if not rows:
                                break
                            target.executemany(sql, [tuple(row) for row in rows])
                        db.restore_postgres_sequence(target, table, source)
                with _sanitized_target_errors():
                    db_postgres.install_pg_triggers(target)
                    db.validate_postgres_schema_connection(target)
            reconciliation = reconcile(source, target, tables)
            with _sanitized_target_errors():
                target.execute("COMMIT")
            committed = True
        except BaseException:
            if target.in_transaction:
                target.execute("ROLLBACK")
            raise
        finally:
            try:
                target.release_writer_session_lock()
            except Exception:
                # target.close() releases the session lock too; never replace
                # the transfer error with a raw driver message here.
                pass
        payload = {
            "report_version": REPORT_VERSION,
            "source_identity": {"path_name": source_path.name, "schema_version": actual_version},
            "target_database": expected_database,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "verify-only" if verify_only else "copied-and-verified",
            "table_count": len(tables), "tables": reconciliation,
        }
        try:
            _write_report(payload, report_path, source_path)
        except Exception as exc:
            if committed:
                raise RuntimeError("target transaction committed, but report publication failed; run --verify-only to regenerate reconciliation") from exc
            raise
        return payload
    finally:
        source.close()
        if target is not None:
            target.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expect-database", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = transfer(args.source, args.report, args.expect_database, args.verify_only)
    except RuntimeError as exc:
        text = _failure_text(exc)
        if "committed" in text:
            print(text, file=sys.stderr)
            return 2
        print(f"SQLite to PostgreSQL transfer failed before commit: {text}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"SQLite to PostgreSQL transfer failed before commit: {_failure_text(exc)}",
            file=sys.stderr,
        )
        return 1
    print(f"SQLite to PostgreSQL {payload['mode']} OK: tables={payload['table_count']}, report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
