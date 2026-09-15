"""Validate iCal feed URLs before the server fetches them (SSRF mitigation)."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
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


# Ranges Python reports as neither private nor reserved, so the attribute
# checks below miss them, but which still reach somewhere other than the public
# internet. A self-hosted box behind carrier-grade NAT, or inside a cluster that
# uses 100.64.0.0/10 for pods, can reach its neighbours through them.
_EXTRA_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("100.64.0.0/10", "192.0.0.0/24", "198.18.0.0/15")
)


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast:
        return True
    # Link-local IPv4 metadata (cloud)
    if ip == ipaddress.ip_address("169.254.169.254"):
        return True
    if any(ip in network for network in _EXTRA_BLOCKED_NETWORKS if ip.version == network.version):
        return True
    return False


@dataclass(frozen=True)
class CalendarFetchTarget:
    """Validated calendar URL plus addresses allowed for the next TCP connect."""

    url: str
    hostname: str
    port: int
    scheme: str
    pinned_ips: tuple[str, ...]


def _default_port(scheme: str, port: int | None) -> int:
    if port is not None:
        return port
    return 443 if scheme == "https" else 80


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


def resolve_calendar_target(url: str) -> CalendarFetchTarget:
    """Validate a calendar URL, resolve DNS once, and return connect-time pinned IPs."""
    raw = (url or "").strip()
    try:
        parsed = urlparse(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise FeedError("Calendar URL is malformed.") from exc
    if parsed.scheme not in ("http", "https"):
        raise FeedError("Calendar URL must use http:// or https://.")
    if not hostname:
        raise FeedError("Calendar URL is missing a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise FeedError("Calendar URL must not contain embedded credentials.")
    if port is not None and not 1 <= port <= 65535:
        raise FeedError("Calendar URL has an invalid port.")
    host = hostname.lower().rstrip(".")
    allow_private = config.ICAL_ALLOW_PRIVATE and config.DEPLOYMENT != "production"
    if not allow_private:
        if host in _BLOCKED_HOSTNAMES or host.endswith(".local"):
            raise FeedError("That calendar host is not allowed.")
        if host == "127.0.0.1" or host.startswith("127."):
            raise FeedError("Calendar URL must not point to a loopback address.")
    ips = _resolve_host_ips(host)
    if not allow_private:
        for ip in ips:
            if _blocked_ip(ip):
                raise FeedError(
                    "Calendar URL must point to a public internet host, not a private or internal address."
                )
    pinned = tuple(dict.fromkeys(str(ip) for ip in ips))
    return CalendarFetchTarget(
        url=raw,
        hostname=host,
        port=_default_port(parsed.scheme, port),
        scheme=parsed.scheme.lower(),
        pinned_ips=pinned,
    )


def validate_calendar_url(url: str) -> str:
    """Return a normalised URL or raise FeedError if the target is not allowed."""
    return resolve_calendar_target(url).url


def resolve_redirect_url(current: str, location: str) -> str:
    joined = urljoin(current, location)
    return validate_calendar_url(joined)
