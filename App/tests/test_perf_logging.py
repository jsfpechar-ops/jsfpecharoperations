"""WP13: per-request query, DB-time and lock-time numbers, and the report.

The access line gains ``q=``, ``db_ms=`` and ``lock_ms=``; the counter behind
them is a fresh object per request; nothing from the request itself (a token,
a query string, guest data) reaches the line; jobs log their run time; and
``tools/perf_report.py`` turns a week of lines into per-group numbers without
ever printing a route.
"""
from __future__ import annotations

import io
import logging
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, db, scheduler
from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import perf_report  # noqa: E402

ACCESS_LOGGER = "ubyhost.access"
LINE_RE = re.compile(
    r"^method=\w+ route=\S+ status=\d+ ms=\d+ q=(\d+) db_ms=(\d+) lock_ms=(\d+)$"
)


@pytest.fixture(autouse=True)
def _no_counter_left_behind():
    """Tests that start a counter by hand must not leave it on the main thread."""
    token = db._request_stats.set(None)
    yield
    db._request_stats.reset(token)


def _lines(caplog, name=ACCESS_LOGGER):
    return [record.getMessage() for record in caplog.records if record.name == name]


def test_the_access_line_carries_query_count_and_db_time(caplog):
    db.init_db()
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get("/login?lang=en")
    lines = _lines(caplog)
    assert len(lines) == 1, lines
    match = LINE_RE.match(lines[0])
    assert match, lines[0]
    assert int(match.group(1)) >= 1  # the login page reads the database


def test_the_counter_starts_fresh_for_every_request(caplog):
    db.init_db()
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        for _ in range(3):
            client.get("/login?lang=en")
    counts = [int(LINE_RE.match(line).group(1)) for line in _lines(caplog)]
    assert len(counts) == 3
    # Identical requests cost the same; a counter that carried over would grow.
    assert counts[1] == counts[2]
    assert counts[2] <= counts[0]


def test_start_request_stats_replaces_the_previous_counter():
    first = db.start_request_stats()
    db.query("SELECT 1 AS one")
    assert first.queries == 1
    second = db.start_request_stats()
    assert second is not first
    assert second.queries == 0
    assert db.current_request_stats() is second
    db.query("SELECT 1 AS one")
    assert (first.queries, second.queries) == (1, 1)
    assert second.db_seconds > 0


def test_lock_wait_is_measured_on_begin_immediate():
    db.init_db()
    holder_ready = threading.Event()

    def hold_the_write_lock():
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30, isolation_level=None)
        conn.execute("BEGIN IMMEDIATE")
        holder_ready.set()
        time.sleep(0.3)
        conn.execute("COMMIT")
        conn.close()

    thread = threading.Thread(target=hold_the_write_lock)
    thread.start()
    holder_ready.wait(5)
    stats = db.start_request_stats()
    with db.immediate() as cur:
        cur.execute("SELECT 1")
    thread.join()
    assert stats.lock_seconds >= 0.2
    assert stats.db_seconds >= stats.lock_seconds
    assert stats.queries == 1  # BEGIN, COMMIT and the PRAGMAs are not counted


def test_no_token_query_string_or_guest_data_in_the_line(caplog):
    db.init_db()
    token = "z9y8x7w6v5u4t3s2r1q0" * 2
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get(f"/l/{token}?email=guest@example.test&surname=Novak")
    lines = _lines(caplog)
    assert lines and all(LINE_RE.match(line) for line in lines), lines
    joined = " ".join(lines)
    for leaked in (token, "guest@example.test", "Novak", "email="):
        assert leaked not in joined
    assert "route=/l/{token}" in joined


def test_scheduler_jobs_log_run_time_and_items(monkeypatch, caplog):
    db.init_db()
    monkeypatch.setattr(
        scheduler.icalsync,
        "sync_all",
        lambda: {"feeds": 4, "changed": 1, "created": 2, "updated": 0, "cancelled": 0, "errors": 0},
    )
    with caplog.at_level(logging.INFO, logger="ubyhost.scheduler"):
        scheduler._job_sync_calendars()
    runs = [line for line in _lines(caplog, "ubyhost.scheduler") if line.startswith("job run ")]
    assert len(runs) == 1
    assert re.match(r"^job run job=ical ok=1 ms=\d+ feeds=4 changed=1 created=2 ", runs[0]), runs


SAMPLE = """\
2026-10-01 10:00:00,001 INFO    ubyhost.access: method=GET route=/ status=200 ms=10 q=5 db_ms=2 lock_ms=0
2026-10-01 10:00:01,001 INFO    ubyhost.access: method=GET route=/reservations status=200 ms=30 q=9 db_ms=6 lock_ms=1
2026-10-01 10:00:02,001 INFO    ubyhost.access: method=GET route=/l/{token}/{reservation_id} status=200 ms=20 q=4 db_ms=3 lock_ms=0
2026-10-01 10:00:03,001 INFO    ubyhost.access: method=POST route=/l/{token}/{reservation_id}/save status=500 ms=80 q=12 db_ms=40 lock_ms=25
2026-10-01 10:00:04,001 INFO    ubyhost.access: method=GET route=/cenik status=200 ms=5 q=1 db_ms=1 lock_ms=0
2026-10-01 10:00:05,001 INFO    ubyhost.access: method=GET route=/admin/operations status=200 ms=15 q=8 db_ms=5 lock_ms=0
2026-10-01 10:00:06,001 INFO    ubyhost.scheduler: job run job=ical ok=1 ms=900 feeds=10 changed=2 created=3
2026-10-01 11:00:06,001 INFO    ubyhost.scheduler: job run job=ical ok=0 ms=50
2026-09-01 10:00:00,001 INFO    ubyhost.access: method=GET route=/old status=200 ms=99999 q=1 db_ms=1 lock_ms=0
2026-10-01 10:00:07,001 INFO    ubyhost.app: something unrelated route=/l/abcdef
"""


def test_perf_report_groups_routes_and_skips_old_lines(tmp_path, capsys):
    log_file = tmp_path / "app.log"
    log_file.write_text(SAMPLE, encoding="utf-8")
    assert perf_report.main([str(log_file), "--now", "2026-10-03T12:00:00"]) == 0
    out = capsys.readouterr().out
    rows = {line.split()[0]: line.split() for line in out.splitlines() if line.strip()}
    assert rows["host"][1] == "2"  # "/" and /reservations
    assert rows["guest"][1] == "2"
    assert rows["public"][1] == "1"
    assert rows["admin"][1] == "1"
    assert rows["guest"][-1] == "50.00"  # one 500 out of two guest requests
    assert "99999" not in out  # the September line is outside the window
    assert "iCal changed ratio: 2/10" in out
    assert "ical" in rows and rows["ical"][2] == "1"  # one failed run
    # No route, and nothing token-shaped, is ever printed.
    assert "/l/" not in out and "{token}" not in out and "/reservations" not in out


def test_perf_report_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(SAMPLE))
    assert perf_report.main(["--days", "0"]) == 0
    out = capsys.readouterr().out
    assert "99999" in out  # --days 0 keeps every line


def test_route_groups():
    assert perf_report.route_group("/l/{token}") == "guest"
    assert perf_report.route_group("/admin/users") == "admin"
    assert perf_report.route_group("/pruvodce/{slug}") == "public"
    assert perf_report.route_group("/") == "host"
    assert perf_report.route_group("<unmatched>") == "other"
    assert perf_report.percentile([1, 2, 3, 4, 100], 99) == 100
    assert perf_report.percentile([], 50) == 0
