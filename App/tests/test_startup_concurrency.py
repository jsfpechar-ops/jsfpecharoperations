"""Start-up work must be safe when several processes boot at once (WP06).

Production runs two uvicorn workers and a scheduler worker on one volume. All
three call ``db.init_db()`` (and the web workers create the first
administrator) at the same moment after a deploy. Without a cross-process lock
two of them can both see a column missing and both ``ALTER TABLE``, or both
insert the one-off settings row, and the loser crashes on start.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from app import config, db

APP_DIR = Path(__file__).resolve().parent.parent

_BOOT = r"""
import os, sys, time
start = float(sys.argv[1])
while time.time() < start:
    pass
from app import db
db.init_db()
if os.environ.get("BOOT_ADMIN") == "1":
    from app import auth, main
    with db.startup_lock():
        auth.ensure_bootstrap_admin()
        main.rotate_weak_permalinks()
print("ok")
"""


def _env(tmp_path: Path, **extra: str) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "UBYHOST_DATA_DIR": str(tmp_path),
            "UBYHOST_DB": str(tmp_path / "race.db"),
            "UBYHOST_SECRET_KEY": "test-secret-key-not-for-real-use",
        }
    )
    env.update(extra)
    return env


def _boot_many(tmp_path: Path, count: int, **extra: str) -> list:
    start = time.time() + 1.5
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _BOOT, str(start)],
            cwd=APP_DIR,
            env=_env(tmp_path, **extra),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(count)
    ]
    return [(p.wait(timeout=60), *p.communicate()) for p in procs]


def _columns(path: Path, table: str) -> set:
    import sqlite3

    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_init_db_from_many_processes_at_once_on_a_fresh_file(tmp_path):
    for attempt in range(3):
        target = tmp_path / f"run{attempt}"
        target.mkdir()
        results = _boot_many(target, 6)
        failures = [err for code, _out, err in results if code != 0]
        assert not failures, failures[0]
        guest = _columns(target / "race.db", "guest")
        assert {"doc_number_enc", "fee_host_reason_reference"} <= guest


def test_bootstrap_admin_is_created_once_when_web_workers_race(tmp_path):
    results = _boot_many(
        tmp_path,
        4,
        BOOT_ADMIN="1",
        UBYHOST_BOOTSTRAP_ADMIN="1",
        UBYHOST_ADMIN_EMAIL="race-admin@example.test",
    )
    failures = [err for code, _out, err in results if code != 0]
    assert not failures, failures[0]
    import sqlite3

    conn = sqlite3.connect(tmp_path / "race.db")
    try:
        admins = conn.execute("SELECT COUNT(*) FROM user_account WHERE role = 'admin'").fetchone()[0]
    finally:
        conn.close()
    assert admins == 1


def test_the_startup_lock_is_reentrant_in_one_process(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "reentrant.db")
    with db.startup_lock():
        with db.startup_lock():
            db.init_db()
    assert db.query_one("SELECT COUNT(*) AS n FROM settings") is not None


def test_init_db_waits_for_a_lock_held_by_another_process(monkeypatch, tmp_path):
    """The lock is real across processes: init_db blocks until it is released."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "blocked.db")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, sys, time\n"
            "h = open(sys.argv[1], 'a+')\n"
            "fcntl.flock(h, fcntl.LOCK_EX)\n"
            "print('held', flush=True)\n"
            "time.sleep(1.5)\n",
            str(config.DATA_DIR / db.STARTUP_LOCK_NAME),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        started = time.monotonic()
        db.init_db()
        waited = time.monotonic() - started
    finally:
        holder.wait(timeout=10)
    assert waited >= 1.0
