"""Resolve the visitor IP behind reverse proxies without trusting client-spoofed headers."""
from __future__ import annotations

import ipaddress
import logging
from typing import Iterable, Optional

from . import config

log = logging.getLogger(__name__)

_TRUSTED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()
_warned_about_unset_proxies = False


def _parse_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        networks.append(ipaddress.ip_network(piece, strict=False))
    return networks


def _warn_about_unset_proxies() -> None:
    """Say once, loudly, that the operator's proxy is not configured."""
    global _warned_about_unset_proxies
    if _warned_about_unset_proxies:
        return
    _warned_about_unset_proxies = True
    log.warning(
        "CLOUDFLARE_PROXY is on but UBYHOST_TRUSTED_PROXY_CIDRS is unset, so "
        "CF-Connecting-IP is ignored and every visitor shares the proxy's rate-limit "
        "bucket. Set UBYHOST_TRUSTED_PROXY_CIDRS to the reverse proxy's network - see "
        "docs/CLOUDFLARE.md."
    )


def trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """The networks whose CF-Connecting-IP may be believed.

    Only an explicit UBYHOST_TRUSTED_PROXY_CIDRS is honoured. CLOUDFLARE_PROXY=1
    used to imply the whole private space (loopback, 10/8, 172.16/12, 192.168/16),
    which meant any host that could reach the origin from a private address - a
    co-tenant container, a machine on the office LAN - could name its own visitor
    address and walk past every per-address rate limit. The app cannot tell a real
    Caddy peer from any other private one, so it does not guess: an unset value
    trusts nothing and the operator names the proxy network instead.
    """
    global _TRUSTED_NETWORKS
    if not _TRUSTED_NETWORKS:
        raw = (config.TRUSTED_PROXY_CIDRS or "").strip()
        nets = _parse_networks(raw)
        if not nets and config.CLOUDFLARE_PROXY:
            _warn_about_unset_proxies()
        _TRUSTED_NETWORKS = tuple(nets)
    return _TRUSTED_NETWORKS


def reset_trusted_proxy_cache() -> None:
    """Test helper: reload TRUSTED_PROXY_CIDRS / CLOUDFLARE_PROXY from config."""
    global _TRUSTED_NETWORKS, _warned_about_unset_proxies
    _TRUSTED_NETWORKS = ()
    _warned_about_unset_proxies = False


def peer_host(scope: dict) -> Optional[str]:
    client = scope.get("client")
    if not client:
        return None
    return str(client[0]) if client[0] else None


def is_trusted_proxy(host: Optional[str], networks: Iterable | None = None) -> bool:
    if not host:
        return False
    nets = networks if networks is not None else trusted_proxy_networks()
    if not nets:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in nets)


def _normalise_visitor_ip(value: str) -> Optional[str]:
    candidate = (value or "").strip()
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def visitor_ip_from_cf_header(
    scope: dict,
    headers: dict[str, str],
    networks: Iterable | None = None,
) -> Optional[str]:
    """Return CF-Connecting-IP only when the immediate peer is a trusted proxy."""
    if not is_trusted_proxy(peer_host(scope), networks):
        return None
    return _normalise_visitor_ip(headers.get("cf-connecting-ip", ""))


def apply_visitor_client(scope: dict, headers: dict[str, str]) -> None:
    """Overwrite scope client with the visitor IP when safely derived from Cloudflare."""
    visitor = visitor_ip_from_cf_header(scope, headers)
    if not visitor:
        return
    _host, port = scope.get("client") or ("", 0)
    scope["client"] = (visitor, port or 0)
