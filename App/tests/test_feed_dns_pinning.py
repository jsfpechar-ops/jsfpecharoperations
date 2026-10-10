"""DNS rebinding must not bypass iCal SSRF validation at connect time.

[F9] Pinning used to be a process-global monkeypatch of
``urllib3.util.connection.create_connection``, so a scheduler poll and a manual
"Sync now" could cross pinned addresses, or leave the wrong function installed
for the rest of the process. These tests cover the per-request implementation
that replaced it, plus the fetch limits it must keep enforcing.
"""
from __future__ import annotations

import os
import socket
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import urllib3.util.connection
from app import config
from app import feed_fetch
from app.feed_fetch import CalendarFetchError, fetch_calendar_text


@pytest.fixture(autouse=True)
def enforce_public_ical_only(monkeypatch):
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", False)
    # Every mocked HTTP endpoint in this module uses reserved .example names.
    # Let those fixture URLs reach their loopback servers despite cloud proxy
    # injection; keep proxy settings active for every other host.
    for variable in ("NO_PROXY", "no_proxy"):
        inherited = os.environ.get(variable, "")
        entries = [entry for entry in inherited.split(",") if entry]
        if ".example" not in entries:
            entries.append(".example")
        monkeypatch.setenv(variable, ",".join(entries))


def _calendar(prodid: str) -> bytes:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        f"PRODID:-//{prodid}//EN\r\n"
        "END:VCALENDAR\r\n"
    ).encode()


def _serve(handler, host: str, port: int, family: int = socket.AF_INET) -> HTTPServer:
    if family == socket.AF_INET6:

        class _V6Server(HTTPServer):
            address_family = socket.AF_INET6

            def server_bind(self):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                super().server_bind()

        server = _V6Server((host, port), handler)
    else:
        server = HTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _stop(*servers: HTTPServer) -> None:
    for server in servers:
        server.shutdown()
        server.server_close()


def _point_hosts_at(monkeypatch, hosts: dict[str, str]) -> None:
    """Resolve only the named hosts; every other name keeps the real resolver."""
    real_gai = socket.getaddrinfo

    def fake_gai(host, port, *args, **kwargs):
        if host in hosts:
            return real_gai(hosts[host], port, *args, **kwargs)
        return real_gai(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_gai)


def _allow_local_servers(monkeypatch, *hosts: str) -> None:
    """Let the loopback test servers through: self-hosted, so private targets are on."""
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", True)
    monkeypatch.setattr(config, "DEPLOYMENT", "test")
    if hosts:
        _point_hosts_at(monkeypatch, {host: "127.0.0.1" for host in hosts})


class _Routes(BaseHTTPRequestHandler):
    """A calendar server driven by a path -> (status, Location) table."""

    body = b""
    routes: dict[str, tuple[int, str | None]] = {}
    counters: Counter = Counter()

    def do_GET(self):
        self.counters[self.path] += 1
        status, location = self.routes.get(self.path, (200, None))
        self.send_response(status)
        if location is not None:
            self.send_header("Location", location)
        self.send_header("Content-Type", "text/calendar")
        if status == 200:
            self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        if status == 200:
            self.wfile.write(self.body)

    def log_message(self, *_args):
        return


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


def test_two_concurrent_fetches_do_not_cross_pinned_addresses(monkeypatch):
    """[F9] Each request pins its own address; nothing process-global changes."""
    _allow_local_servers(monkeypatch)
    barrier = threading.Barrier(2, timeout=15)
    untouched: list[bool] = []
    real_create_connection = urllib3.util.connection.create_connection

    class _Waiting(BaseHTTPRequestHandler):
        body = b""

        def do_GET(self):
            untouched.append(
                urllib3.util.connection.create_connection is real_create_connection
            )
            barrier.wait()
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.send_header("Content-Length", str(len(self.body)))
            self.end_headers()
            self.wfile.write(self.body)

        def log_message(self, *_args):
            return

    class FirstHandler(_Waiting):
        body = _calendar("first")

    class SecondHandler(_Waiting):
        body = _calendar("second")

    # One server per address, both on the same port, so a crossed pin is visible.
    first = _serve(FirstHandler, "127.0.0.1", 0)
    second = _serve(SecondHandler, "::1", first.server_port, family=socket.AF_INET6)
    try:
        _point_hosts_at(monkeypatch, {"first.example": "127.0.0.1", "second.example": "::1"})
        results: dict[str, str] = {}
        failures: dict[str, str] = {}

        def fetch(name: str, url: str) -> None:
            try:
                results[name] = fetch_calendar_text(url)
            except Exception as exc:  # reported as a test failure below
                failures[name] = f"{type(exc).__name__}: {exc}"

        threads = [
            threading.Thread(
                target=fetch,
                args=(name, f"http://{name}.example:{first.server_port}/calendar.ics"),
            )
            for name in ("first", "second")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert failures == {}
        assert "PRODID:-//first//EN" in results["first"]
        assert "PRODID:-//second//EN" in results["second"]
        # Both requests were in flight at once and the global dialler never moved.
        assert untouched == [True, True]
        assert urllib3.util.connection.create_connection is real_create_connection
    finally:
        _stop(first, second)


def test_a_calendar_over_the_size_cap_is_refused(monkeypatch):
    _allow_local_servers(monkeypatch, "feed.example")
    cap = feed_fetch.MAX_FEED_BYTES

    class DeclaredLength(_Routes):
        body = _calendar("huge") + b"0" * cap

    class Streamed(_Routes):
        body = _calendar("huge") + b"0" * cap

        def do_GET(self):
            # No Content-Length: the cap must stop a streamed body too.
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.end_headers()
            try:
                self.wfile.write(self.body)
            except OSError:
                pass

    declared = _serve(DeclaredLength, "127.0.0.1", 0)
    streamed = _serve(Streamed, "127.0.0.1", 0)
    try:
        with pytest.raises(CalendarFetchError, match="too large"):
            fetch_calendar_text(f"http://feed.example:{declared.server_port}/calendar.ics")
        with pytest.raises(CalendarFetchError, match="too large"):
            fetch_calendar_text(f"http://feed.example:{streamed.server_port}/calendar.ics")
    finally:
        _stop(declared, streamed)


def test_a_calendar_exactly_at_the_size_cap_is_accepted(monkeypatch):
    _allow_local_servers(monkeypatch, "feed.example")
    cap = feed_fetch.MAX_FEED_BYTES
    exact = _calendar("exact")
    exact += b"0" * (cap - len(exact))

    class Handler(_Routes):
        body = exact

    server = _serve(Handler, "127.0.0.1", 0)
    try:
        text = fetch_calendar_text(f"http://feed.example:{server.server_port}/calendar.ics")
        assert len(text.encode()) == cap
    finally:
        _stop(server)


def test_a_redirect_chain_is_followed_and_bounded(monkeypatch):
    _allow_local_servers(monkeypatch, "feed.example")

    class Chain(_Routes):
        body = _calendar("chain")
        routes = {
            "/hop1": (302, "/hop2"),
            "/hop2": (302, "/hop3"),
            "/hop3": (200, None),
        }
        counters: Counter = Counter()

    class Loop(_Routes):
        routes = {"/loop": (302, "/loop")}
        counters: Counter = Counter()

    class Nowhere(_Routes):
        routes = {"/go": (302, None)}

    chain = _serve(Chain, "127.0.0.1", 0)
    loop = _serve(Loop, "127.0.0.1", 0)
    nowhere = _serve(Nowhere, "127.0.0.1", 0)
    try:
        text = fetch_calendar_text(f"http://feed.example:{chain.server_port}/hop1")
        assert "PRODID:-//chain//EN" in text

        with pytest.raises(CalendarFetchError, match="redirected too many times"):
            fetch_calendar_text(f"http://feed.example:{loop.server_port}/loop")
        # MAX_REDIRECTS hops are allowed; the response after them ends the loop.
        assert Loop.counters["/loop"] == feed_fetch.MAX_REDIRECTS + 1

        with pytest.raises(CalendarFetchError, match="missing Location"):
            fetch_calendar_text(f"http://feed.example:{nowhere.server_port}/go")
    finally:
        _stop(chain, loop, nowhere)


def test_a_host_with_mixed_public_and_private_addresses_is_refused(monkeypatch):
    """One private answer is enough to disqualify a public-looking host."""
    real_gai = socket.getaddrinfo

    def mixed_gai(host, port, *args, **kwargs):
        if host == "mixed.example":
            return real_gai("93.184.216.34", port, *args, **kwargs) + real_gai(
                "127.0.0.1", port, *args, **kwargs
            )
        return real_gai(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", mixed_gai)
    with pytest.raises(CalendarFetchError) as caught:
        fetch_calendar_text("http://mixed.example/calendar.ics")
    assert "public internet host" in str(caught.value)


def test_the_pinned_https_connection_dials_the_pinned_address(monkeypatch):
    """The hostname stays on the connection, so SNI and Host still name the real host."""
    dialled: list[tuple[str, int]] = []

    def record(pinned_ip, port, **kwargs):
        dialled.append((pinned_ip, port))
        raise ConnectionRefusedError()

    monkeypatch.setattr(feed_fetch, "_socket_connect_pinned", record)
    adapter = feed_fetch._pinned_adapter("203.0.113.9")
    pool = adapter.poolmanager.connection_from_url("https://feed.example/calendar.ics")
    connection = pool._new_conn()
    try:
        assert isinstance(connection, feed_fetch._PinnedConnection)
        assert connection.pinned_ip == "203.0.113.9"
        assert connection.host == "feed.example"
        assert connection.port == 443
        # A dial failure is reported as urllib3 reports it, so requests maps it
        # to its usual ConnectionError and the host sees a fetch failure.
        with pytest.raises(urllib3.exceptions.NewConnectionError):
            connection._new_conn()
    finally:
        connection.close()
    assert dialled == [("203.0.113.9", 443)]


def test_a_failing_connection_is_reported_not_retried_forever(monkeypatch):
    _allow_local_servers(monkeypatch, "dead.example")
    # Port 1 has no listener, so the pinned dial fails on every attempt.
    with pytest.raises(CalendarFetchError, match="Could not download the calendar"):
        fetch_calendar_text("http://dead.example:1/calendar.ics")


def test_a_calendar_is_read_as_utf8_and_loses_its_bom(monkeypatch):
    """No charset means UTF-8, not Latin-1; a BOM never reaches the parser."""
    _allow_local_servers(monkeypatch, "feed.example")
    payload = "﻿BEGIN:VCALENDAR\r\nSUMMARY:Novák Šťastný\r\nEND:VCALENDAR\r\n".encode()

    class Plain(_Routes):
        body = payload

    class Declared(_Routes):
        body = payload

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Length", str(len(self.body)))
            self.end_headers()
            self.wfile.write(self.body)

    plain = _serve(Plain, "127.0.0.1", 0)
    declared = _serve(Declared, "127.0.0.1", 0)
    try:
        for server in (plain, declared):
            text = fetch_calendar_text(f"http://feed.example:{server.server_port}/calendar.ics")
            assert text.startswith("BEGIN:VCALENDAR")
            assert "Novák Šťastný" in text
    finally:
        _stop(plain, declared)
