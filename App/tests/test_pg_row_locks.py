"""Keyed row locks (0466 part b).

PostgreSQL write transactions no longer queue behind one global advisory lock.
A block that reads, decides and writes takes ``db.lock_key(cur, name, id)``
first. These tests prove both halves on PostgreSQL. The SQLite half runs in
every test row and proves ``lock_key`` issues no statement there.
"""
from __future__ import annotations

import sqlite3
import threading
import time

import pytest

# Import first: test_db_postgres copies UBYHOST_TEST_DATABASE_URL into the
# application setting, which app.config reads once at import time.
from test_db_postgres import _PG_URL
from app import config, db

if _PG_URL:
    # Imported only on PostgreSQL: a module-level import of this autouse session
    # fixture would make it set up (and fail) for the SQLite-only test below.
    from test_db_postgres import pg_runtime  # noqa: F401

needs_postgres = pytest.mark.skipif(
    not _PG_URL,
    reason=(
        "PostgreSQL row-lock tests need UBYHOST_DATABASE_URL (or "
        "UBYHOST_TEST_DATABASE_URL) for a disposable target whose database name "
        "contains 'test'; this pytest process runs the SQLite row"
    ),
)


@needs_postgres
def test_writers_on_different_tables_do_not_queue(pg_runtime):
    """(a) No global writer lock: a second writer finishes while the first holds its transaction."""
    holding = threading.Event()
    release = threading.Event()
    key_a = "row-lock-probe-a"
    email_hash = "row-lock-probe-b"

    def first_writer():
        with db.immediate() as cur:
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)", (key_a, "a")
            )
            holding.set()
            release.wait(timeout=20)

    def second_writer(done):
        with db.immediate() as cur:
            cur.execute(
                "INSERT INTO mail_suppression (email_hash, scope, created_at) "
                "VALUES (?, ?, ?)",
                (email_hash, "row-lock-test", "2026-01-01T00:00:00"),
            )
        done.set()

    db.execute("DELETE FROM settings WHERE key = ?", (key_a,))
    db.execute("DELETE FROM mail_suppression WHERE email_hash = ?", (email_hash,))
    first = threading.Thread(target=first_writer)
    done = threading.Event()
    try:
        first.start()
        assert holding.wait(timeout=20)
        second = threading.Thread(target=second_writer, args=(done,))
        second.start()
        second.join(timeout=5)
        finished_while_first_open = done.is_set()
        assert finished_while_first_open, "second writer queued behind the first"
    finally:
        release.set()
        first.join(timeout=20)
        db.execute("DELETE FROM settings WHERE key = ?", (key_a,))
        db.execute("DELETE FROM mail_suppression WHERE email_hash = ?", (email_hash,))


@needs_postgres
def test_lock_key_serialises_same_row_and_not_other_rows(pg_runtime):
    """(b) Same (name, id) waits for the holder; a different id does not wait."""
    holding = threading.Event()
    waited = {}

    def holder():
        with db.immediate() as cur:
            db.lock_key(cur, "guest", 1)
            holding.set()
            time.sleep(1.0)

    def same_row_waiter():
        assert holding.wait(timeout=20)
        started = time.monotonic()
        with db.immediate() as cur:
            db.lock_key(cur, "guest", 1)
        waited["same"] = time.monotonic() - started

    first = threading.Thread(target=holder)
    second = threading.Thread(target=same_row_waiter)
    try:
        first.start()
        assert holding.wait(timeout=20)
        second.start()
        started = time.monotonic()
        with db.immediate() as cur:
            db.lock_key(cur, "guest", 2)
        other_row = time.monotonic() - started
        assert other_row < 0.5, f"a different id waited {other_row:.2f}s"
    finally:
        second.join(timeout=20)
        first.join(timeout=20)
    assert waited["same"] >= 0.9, f"same id did not wait ({waited['same']:.2f}s)"


def test_lock_key_is_a_no_op_on_sqlite(monkeypatch):
    """(c) SQLite: lock_key executes no statement (BEGIN IMMEDIATE already serialises)."""
    monkeypatch.setattr(config, "DB_BACKEND", "sqlite", raising=False)
    conn = sqlite3.connect(":memory:")
    traced = []
    conn.set_trace_callback(traced.append)
    cur = conn.cursor()
    db.lock_key(cur, "guest", 1)
    db.lock_key(cur, "guest", 2)
    assert traced == []
    conn.close()
