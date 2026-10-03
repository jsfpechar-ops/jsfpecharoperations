"""Fetch calendar feeds with DNS pinning (no second lookup at connect time).

The pinning is done with a per-request ``requests`` adapter whose connection
class dials the address validated by ``feed_url`` while the pool keeps the
hostname. Nothing process-global is mutated, so a poll and a manual "Sync now"
running at the same time cannot cross pinned addresses.
"""
from __future__ import annotations

import socket
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests
import urllib3.connection
import urllib3.connectionpool
import urllib3.exceptions
import urllib3.util.connection

from . import feed_url
from .feed_url import CalendarFetchTarget, FeedUrlError

USER_AGENT = "UbyHost/1.0 (+self-hosted Czech foreign-police reporting)"
FETCH_TIMEOUT = 45
MAX_FEED_BYTES = 5 * 1024 * 1024
# A server that trickles bytes would otherwise hold the sync for ever.
TOTAL_TIMEOUT_SECONDS = 60
MAX_REDIRECTS = 3


class CalendarFetchError(Exception):
    pass


# A stored validator is sent back verbatim, so anything a server could use to
# smuggle a header (or that requests would refuse) is dropped instead.
MAX_VALIDATOR_LENGTH = 256


def clean_validator(value: Optional[str]) -> Optional[str]:
    """An ETag or Last-Modified value safe to store and send back, or None."""
    if not value:
        return None
    value = value.strip()
    if not value or len(value) > MAX_VALIDATOR_LENGTH:
        return None
    if any(not 0x20 <= ord(ch) <= 0x7E for ch in value):
        return None
    return value


@dataclass
class FetchedCalendar:
    """One download: the text, or ``not_modified`` when the server answered 304."""

    text: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    not_modified: bool = False


def _socket_connect_pinned(
    pinned_ip: str,
    port: int,
    timeout: object = urllib3.util.connection._DEFAULT_TIMEOUT,
    source_address: Optional[tuple[str, int]] = None,
    socket_options: Optional[list[tuple[int, int, int]]] = None,
) -> socket.socket:
    """Open TCP to a validated address without calling ``getaddrinfo`` again."""
    if ":" in pinned_ip:
        family = socket.AF_INET6
    else:
        family = socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    urllib3.util.connection._set_socket_options(sock, socket_options)
    if timeout is not urllib3.util.connection._DEFAULT_TIMEOUT:
        sock.settimeout(timeout)
    if source_address:
        sock.bind(source_address)
    sock.connect((pinned_ip, port))
    return sock


class _PinnedConnection:
    """Mixin: dial ``pinned_ip`` instead of resolving the pool's host again.

    The connection still carries the hostname as ``self.host``, so the ``Host``
    header, TLS SNI and certificate verification all keep naming the real host;
    only the TCP dial is pinned.
    """

    pinned_ip: str = ""

    def _new_conn(self) -> socket.socket:
        try:
            sock = _socket_connect_pinned(
                self.pinned_ip,
                self.port,
                timeout=self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except socket.gaierror as exc:
            raise urllib3.exceptions.NameResolutionError(self.host, self, exc) from exc
        except socket.timeout as exc:
            raise urllib3.exceptions.ConnectTimeoutError(
                self,
                f"Connection to {self.host} timed out. (connect timeout={self.timeout})",
            ) from exc
        except OSError as exc:
            raise urllib3.exceptions.NewConnectionError(
                self, f"Failed to establish a new connection: {exc}"
            ) from exc

        sys.audit("http.client.connect", self, self.host, self.port)

        return sock


def _pinned_adapter(pinned_ip: str) -> requests.adapters.HTTPAdapter:
    """An adapter whose sockets may only go to ``pinned_ip``.

    The classes are built per request so the address is carried on the class
    rather than in any shared state: two fetches to different hosts hold two
    different adapters and cannot interfere.
    """
    http_connection = type(
        "_PinnedHTTPConnection",
        (_PinnedConnection, urllib3.connection.HTTPConnection),
        {"pinned_ip": pinned_ip},
    )
    https_connection = type(
        "_PinnedHTTPSConnection",
        (_PinnedConnection, urllib3.connection.HTTPSConnection),
        {"pinned_ip": pinned_ip},
    )
    http_pool = type(
        "_PinnedHTTPConnectionPool",
        (urllib3.connectionpool.HTTPConnectionPool,),
        {"ConnectionCls": http_connection},
    )
    https_pool = type(
        "_PinnedHTTPSConnectionPool",
        (urllib3.connectionpool.HTTPSConnectionPool,),
        {"ConnectionCls": https_connection},
    )
    adapter = requests.adapters.HTTPAdapter()
    adapter.poolmanager.pool_classes_by_scheme = {"http": http_pool, "https": https_pool}
    return adapter


def _pinned_session(pinned_ip: str) -> requests.Session:
    session = requests.Session()
    session.mount("http://", _pinned_adapter(pinned_ip))
    session.mount("https://", _pinned_adapter(pinned_ip))
    return session


def _request_get(
    target: CalendarFetchTarget, headers: dict[str, str]
) -> tuple[requests.Response, requests.Session]:
    """Fetch ``target``, trying each validated address in turn.

    Returns the response together with the session that owns its socket. The
    caller must read the body before closing the session: with ``stream=True``
    the body arrives over a connection the session's pool owns.
    """
    last_error: Optional[Exception] = None
    for pinned in target.pinned_ips:
        session = _pinned_session(pinned)
        try:
            response = session.get(
                target.url,
                timeout=FETCH_TIMEOUT,
                headers=headers,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            last_error = exc
            session.close()
            continue
        return response, session
    if last_error:
        raise last_error
    raise CalendarFetchError("Could not connect to the calendar host.")


def fetch_calendar_text(url: str) -> str:
    """Download an iCal document; each hop is validated and pinned to resolved IPs."""
    return fetch_calendar(url).text


def fetch_calendar(
    url: str, etag: Optional[str] = None, last_modified: Optional[str] = None
) -> FetchedCalendar:
    """fetch_calendar_text, made conditional when the previous answer's validators are known.

    With ``etag`` or ``last_modified`` the request carries ``If-None-Match`` /
    ``If-Modified-Since``, and a 304 comes back as ``not_modified`` with no
    text. The validators of a full answer are returned for the next request.
    """
    try:
        current = feed_url.resolve_calendar_target(url)
    except FeedUrlError as exc:
        raise CalendarFetchError(str(exc)) from exc
    headers = {"User-Agent": USER_AGENT, "Accept": "text/calendar"}
    etag = clean_validator(etag)
    last_modified = clean_validator(last_modified)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    conditional = bool(etag or last_modified)
    response: Optional[requests.Response] = None
    session: Optional[requests.Session] = None
    text = ""
    validators: tuple = (None, None)
    try:
        for hop in range(MAX_REDIRECTS + 1):
            response, session = _request_get(current, headers)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            if hop >= MAX_REDIRECTS:
                raise CalendarFetchError("Calendar redirected too many times.")
            location = response.headers.get("Location")
            if not location:
                raise CalendarFetchError(
                    f"Calendar redirect missing Location (HTTP {response.status_code})."
                )
            response.close()
            session.close()
            session = None
            try:
                current = feed_url.resolve_calendar_target(
                    feed_url.resolve_redirect_url(current.url, location)
                )
            except FeedUrlError as exc:
                raise CalendarFetchError(str(exc)) from exc
        if response is None:
            raise CalendarFetchError("Could not download the calendar.")
        if response.status_code == 304 and conditional:
            return FetchedCalendar(
                "",
                etag=clean_validator(response.headers.get("ETag")) or etag,
                last_modified=clean_validator(response.headers.get("Last-Modified"))
                or last_modified,
                not_modified=True,
            )
        if response.status_code != 200:
            raise CalendarFetchError(f"Calendar returned HTTP {response.status_code}.")
        content_length = response.headers.get("Content-Length", "")
        if content_length.isdigit() and int(content_length) > MAX_FEED_BYTES:
            raise CalendarFetchError("Calendar is too large.")
        body = bytearray()
        deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > MAX_FEED_BYTES:
                raise CalendarFetchError("Calendar is too large.")
            if time.monotonic() > deadline:
                raise CalendarFetchError("Calendar download took too long.")
        # iCal is UTF-8 by spec. requests guesses ISO-8859-1 for any text/*
        # without a charset, which garbled Czech names; trust only an explicit one.
        declared = "charset" in response.headers.get("Content-Type", "").lower()
        encoding = response.encoding if declared and response.encoding else "utf-8-sig"
        # A BOM survives a declared "charset=utf-8" and breaks the parser.
        text = bytes(body).decode(encoding, errors="replace").lstrip("\ufeff")
        validators = (
            clean_validator(response.headers.get("ETag")),
            clean_validator(response.headers.get("Last-Modified")),
        )
    except requests.RequestException as exc:
        raise CalendarFetchError(f"Could not download the calendar: {exc}") from exc
    finally:
        if response is not None:
            response.close()
        if session is not None:
            session.close()
    if "BEGIN:VCALENDAR" not in text.upper():
        raise CalendarFetchError(
            "That URL did not return an iCal calendar. Check you copied the whole export link "
            "(it contains '/ical/' and usually ends with '.ics')."
        )
    return FetchedCalendar(text, etag=validators[0], last_modified=validators[1])
