"""Shared parsing and redirect helpers for host-facing routes."""
from __future__ import annotations

from urllib.parse import quote

from fastapi.responses import RedirectResponse


def back(path: str, msg: str = "", err: str = "") -> RedirectResponse:
    query = []
    if msg:
        query.append(f"msg={quote(msg)}")
    if err:
        query.append(f"err={quote(err)}")
    if not query:
        return RedirectResponse(path, status_code=303)
    qs = "&".join(query)
    if "#" in path:
        base, fragment = path.split("#", 1)
        sep = "&" if "?" in base else "?"
        return RedirectResponse(f"{base}{sep}{qs}#{fragment}", status_code=303)
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep}{qs}", status_code=303)


def form_str(form, key: str, default: str = "") -> str:
    value = form.get(key)
    return (value or default).strip() if isinstance(value, str) else default
