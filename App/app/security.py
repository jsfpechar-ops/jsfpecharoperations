"""Small, dependency-free web security helpers."""
from __future__ import annotations

import hashlib
import hmac
import posixpath
from typing import Optional
from urllib.parse import unquote, urlsplit, urlunsplit

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import auth, config

CSRF_FIELD = "_csrf"
CSRF_HEADER = "x-csrf-token"
CSRF_MAX_AGE = auth.SESSION_REMEMBER_MAX_AGE


def safe_local_path(value: Optional[str], default: str = "/") -> str:
    """Return a normalized same-site path, or ``default`` for unsafe input."""
    raw = (value or "").strip()
    if not raw or any(ord(char) < 0x20 for char in raw) or "\\" in raw:
        return default
    split = urlsplit(raw)
    if split.scheme or split.netloc or not split.path.startswith("/") or split.path.startswith("//"):
        return default
    decoded_path = unquote(split.path)
    if (
        decoded_path.startswith("//")
        or "\\" in decoded_path
        or any(ord(char) < 0x20 for char in decoded_path)
    ):
        return default
    path = posixpath.normpath(split.path)
    if not path.startswith("/") or path.startswith("//"):
        return default
    return urlunsplit(("", "", path, split.query, ""))


def _csrf_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-csrf")


def _session_binding(request: Request) -> str:
    session = request.cookies.get(auth.SESSION_COOKIE, "")
    return hashlib.sha256(session.encode("utf-8")).hexdigest()


def csrf_token(request: Request) -> str:
    """Issue a signed token bound to the current host session."""
    return _csrf_serializer().dumps({"session": _session_binding(request)})


def csrf_token_valid(request: Request, token: str) -> bool:
    try:
        payload = _csrf_serializer().loads(token or "", max_age=CSRF_MAX_AGE)
    except BadSignature:
        return False
    expected = _session_binding(request)
    return isinstance(payload, dict) and hmac.compare_digest(
        str(payload.get("session", "")), expected
    )


def _canonical_host(hostname: Optional[str]) -> str:
    host = (hostname or "").lower().split(":", 1)[0]
    if host.startswith("www."):
        return host[4:]
    return host


def _hosts_equivalent(left: Optional[str], right: Optional[str]) -> bool:
    return _canonical_host(left) == _canonical_host(right) and bool(_canonical_host(left))


def _request_is_same_site(request: Request) -> bool:
    """Reject obvious cross-site posts; allow same registrable host (e.g. www vs apex)."""
    fetch_site = (request.headers.get("sec-fetch-site") or "").lower()
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme.lower() != request.url.scheme.lower():
            return False
        return _hosts_equivalent(parsed.hostname, request.url.hostname)
    referer = request.headers.get("referer")
    if referer:
        parsed = urlsplit(referer)
        return _hosts_equivalent(parsed.hostname, request.url.hostname)
    if fetch_site == "cross-site":
        return False
    return True


async def protect_host_post(request: Request) -> None:
    """Require CSRF proof for state-changing host requests in production."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    if config.DEPLOYMENT != "production":
        return
    if not _request_is_same_site(request):
        raise HTTPException(status_code=403, detail="Cross-site request rejected.")
    supplied = request.headers.get(CSRF_HEADER, "")
    if not supplied:
        form = await request.form()
        supplied = str(form.get(CSRF_FIELD, ""))
    if not csrf_token_valid(request, supplied):
        raise HTTPException(status_code=403, detail="Invalid or expired form token.")
