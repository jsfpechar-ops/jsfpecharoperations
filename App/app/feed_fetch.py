"""Fetch calendar feeds with DNS pinning (no second lookup at connect time)."""
from __future__ import annotations

import contextlib
import socket
import threading
from typing import Iterator, Optional

import requests
import urllib3.util.connection as urllib3_connection

from . import feed_url
from .feed_url import CalendarFetchTarget, FeedUrlError

USER_AGENT = "UbyHost/1.0 (+self-hosted Czech foreign-police reporting)"
FETCH_TIMEOUT = 45
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3

# urllib3's create_connection is patched globally while connecting; serialize fetches
# so concurrent sync jobs cannot pin one thread's HTTP client to another's IP.
_connect_lock = threading.Lock()


class CalendarFetchError(Exception):
    pass


def _socket_connect_pinned(
    pinned_ip: str,
    port: int,
    timeout: object = urllib3_connection._DEFAULT_TIMEOUT,
    source_address: Optional[tuple[str, int]] = None,
    socket_options: Optional[list[tuple[int, int, int]]] = None,
) -> socket.socket:
    """Open TCP to a validated address without calling ``getaddrinfo`` again."""
    if ":" in pinned_ip:
        family = socket.AF_INET6
    else:
        family = socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    urllib3_connection._set_socket_options(sock, socket_options)
    if timeout is not urllib3_connection._DEFAULT_TIMEOUT:
        sock.settimeout(timeout)
    if source_address:
        sock.bind(source_address)
    sock.connect((pinned_ip, port))
    return sock


@contextlib.contextmanager
def _connect_only_to(pinned_ip: str) -> Iterator[None]:
    """Force urllib3 to open TCP to ``pinned_ip`` without a second DNS lookup."""
    original = urllib3_connection.create_connection

    def create_connection(
        address,
        timeout=urllib3_connection._DEFAULT_TIMEOUT,
        source_address=None,
        socket_options=None,
    ):
        _host, port = address
        return _socket_connect_pinned(
            pinned_ip,
            port,
            timeout=timeout,
            source_address=source_address,
            socket_options=socket_options,
        )

    with _connect_lock:
        urllib3_connection.create_connection = create_connection
        try:
            yield
        finally:
            urllib3_connection.create_connection = original


def _request_get(target: CalendarFetchTarget, headers: dict[str, str]) -> requests.Response:
    last_error: Optional[Exception] = None
    for pinned in target.pinned_ips:
        try:
            with _connect_only_to(pinned):
                response = requests.get(
                    target.url,
                    timeout=FETCH_TIMEOUT,
                    headers=headers,
                    allow_redirects=False,
                    stream=True,
                )
            return response
        except requests.RequestException as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise CalendarFetchError("Could not connect to the calendar host.")


def fetch_calendar_text(url: str) -> str:
    """Download an iCal document; each hop is validated and pinned to resolved IPs."""
    try:
        current = feed_url.resolve_calendar_target(url)
    except FeedUrlError as exc:
        raise CalendarFetchError(str(exc)) from exc
    headers = {"User-Agent": USER_AGENT, "Accept": "text/calendar"}
    response: Optional[requests.Response] = None
    try:
        for hop in range(MAX_REDIRECTS + 1):
            response = _request_get(current, headers)
            if response.status_code in (301, 302, 303, 307, 308):
                if hop >= MAX_REDIRECTS:
                    response.close()
                    raise CalendarFetchError("Calendar redirected too many times.")
                location = response.headers.get("Location")
                if not location:
                    response.close()
                    raise CalendarFetchError(
                        f"Calendar redirect missing Location (HTTP {response.status_code})."
                    )
                response.close()
                try:
                    current = feed_url.resolve_calendar_target(
                        feed_url.resolve_redirect_url(current.url, location)
                    )
                except FeedUrlError as exc:
                    raise CalendarFetchError(str(exc)) from exc
                continue
            break
    except requests.RequestException as exc:
        raise CalendarFetchError(f"Could not download the calendar: {exc}") from exc
    if response is None:
        raise CalendarFetchError("Could not download the calendar.")
    if response.status_code != 200:
        response.close()
        raise CalendarFetchError(f"Calendar returned HTTP {response.status_code}.")
    content_length = response.headers.get("Content-Length", "")
    if content_length.isdigit() and int(content_length) > MAX_FEED_BYTES:
        response.close()
        raise CalendarFetchError("Calendar is too large.")
    body = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > MAX_FEED_BYTES:
                raise CalendarFetchError("Calendar is too large.")
    finally:
        response.close()
    text = bytes(body).decode(response.encoding or "utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text.upper():
        raise CalendarFetchError(
            "That URL did not return an iCal calendar. Check you copied the whole export link "
            "(it contains '/ical/' and usually ends with '.ics')."
        )
    return text
