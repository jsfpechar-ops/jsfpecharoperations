"""Czech bank-account helpers and QR Platba (SPAYD 1.0) payloads.

Shared by the invoice builder and the invoice PDF. UbyHost never processes a
payment: these helpers only format the host's own account into a QR a Czech
banking app can read.
"""
from __future__ import annotations

import base64
import io
import re
import unicodedata
from decimal import Decimal

import qrcode
from qrcode.constants import ERROR_CORRECT_M

_WEIGHTS = (6, 3, 7, 9, 10, 5, 8, 4, 2, 1)
_ACCOUNT_RE = re.compile(r"^(?:(\d{1,6})-)?(\d{2,10})/(\d{4})$")
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$")
_QR_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:")


def _mod11_ok(digits: str) -> bool:
    padded = digits.zfill(10)
    return sum(int(d) * w for d, w in zip(padded, _WEIGHTS)) % 11 == 0


def _iban_ok(iban: str) -> bool:
    moved = iban[4:] + iban[:4]
    return int("".join(str(int(ch, 36)) for ch in moved)) % 97 == 1


def normalise_account(raw: str) -> tuple:
    """Return (display_account, iban). Raise ValueError on bad input."""
    text = re.sub(r"\s+", "", raw or "").upper()
    if _IBAN_RE.match(text):
        if not _iban_ok(text):
            raise ValueError("iban_checksum")
        return text, text
    match = _ACCOUNT_RE.match(text)
    if not match:
        raise ValueError("account_format")
    prefix, number, bank = match.group(1) or "", match.group(2), match.group(3)
    if (prefix and not _mod11_ok(prefix)) or not _mod11_ok(number):
        raise ValueError("account_checksum")
    bban = bank + prefix.zfill(6) + number.zfill(10)
    check = 98 - int(bban + "123500") % 97
    display = f"{prefix}-{number}/{bank}" if prefix else f"{number}/{bank}"
    return display, f"CZ{check:02d}{bban}"


def format_iban(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def ascii_upper(text: str, limit: int) -> str:
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).upper()
    plain = "".join(ch if ch in _QR_CHARS else " " for ch in plain)
    plain = re.sub(r" +", " ", plain).strip()
    return plain[:limit].rstrip()


def spayd(iban: str, amount, vs: str, message: str, bic: str = "") -> str:
    account = iban + (f"+{bic.upper()}" if bic else "")
    parts = [
        "SPD", "1.0",
        f"ACC:{account}",
        f"AM:{Decimal(amount):.2f}",
        "CC:CZK",
        f"X-VS:{vs}",
        f"MSG:{ascii_upper(message, 60)}",
    ]
    return "*".join(parts)


def qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=6, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image().save(output, format="PNG")
    return output.getvalue()


def qr_data_uri(payload: str) -> str:
    return "data:image/png;base64," + base64.b64encode(qr_png_bytes(payload)).decode()
