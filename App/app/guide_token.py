"""The QR token of a property's guest guide (brief 0294).

One token per property, 192 random bits, stored in ``apartment.guide_token``.
It opens ``/g/{token}``: the "everyone" cards only, for anyone standing at the
property. It is never the stay link token, so rotating it (brief 0295) does not
break a single stay link, and a leaked QR photo never opens a registration form.
"""
from __future__ import annotations

import io
import secrets
from typing import Any, Dict, Optional

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from . import db

TOKEN_BYTES = 24  # 192 bits, 32 url-safe characters


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def current(apartment_id: int) -> Optional[str]:
    row = db.query_one("SELECT guide_token FROM apartment WHERE id = ?", (apartment_id,))
    return row["guide_token"] if row and row["guide_token"] else None


def ensure(apartment_id: int) -> str:
    """The property's token, created on first use. Never replaces one that exists."""
    token = current(apartment_id)
    if token:
        return token
    token = new_token()
    db.execute(
        "UPDATE apartment SET guide_token = ? WHERE id = ? AND guide_token IS NULL",
        (token, apartment_id),
    )
    return current(apartment_id) or token


def rotate(apartment_id: int) -> str:
    """A fresh token; the old QR code stops working at once (UI in brief 0295)."""
    token = new_token()
    db.update("apartment", apartment_id, {"guide_token": token})
    return token


def apartment_for(token: str) -> Optional[Dict[str, Any]]:
    """The live property behind a QR token, or None for anything else.

    Length-checked first so a database lookup never runs for junk, and the
    row is matched exactly: an old, rotated token matches nothing.
    """
    if not token or len(token) > 64:
        return None
    row = db.query_one(
        "SELECT * FROM apartment WHERE guide_token = ? AND active = 1 AND archived_at IS NULL",
        (token,),
    )
    return dict(row) if row else None

def qr_png(url: str) -> bytes:
    """A print-sized PNG of the QR code (brief 0295): about 6 cm at 300 dpi."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=20, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    out = io.BytesIO()
    qr.make_image().save(out, format="PNG")
    return out.getvalue()
