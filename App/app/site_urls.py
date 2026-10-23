"""Explicit public and host origins, shared by runtime and deploy preflight.

No app imports: the server's Python can validate this before building an image.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit


def origin(url: str) -> str:
    """Canonical browser origin, including a non-default port."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    default = {"http": 80, "https": 443}.get(scheme)
    return f"{scheme}://{host}" + (f":{port}" if port and port != default else "")


def validate_app_url(
    public_base_url: str, app_base_url: str, app_domain: str, *, production: bool,
) -> None:
    """Require a matching, explicit child hostname while preserving the RP ID."""
    if not app_base_url and not app_domain:
        return
    if not app_base_url or not app_domain:
        raise ValueError("Set UBYHOST_APP_BASE_URL and UBYHOST_APP_DOMAIN together.")
    public = urlsplit(public_base_url)
    app = urlsplit(app_base_url)
    domain = app_domain.lower()
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if len(domain) > 253 or not re.fullmatch(rf"(?:{label}\.)*{label}", domain):
        raise ValueError("UBYHOST_APP_DOMAIN must be a hostname, without a scheme or port.")
    # Accessing .port also rejects malformed or out-of-range ports.
    app_port = app.port
    if (
        app.scheme not in {"http", "https"}
        or not app.hostname
        or app.username is not None
        or app.password is not None
        or app.path not in {"", "/"}
        or app.query
        or app.fragment
        or any(char.isspace() for char in app_base_url)
    ):
        raise ValueError("UBYHOST_APP_BASE_URL must be an HTTP(S) origin without a path.")
    if app.hostname.lower() != domain:
        raise ValueError("UBYHOST_APP_BASE_URL host does not match UBYHOST_APP_DOMAIN.")
    public_host = (public.hostname or "").lower()
    if not public_host or not domain.endswith("." + public_host):
        raise ValueError("UBYHOST_APP_DOMAIN must be a subdomain of the public host (passkey RP ID).")
    if production and (app.scheme != "https" or app_port not in {None, 443}):
        raise ValueError("UBYHOST_APP_BASE_URL must use https:// on the default port in production.")


def login_redirect_url(
    hostname: str | None, path: str, query: str, *, public_base_url: str, app_base_url: str,
) -> str:
    """Move only public-host login GETs, including old mailed links, to the app."""
    if app_base_url.rstrip("/") == public_base_url.rstrip("/"):
        return ""
    if (hostname or "").lower() != (urlsplit(public_base_url).hostname or "").lower():
        return ""
    if path not in {"/login", "/login/", "/login/link"}:
        return ""
    target_path = "/login" if path == "/login/" else path
    target = app_base_url.rstrip("/") + target_path
    return target + ("?" + query if query else "")


if __name__ == "__main__":
    try:
        validate_app_url(
            os.environ.get("UBYHOST_PUBLIC_BASE_URL", ""),
            os.environ.get("UBYHOST_APP_BASE_URL", ""),
            os.environ.get("UBYHOST_APP_DOMAIN", ""),
            production=os.environ.get("UBYHOST_DEPLOYMENT") == "production",
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
