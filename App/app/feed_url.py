"""Validate iCal feed URLs before the server fetches them (SSRF mitigation)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

from . import config

class FeedUrlError(Exception):
    """Unsafe or invalid calendar URL."""


FeedError = FeedUrlError  # alias for callers expecting icalsync.FeedError shape

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
    }
)


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast:
        return True
    # Link-local IPv4 metadata (cloud)
    if ip == ipaddress.ip_address("169.254.169.254"):
        return True
    return False


def _resolve_host_ips(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FeedError(f"Could not resolve calendar host: {exc}") from exc
    ips: list[ipaddress._BaseAddress] = []
    for info in infos:
        try:
            ips.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not ips:
        raise FeedError("Could not resolve calendar host.")
    return ips


def validate_calendar_url(url: str) -> str:
    """Return a normalised URL or raise FeedError if the target is not allowed."""
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise FeedError("Calendar URL must use http:// or https://.")
    if not parsed.hostname:
        raise FeedError("Calendar URL is missing a hostname.")
    if config.ICAL_ALLOW_PRIVATE:
        return raw
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".local"):
        raise FeedError("That calendar host is not allowed.")
    if host == "127.0.0.1" or host.startswith("127."):
        raise FeedError("Calendar URL must not point to a loopback address.")
    for ip in _resolve_host_ips(host):
        if _blocked_ip(ip):
            raise FeedError(
                "Calendar URL must point to a public internet host, not a private or internal address."
            )
    return raw


def resolve_redirect_url(current: str, location: str) -> str:
    joined = urljoin(current, location)
    return validate_calendar_url(joined)
