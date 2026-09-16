"""DNS rebinding must not bypass iCal SSRF validation at connect time."""
from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests
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


def test_concurrent_fetches_serialize_pinned_connect(monkeypatch):
    """Overlapping sync jobs must not patch urllib3 with two different pins at once."""
    import time

    order: list[str] = []
    release = threading.Event()

    def slow_pinned_connect(pinned_ip, port, **kwargs):
        order.append(pinned_ip)
        if not release.wait(timeout=5):
            raise TimeoutError("timed out waiting for release")
        raise ConnectionRefusedError()

    monkeypatch.setattr(feed_fetch, "_socket_connect_pinned", slow_pinned_connect)

    def run_fetch(pinned_ip: str) -> None:
        try:
            with feed_fetch._connect_only_to(pinned_ip):
                requests.get("http://calendar.example/feed.ics", timeout=1, allow_redirects=False)
        except (requests.RequestException, ConnectionRefusedError, TimeoutError):
            pass

    first = threading.Thread(target=run_fetch, args=("first-pin",))
    first.start()
    for _ in range(100):
        if order:
            break
        time.sleep(0.01)
    assert order == ["first-pin"]

    second = threading.Thread(target=run_fetch, args=("second-pin",))
    second.start()
    time.sleep(0.05)
    assert order == ["first-pin"]

    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert not first.is_alive() and not second.is_alive()
    assert order == ["first-pin", "second-pin"]
