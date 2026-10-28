"""Document scanning (OCR): read a guest's document photo locally, no AI.

Tesseract runs on the server as a subprocess and reads the photo's
machine-readable zone (MRZ); the check digits validate the read before any
field is offered. Nothing leaves the server, and nothing is stored by this
module - the read fields return to the browser as form suggestions only.

Max plan only (the pricing copy promises scanning on Max, and explicitly
not during the trial). Tesseract must be installed (the Docker image ships
it); ``available`` says so per property.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Dict, List, Optional

from . import billing, config, passport_photos, validation

TESSERACT = shutil.which("tesseract") or ""

# Tesseract works best on a modest, greyscale image; the MRZ is high-contrast.
MAX_EDGE = 1568
GREY_QUALITY = 80

_TD3_LEN = 44
_TD1_LEN = 30

# The two characters that may legally appear in an MRZ.
_MRZ_CHARS = re.compile(r"^[A-Z0-9<]*$")

_WEIGHTS = (7, 3, 1)
_VALUE = {ch: i for i, ch in enumerate("0123456789")}
for _i, _ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _VALUE[_ch] = 10 + _i


class BadDocument(ValueError):
    """The upload is not an image this module can read (a PDF, for example)."""


class NoEngine(Exception):
    """Tesseract is not installed on this server."""


class NothingRead(Exception):
    """No valid machine-readable zone was found in the photo."""


def available(apartment) -> bool:
    """True when this property's guest form may offer the scan button.

    The gates: Tesseract installed, and the owner's active Max subscription -
    the trial does not include scanning, matching the pricing copy.
    """
    if not TESSERACT:
        return False
    owner_id = apartment["owner_user_id"] if apartment else None
    if owner_id is None:
        return False
    row = _owner_email_row(owner_id)
    if row and config.AI_TEST_EMAILS:
        # While a test list is set, only listed owners may scan (0376 pattern).
        if row["email"].strip().lower() not in config.AI_TEST_EMAILS:
            return False
    ent = billing.entitlements(int(owner_id))
    return ent.status == "active" and ent.plan == "max"


def _owner_email_row(owner_user_id: int):
    from . import db

    return db.query_one("SELECT email FROM user_account WHERE id = ?", (owner_user_id,))


def prepare_image(content: bytes, content_type: str) -> bytes:
    """A clean, metadata-free greyscale JPEG no larger than MAX_EDGE on a side."""
    import io

    from PIL import Image

    ctype = passport_photos.validate_upload(content, content_type)
    if ctype == passport_photos.ALLOWED_PDF_TYPE:
        raise BadDocument("pdf")
    clean = passport_photos.reencode_image(content)
    with Image.open(io.BytesIO(clean)) as image:
        width, height = image.size
        scale = MAX_EDGE / max(width, height)
        if scale < 1:
            image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))))
        if image.mode != "L":
            image = image.convert("L")
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=GREY_QUALITY)
    return out.getvalue()


def _check_digit(field: str) -> str:
    """The ICAO 7-3-1 check digit character for a field (``<`` counts as 0)."""
    total = 0
    for i, ch in enumerate(field):
        total += _VALUE.get(ch, 0) * _WEIGHTS[i % 3]
    return str(total % 10)


def _mrz_lines(raw_text: str) -> List[str]:
    """Uppercase OCR lines that look like MRZ lines, longest formats first."""
    lines = []
    for line in raw_text.upper().splitlines():
        line = line.strip()
        if not line:
            continue
        # Tesseract commonly confuses O/0 in the MRZ; the zone is A-Z, 0-9 and <.
        cleaned = re.sub(r"[^A-Z0-9<]", "", line)
        if len(cleaned) >= _TD1_LEN and _MRZ_CHARS.match(cleaned):
            lines.append(cleaned)
    return lines


def _fix_o_confusion(field: str, check: str) -> str:
    """The MRZ field and its printed check digit: an O/0 misread resolves one way."""
    if _check_digit(field) == check:
        return field
    for candidate in (field.replace("O", "0"), field.replace("0", "O")):
        if _check_digit(candidate) == check:
            return candidate
    return field


def _clean_field(text: str) -> str:
    return text.replace("<", " ").strip()


def _yymmdd_to_ddmmyyyy(text: str) -> str:
    year, month, day = int(text[:2]), int(text[2:4]), int(text[4:6])
    if year <= 29:
        year += 2000
    else:
        year += 1900
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return ""
    return f"{day:02d}{month:02d}{year}"


def _td3(line1: str, line2: str) -> Optional[Dict[str, str]]:
    """Passport (ICAO 9303 TD3): two 44-character lines."""
    if len(line1) < _TD3_LEN or len(line2) < _TD3_LEN:
        return None
    if line1[0] != "P" or line1[1] != "<":
        return None
    doc = _fix_o_confusion(line2[0:9], line2[9])
    if _check_digit(doc) != line2[9]:
        return None
    birth = _fix_o_confusion(line2[13:19], line2[19])
    if _check_digit(birth) != line2[19]:
        return None
    names = line1[5:].split("<<", 1)
    surname = _clean_field(names[0])
    first_name = _clean_field(names[1]) if len(names) > 1 else ""
    birth = _yymmdd_to_ddmmyyyy(birth)
    if not surname or not birth:
        return None
    return {
        "surname": validation.normalise_name(surname),
        "first_name": validation.normalise_name(first_name),
        "birth_date": birth,
        "nationality": line2[10:13],
        "doc_number": validation.normalise_document(doc),
    }


def _td1(line1: str, line2: str, line3: str) -> Optional[Dict[str, str]]:
    """ID card (ICAO 9303 TD1): three 30-character lines."""
    for line in (line1, line2, line3):
        if len(line) < _TD1_LEN:
            return None
    # TD1 line 1: doc code(2) issuing state(3) doc number(9) check(1).
    doc = _fix_o_confusion(line1[5:14], line1[14])
    if _check_digit(doc) != line1[14]:
        return None
    birth = _fix_o_confusion(line2[0:6], line2[6])
    if _check_digit(birth) != line2[6]:
        return None
    names = line3.split("<<", 1)
    surname = _clean_field(names[0])
    first_name = _clean_field(names[1]) if len(names) > 1 else ""
    birth = _yymmdd_to_ddmmyyyy(birth)
    if not surname or not birth:
        return None
    return {
        "surname": validation.normalise_name(surname),
        "first_name": validation.normalise_name(first_name),
        "birth_date": birth,
        "nationality": line2[15:18],
        "doc_number": validation.normalise_document(doc),
    }


def parse_mrz(raw_text: str) -> Dict[str, str]:
    """Form values from an MRZ, or raise ``NothingRead``.

    Tries TD3 (passport, 2x44) then TD1 (ID card, 3x30), and only returns a
    read whose document-number and birth-date check digits validate.
    """
    lines = _mrz_lines(raw_text)
    for i in range(len(lines) - 1):
        values = _td3(lines[i], lines[i + 1])
        if values:
            return values
    for i in range(len(lines) - 2):
        values = _td1(lines[i], lines[i + 1], lines[i + 2])
        if values:
            return values
    raise NothingRead()


def run_tesseract(jpeg: bytes) -> str:
    """Tesseract's raw text for one image. Tests replace this function."""
    import tempfile
    from pathlib import Path

    if not TESSERACT:
        raise NoEngine()
    with tempfile.TemporaryDirectory(prefix="ubyocr-") as tmp:
        image_path = Path(tmp) / "doc.jpg"
        image_path.write_bytes(jpeg)
        result = subprocess.run(
            [TESSERACT, str(image_path), "stdout", "-l", "eng", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=25,
        )
    if result.returncode != 0:
        raise NothingRead()
    return result.stdout


def read_document(jpeg: bytes) -> Dict[str, str]:
    """The document's fields as normalised form values; nothing is stored."""
    raw = run_tesseract(jpeg)
    values = parse_mrz(raw)
    countries = validation.country_codes()
    if values["nationality"] not in countries:
        values["nationality"] = ""
    return values


__all__ = [
    "BadDocument",
    "NoEngine",
    "NothingRead",
    "available",
    "prepare_image",
    "parse_mrz",
    "run_tesseract",
    "read_document",
    "TESSERACT",
]
