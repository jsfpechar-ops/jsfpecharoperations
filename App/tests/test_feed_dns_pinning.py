"""DNS rebinding must not bypass iCal SSRF validation at connect time."""
from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from app import config
from app import feed_fetch
from app.feed_fetch import CalendarFetchError, fetch_calendar_text


@pytest.fixture(autouse=True)
def enforce_public_ical_only(monkeypatch):
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", False)


def test_fetch_pins_first_resolved_ip_against_dns_rebinding(monkeypatch):
    evil = (
        b"BEGIN:VCALENDAR\r\n"
        b"PRODID:-//ssrf-poc\r\n"
        b"END:VCALENDAR\r\n"
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.end_headers()
            self.wfile.write(evil)

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    real_gai = socket.getaddrinfo
    lookups = {"count": 0}

    public_ip = "93.184.216.34"

    def rebinding_gai(host, port, *args, **kwargs):
        lookups["count"] += 1
        if lookups["count"] == 1:
            return real_gai(public_ip, port, *args, **kwargs)
        return real_gai("127.0.0.1", server.server_port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", rebinding_gai)

    connected: list[str] = []

    def track_pinned_connect(pinned_ip, port, **kwargs):
        connected.append(pinned_ip)
        raise ConnectionRefusedError()

    monkeypatch.setattr(feed_fetch, "_socket_connect_pinned", track_pinned_connect)

    with pytest.raises(CalendarFetchError):
        fetch_calendar_text("http://rebind.example/calendar.ics")

    assert lookups["count"] == 1
    assert connected == [public_ip]
    assert "127.0.0.1" not in connected
