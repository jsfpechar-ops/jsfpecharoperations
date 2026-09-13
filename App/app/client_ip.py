"""Resolve the visitor IP behind reverse proxies without trusting client-spoofed headers."""
from __future__ import annotations

import ipaddress
from typing import Iterable, Optional

from . import config

_TRUSTED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()


def _parse_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        networks.append(ipaddress.ip_network(piece, strict=False))
    return networks


def _default_cloudflare_proxy_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Docker/Caddy peers on the internal network when Cloudflare fronts the origin."""
    return [
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    ]


def trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    global _TRUSTED_NETWORKS
    if not _TRUSTED_NETWORKS:
        raw = (config.TRUSTED_PROXY_CIDRS or "").strip()
        if raw:
            nets = _parse_networks(raw)
        elif config.CLOUDFLARE_PROXY:
            nets = _default_cloudflare_proxy_networks()
        else:
            nets = []
        _TRUSTED_NETWORKS = tuple(nets)
    return _TRUSTED_NETWORKS


def reset_trusted_proxy_cache() -> None:
    """Test helper: reload TRUSTED_PROXY_CIDRS / CLOUDFLARE_PROXY from config."""
    global _TRUSTED_NETWORKS
    _TRUSTED_NETWORKS = ()


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
