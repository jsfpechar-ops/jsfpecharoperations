from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import stat
import sqlite3

import pytest

from app import config, db


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    db.close_connections()
    path = tmp_path / "readonly.sqlite"
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    db.execute("CREATE TABLE readonly_probe (value INTEGER NOT NULL)")
    db.execute("INSERT INTO readonly_probe (value) VALUES (1)")
    db.execute("PRAGMA journal_mode = DELETE")
    db.close_connections()
    yield path
    db.close_connections()


def test_readonly_cursor_is_read_only_without_open_side_effects(
    isolated_database, monkeypatch
):
    path = isolated_database
    before_bytes = path.read_bytes()
    before_mode = stat.S_IMODE(path.stat().st_mode)

    def forbidden(*args, **kwargs):
        pytest.fail("read-only cursor must not use init_db or _open")

    monkeypatch.setattr(db, "init_db", forbidden)
    monkeypatch.setattr(db, "_open", forbidden)

    with db.readonly_cursor() as cur:
        assert cur.execute("SELECT value FROM readonly_probe").fetchone()["value"] == 1
        assert cur.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            cur.execute("INSERT INTO readonly_probe (value) VALUES (2)")

    assert path.read_bytes() == before_bytes
    assert stat.S_IMODE(path.stat().st_mode) == before_mode


def test_readonly_cursor_keeps_one_wal_snapshot(isolated_database):
    db.execute("PRAGMA journal_mode = WAL")
    db.close_connections()
    with db.readonly_cursor() as cur:
        assert cur.execute("SELECT value FROM readonly_probe").fetchone()["value"] == 1
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                db.execute, "UPDATE readonly_probe SET value = 2 WHERE value = 1"
            )
            assert future.result(timeout=5) == 1
        assert cur.execute("SELECT value FROM readonly_probe").fetchone()["value"] == 1

    assert db.query_one("SELECT value FROM readonly_probe")["value"] == 2
