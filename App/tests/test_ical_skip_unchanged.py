"""WP15: an unchanged calendar is neither downloaded in full nor parsed again."""
from __future__ import annotations

import logging
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import alerts, config, db, feed_fetch, icalsync


def _cal(events):
    body = "".join(
        f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{f.replace('-', '')}\nDTEND;VALUE=DATE:{t.replace('-', '')}\n"
        f"UID:{u}\nSUMMARY:Reserved\nEND:VEVENT\n" for u, f, t in events)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\n{body}END:VCALENDAR\n"


ONE = _cal([("one", "2099-03-01", "2099-03-05")])
TWO = _cal([("one", "2099-03-01", "2099-03-05"), ("two", "2099-04-01", "2099-04-03")])


@pytest.fixture
def feed(monkeypatch, tmp_path):
    db.close_connections()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wp15.sqlite3")
    db.init_db()
    now = db.utcnow()
    apartment = db.insert("apartment", {
        "internal_name": "WP15 flat", "automation_mode": "manual", "active": 1, "created_at": now,
    })
    feed_id = db.insert("ical_feed", {
        "apartment_id": apartment, "url": "https://calendar.example/x.ics", "active": 1,
        "created_at": now,
    })
    yield feed_id
    db.close_connections()


def _row(feed_id):
    return db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))


def _stays(feed_id):
    return sorted(
        row["uid"] for row in db.query(
            "SELECT uid FROM reservation WHERE ical_feed_id = ? AND status = 'active'", (feed_id,)
        )
    )


def _serve_texts(monkeypatch, texts):
    """fetch_feed stand-in: answers from ``texts`` and records what it was sent."""
    calls = []

    def fake(url, etag=None, last_modified=None):
        calls.append({"etag": etag, "last_modified": last_modified})
        return texts[min(len(calls), len(texts)) - 1]

    monkeypatch.setattr(icalsync, "fetch_feed", fake)
    return calls


def _spy_parse(monkeypatch):
    parsed = []
    real = icalsync.parse_events

    def spy(text):
        parsed.append(text)
        return real(text)

    monkeypatch.setattr(icalsync, "parse_events", spy)
    return parsed


def _stamp(feed_id, column, value):
    db.execute(f"UPDATE ical_feed SET {column} = ? WHERE id = ?", (value, feed_id))


def test_unchanged_body_is_not_parsed_and_only_the_check_is_written(feed, monkeypatch):
    _serve_texts(monkeypatch, [ONE, ONE])
    parsed = _spy_parse(monkeypatch)
    first = icalsync.sync_feed(_row(feed))
    assert first["outcome"] == "changed" and first["created"] == 1
    stored = _row(feed)
    assert stored["body_sha256"] == icalsync.body_digest(ONE)
    _stamp(feed, "last_sync_at", "2000-01-01T00:00:00+00:00")
    _stamp(feed, "last_checked_at", "2000-01-01T00:00:00+00:00")

    second = icalsync.sync_feed(_row(feed))

    assert second["outcome"] == "unchanged"
    assert len(parsed) == 1, "the unchanged calendar was parsed again"
    after = _row(feed)
    assert after["last_sync_at"] == "2000-01-01T00:00:00+00:00", "last_sync_at must keep its meaning"
    assert after["last_checked_at"] > "2000-01-01T00:00:00+00:00"
    assert after["last_status"] == "ok"
    assert _stays(feed) == ["one"]


def test_changed_body_is_reconciled_as_before(feed, monkeypatch):
    _serve_texts(monkeypatch, [ONE, TWO])
    parsed = _spy_parse(monkeypatch)
    icalsync.sync_feed(_row(feed))
    _stamp(feed, "last_sync_at", "2000-01-01T00:00:00+00:00")

    stats = icalsync.sync_feed(_row(feed))

    assert stats["outcome"] == "changed"
    assert stats["created"] == 1
    assert len(parsed) == 2
    assert _stays(feed) == ["one", "two"]
    after = _row(feed)
    assert after["body_sha256"] == icalsync.body_digest(TWO)
    assert after["last_sync_at"] > "2000-01-01T00:00:00+00:00"


def test_stored_validators_are_sent_and_a_304_skips_parsing(feed, monkeypatch):
    first = icalsync.FeedText(ONE)
    first.etag = '"v1"'
    first.last_modified = "Wed, 01 Jan 2099 00:00:00 GMT"
    not_modified = icalsync.FeedText("")
    not_modified.etag = '"v1"'
    not_modified.not_modified = True
    calls = _serve_texts(monkeypatch, [first, not_modified])
    parsed = _spy_parse(monkeypatch)

    icalsync.sync_feed(_row(feed))
    assert _row(feed)["etag"] == '"v1"'
    _stamp(feed, "last_sync_at", "2000-01-01T00:00:00+00:00")
    stats = icalsync.sync_feed(_row(feed))

    assert calls[0] == {"etag": None, "last_modified": None}
    assert calls[1] == {"etag": '"v1"', "last_modified": "Wed, 01 Jan 2099 00:00:00 GMT"}
    assert stats["outcome"] == "not_modified"
    assert len(parsed) == 1
    after = _row(feed)
    assert after["last_sync_at"] == "2000-01-01T00:00:00+00:00"
    assert after["last_checked_at"] > after["last_sync_at"]
    assert _stays(feed) == ["one"]


def test_a_failing_feed_still_raises_the_alert_and_is_read_in_full_next_time(feed, monkeypatch):
    _serve_texts(monkeypatch, [ONE])
    icalsync.sync_feed(_row(feed))

    def broken(url, etag=None, last_modified=None):
        raise icalsync.FeedError("Calendar returned HTTP 500.")

    monkeypatch.setattr(icalsync, "fetch_feed", broken)
    stats = icalsync.sync_all()
    assert stats["errors"] == 1
    row = _row(feed)
    assert row["last_status"] == "error"
    assert "feed_error" in [a["kind"] for a in alerts.open_alerts()]

    # The same calendar as before the error is reconciled again, not skipped,
    # and the error clears.
    calls = _serve_texts(monkeypatch, [ONE])
    parsed = _spy_parse(monkeypatch)
    again = icalsync.sync_feed(_row(feed))
    assert again["outcome"] == "changed"
    assert calls == [{"etag": None, "last_modified": None}]
    assert len(parsed) == 1
    assert _row(feed)["last_status"] == "ok"
    assert "feed_error" not in [a["kind"] for a in alerts.open_alerts()]


def test_a_suspect_feed_is_never_skipped(feed, monkeypatch):
    _serve_texts(monkeypatch, [ONE])
    icalsync.sync_feed(_row(feed))
    _stamp(feed, "last_status", "suspect")
    parsed = _spy_parse(monkeypatch)
    stats = icalsync.sync_feed(_row(feed))
    assert stats["outcome"] == "changed"
    assert len(parsed) == 1


def test_sync_all_counts_and_logs_the_outcomes(feed, monkeypatch, caplog):
    _serve_texts(monkeypatch, [ONE, ONE])
    icalsync.sync_all()
    with caplog.at_level(logging.INFO, logger="ubyhost.icalsync"):
        totals = icalsync.sync_all()
    assert (totals["feeds"], totals["unchanged"], totals["not_modified"], totals["changed"]) == (1, 1, 0, 0)
    assert "ical_sync_run feeds=1 not_modified=0 unchanged=1 changed=0 errors=0" in caplog.text


def test_a_legacy_feed_table_gets_the_new_columns(monkeypatch, tmp_path):
    database = tmp_path / "legacy-feed.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE ical_feed (id INTEGER PRIMARY KEY AUTOINCREMENT, apartment_id INTEGER NOT NULL, "
        "url TEXT NOT NULL, label TEXT, own_name TEXT, last_sync_at TEXT, last_status TEXT, "
        "last_error TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()
    db.close_connections()
    monkeypatch.setattr(config, "DB_PATH", database)
    try:
        db.init_db()
        columns = {row["name"] for row in db.query("PRAGMA table_info(ical_feed)")}
        assert {"etag", "last_modified", "body_sha256", "last_checked_at"} <= columns
    finally:
        db.close_connections()


# --- the HTTP side ----------------------------------------------------------------


def test_clean_validator_drops_unsafe_values():
    assert feed_fetch.clean_validator(' "abc" ') == '"abc"'
    assert feed_fetch.clean_validator('"a"\r\nX-Injected: 1') is None
    assert feed_fetch.clean_validator("x" * 300) is None
    assert feed_fetch.clean_validator("") is None
    assert feed_fetch.clean_validator(None) is None


class _Conditional(BaseHTTPRequestHandler):
    body = ONE.encode()
    seen: list = []

    def do_GET(self):
        self.seen.append({
            "If-None-Match": self.headers.get("If-None-Match"),
            "If-Modified-Since": self.headers.get("If-Modified-Since"),
        })
        if self.headers.get("If-None-Match") == '"v1"':
            self.send_response(304)
            self.send_header("ETag", '"v1"')
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("ETag", '"v1"')
        self.send_header("Last-Modified", "Wed, 01 Jan 2099 00:00:00 GMT")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *_args):
        return


class _Always304(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(304)
        self.end_headers()

    def log_message(self, *_args):
        return


def test_the_real_fetch_sends_conditional_headers_and_reads_a_304(monkeypatch):
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", True)
    monkeypatch.setattr(config, "DEPLOYMENT", "test")
    # This test's .example URL is served by its local HTTPServer. Preserve the
    # configured proxy for all other hosts and tests.
    import os

    for variable in ("NO_PROXY", "no_proxy"):
        inherited = os.environ.get(variable, "")
        entries = [entry for entry in inherited.split(",") if entry]
        if ".example" not in entries:
            entries.append(".example")
        monkeypatch.setenv(variable, ",".join(entries))
    real_gai = socket.getaddrinfo
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, port, *a, **k: real_gai("127.0.0.1" if host == "feed.example" else host, port, *a, **k),
    )
    _Conditional.seen = []
    server = HTTPServer(("127.0.0.1", 0), _Conditional)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://feed.example:{server.server_port}/calendar.ics"
    try:
        full = icalsync.fetch_feed(url)
        assert "BEGIN:VCALENDAR" in full
        assert (full.etag, full.last_modified) == ('"v1"', "Wed, 01 Jan 2099 00:00:00 GMT")
        assert not full.not_modified

        cached = icalsync.fetch_feed(url, etag=full.etag, last_modified=full.last_modified)
        assert cached.not_modified and cached == ""
        assert cached.etag == '"v1"'
        assert _Conditional.seen[0] == {"If-None-Match": None, "If-Modified-Since": None}
        assert _Conditional.seen[1] == {
            "If-None-Match": '"v1"', "If-Modified-Since": "Wed, 01 Jan 2099 00:00:00 GMT",
        }
        # Without validators a 304 is still an error, as before.
        server.RequestHandlerClass = _Always304
        with pytest.raises(icalsync.FeedError, match="HTTP 304"):
            icalsync.fetch_feed(url)
    finally:
        server.shutdown()
        server.server_close()
