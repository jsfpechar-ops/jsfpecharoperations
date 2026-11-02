"""Write go/internal/validation/testdata/golden.json from the real Python validation.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/validation_golden.py

The Go test in go/internal/validation/ compares every case byte for byte.
The clock is pinned to 2026-11-01: validation.py reads date.today() through
its module-level name ``date``, which is swapped for a subclass here.
"""

from __future__ import annotations

import base64
import io
import json
import struct
import sys
import zlib
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from PIL import Image  # noqa: E402

from app import reporting, validation  # noqa: E402

OUT = APP.parent / "go" / "internal" / "validation" / "testdata" / "golden.json"


class PinnedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 1)


validation.date = PinnedDate  # the only clock read in validation.py

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def png(width: int, height: int) -> bytes:
    """Deterministic greyscale PNG of zeros (no PIL encoder involved)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = (b"\x00" + b"\x00" * width) * height
    return PNG_MAGIC + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 255, 255)).save(buf, "JPEG", quality=50)
    return buf.getvalue()


def data_url(mime: str, content: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(content).decode("ascii")


VALID_PNG = png(4, 4)
JPEG_BYTES = jpeg()
GUEST_FIELDS = (
    "surname", "first_name", "birth_date", "nationality", "doc_number", "visa_number",
    "res_street", "res_city", "res_country", "purpose", "note",
    "stay_from", "stay_to", "signature_png",
)
BASE_GUEST = {
    "surname": "NOVAK", "first_name": "JAN", "birth_date": "01011990",
    "nationality": "DEU", "doc_number": "C01X00T47", "visa_number": "",
    "res_street": "Hauptstrasse 5", "res_city": "Berlin", "res_country": "DEU",
    "purpose": "99", "note": "", "stay_from": "", "stay_to": "",
    "signature_png": data_url("image/png", VALID_PNG),
}
RES = {"date_from": "2026-10-20", "date_to": "2026-10-25"}
NORES = {"date_from": "", "date_to": ""}

guest_cases: list = []


def g(name, res=None, raw=None, **over):
    row = dict(BASE_GUEST)
    row.update(over)
    guest_cases.append((name, row, res or RES, raw))


def emit_guest(name, row, res, raw):
    guest = {k: row.get(k) or "" for k in GUEST_FIELDS}
    if raw is None:
        issues = reporting.guest_issues(guest, res)
        complete = reporting.guest_is_complete(guest, res)
    else:
        start, end = reporting._stay_dates(guest, res)
        issues = validation.validate_guest(reporting.guest_dict(guest), start, end, raw=raw)
        complete = not validation.errors_only(issues)
    return {
        "name": name,
        "guest": {k: guest[k] for k in GUEST_FIELDS},
        "date_from": res["date_from"],
        "date_to": res["date_to"],
        "raw": raw,
        "issues": [[i.field, i.message, i.severity] for i in issues],
        "complete": complete,
    }


# --- guest cases -------------------------------------------------------------
g("valid")
g("valid_czech_nationality", nationality="CZE", res_country="CZE")
g("valid_lowercase_codes", nationality="deu", res_country="gbr")
g("valid_visa", visa_number="V123456")
g("valid_visa_15", visa_number="V" * 15)
g("valid_inpass_with_note", doc_number="INPASS", note="Rodic C01X00T47")
g("valid_birth_year_0000", birth_date="01010000")
g("valid_birth_day_0", birth_date="00011990")
g("valid_birth_1900", birth_date="01011900")
g("valid_birth_today", birth_date="01112026", res=NORES)
g("valid_stay_from_guest", stay_from="2026-10-22")
g("valid_stay_iso_with_time", stay_from="2026-10-22T08:00:00")
g("valid_purpose_00", purpose="00")
g("valid_signature_jpeg", signature_png=data_url("image/jpeg", JPEG_BYTES))
g("valid_signature_png_1x1", signature_png=data_url("image/png", png(1, 1)))
g("stay_from_invalid_uses_reservation", stay_from="2026-02-30")
g("stay_from_text_uses_reservation", stay_from="22.10.2026")
g("no_reservation_dates", res=NORES)
g("stay_to_before_from", res={"date_from": "2026-10-25", "date_to": "2026-10-20"})
g("stay_to_equal_from", res={"date_from": "2026-10-20", "date_to": "2026-10-20"})
g("stay_to_from_guest_before", stay_to="2026-10-10")
g("surname_empty", surname="")
g("surname_empty_non_latin_raw", surname="", raw={"surname": "Иван"})
g("surname_blank_raw", surname="", raw={"surname": "   "})
g("first_name_non_latin_raw", first_name="", raw={"first_name": "李"})
g("surname_50", surname="A" * 50)
g("surname_51", surname="A" * 51)
g("surname_pipe", surname="NO|VAK")
g("surname_newline", surname="NO\nVAK")
g("surname_50_unicode", surname="Ř" * 50)
g("surname_51_unicode", surname="Ř" * 51)
g("first_name_empty", first_name="")
g("first_name_24", first_name="B" * 24)
g("first_name_25", first_name="B" * 25)
g("first_name_cr", first_name="J\rN")
g("birth_empty", birth_date="")
g("birth_six_digits", birth_date="010199")
g("birth_four_chars", birth_date="0101")
g("birth_dashed", birth_date="01-01-1990")
g("birth_letters", birth_date="0101ABCD")
g("birth_year_1899", birth_date="01011899")
g("birth_month_13", birth_date="01131990")
g("birth_day_32", birth_date="32011990")
g("birth_not_exist", birth_date="31021990")
g("birth_future", birth_date="01012030", res=NORES)
g("birth_tomorrow", birth_date="02112026", res=NORES)
g("birth_after_arrival", birth_date="21102026")
g("nationality_empty", nationality="")
g("nationality_unknown", nationality="XXX")
g("nationality_two_letters", nationality="GB")
g("nationality_czech", nationality="CZE")
g("doc_empty", doc_number="")
g("doc_inpass_no_note", doc_number="INPASS", note="")
g("doc_5", doc_number="12345")
g("doc_6", doc_number="123456")
g("doc_30", doc_number="A" * 30)
g("doc_31", doc_number="A" * 31)
g("doc_newline", doc_number="AB\n123456")
g("visa_16", visa_number="V" * 16)
g("visa_pipe", visa_number="V|1234567")
g("street_empty", res_street="")
g("city_empty", res_city="")
g("country_empty", res_country="")
g("all_residence_empty", res_street="", res_city="", res_country="")
g("street_42", res_street="S" * 42)
g("street_43", res_street="S" * 43)
g("street_digits", res_street="12345")
g("city_digits", res_city="0123")
g("city_43", res_city="C" * 43)
g("city_pipe", res_city="BR|NO")
g("country_unknown", res_country="XXX")
g("purpose_empty", purpose="")
g("purpose_unknown", purpose="98")
g("note_pipe", note="a|b")
g("note_cr", note="a\rb")
g("note_255", note="N" * 255)
g("note_256", note="N" * 256)
g("signature_empty", signature_png="")
g("signature_spaces_only", signature_png="   ")
g("signature_imported", signature_png="imported")
g("signature_imported_padded", signature_png="  imported  ")
g("signature_svg", signature_png="data:image/svg+xml;base64,PHN2Zz4=")
g("signature_gif", signature_png=data_url("image/gif", b"GIF89a"))
g("signature_text_plain", signature_png="data:text/plain;base64,QUJD")
g("signature_bad_padding", signature_png="data:image/png;base64,QUJ")
g("signature_bad_chars", signature_png="data:image/png;base64,@@@@")
g("signature_not_data_url", signature_png="iVBORw0KGgo=")
g("signature_png_wrong_magic", signature_png=data_url("image/png", b"not a png at all"))
g("signature_jpeg_bytes_as_png", signature_png=data_url("image/png", JPEG_BYTES))
g("signature_png_truncated", signature_png=data_url("image/png", VALID_PNG[:20]))
g("signature_png_width_6001", signature_png=data_url("image/png", png(6001, 1)))
g("signature_png_pixels_12m", signature_png=data_url("image/png", png(3500, 3500)))
g("signature_payload_over_cap", signature_png="data:image/png;base64,"
  + base64.b64encode(PNG_MAGIC + b"\x00" * 300000).decode("ascii"))
g("signature_decoded_over_cap", signature_png=data_url("image/png", PNG_MAGIC + b"\x00" * (262146 - 8)))
g("stacked_errors", surname="", birth_date="", nationality="", doc_number="",
  purpose="", note="a|b", signature_png="")

# --- apartment cases ---------------------------------------------------------
BASE_AP = {
    "uby_idub": "ABCDEFGH1234", "uby_mark": "AAKLI", "uby_name": "Penzion U Lesa",
    "uby_contact": "Jan Novak", "addr_okres": "Praha", "addr_obec": "Praha",
    "addr_obec_cast": "", "addr_street": "Dlouha", "addr_house_no": "12",
    "addr_orient_no": "3a", "addr_zip": "11000", "uby_ws_user": "UBY-WS_AAKLI",
    "uby_ws_password": "secret", "legal_entity_id": "5", "data_controller_entity_id": "",
}
ap_cases: list = []


def ap(name, **over):
    row = dict(BASE_AP)
    row.update(over)
    ap_cases.append((name, row))


ap("valid")
ap("valid_no_orient", addr_orient_no="")
ap("valid_contact_empty", uby_contact="")
ap("valid_idub_14", uby_idub="ABCDEFGHIJKLMN")
ap("valid_mark_6", uby_mark="AB1234")
ap("valid_name_35", uby_name="N" * 35)
ap("valid_name_35_unicode", uby_name="Ř" * 35)
ap("valid_house_E", addr_house_no="E12")
ap("valid_house_lower_e", addr_house_no="12e")
ap("valid_zip_spaced", addr_zip="112 00")
ap("valid_ws_test_login", uby_ws_user="uby-tws1ab45")
ap("valid_ws_no_underscore", uby_ws_user="UBY-WSab12cd")
ap("valid_orient_3_letter", addr_orient_no="123Z")
ap("idub_empty", uby_idub="")
ap("idub_short", uby_idub="ABC")
ap("idub_15", uby_idub="ABCDEFGHIJKLMNO")
ap("idub_hyphen", uby_idub="ABCD-EFGH1234")
ap("mark_empty", uby_mark="")
ap("mark_4", uby_mark="AB12")
ap("mark_7", uby_mark="AB12345")
ap("name_empty", uby_name="")
ap("name_36", uby_name="N" * 36)
ap("contact_51", uby_contact="C" * 51)
ap("okres_33", addr_okres="O" * 33)
ap("obec_49", addr_obec="O" * 49)
ap("obec_cast_49", addr_obec_cast="O" * 49)
ap("street_49", addr_street="S" * 49)
ap("house_empty", addr_house_no="")
ap("house_5_digits", addr_house_no="12345")
ap("house_letters", addr_house_no="1A")
ap("orient_4_digits", addr_orient_no="1234")
ap("orient_two_letters", addr_orient_no="12ab")
ap("zip_empty", addr_zip="")
ap("zip_4", addr_zip="1234")
ap("zip_letters", addr_zip="ABCDE")
ap("obec_empty", addr_obec="")
ap("ws_empty", uby_ws_user="")
ap("ws_web_form_login", uby_ws_user="ub1234567")
ap("ws_short_suffix", uby_ws_user="UBY-WS_AB")
ap("password_empty", uby_ws_password="")
ap("legal_no_controller", legal_entity_id="", data_controller_entity_id="")
ap("legal_with_controller", legal_entity_id="", data_controller_entity_id="7")
ap("all_empty", **{k: "" for k in BASE_AP})


def emit_ap(name, row):
    return {
        "name": name,
        "row": row,
        "issues": [[i.field, i.message, i.severity] for i in validation.validate_apartment(row)],
    }


def main() -> None:
    data = {
        "today": "2026-11-01",
        "guest": [emit_guest(*c) for c in guest_cases],
        "apartment": [emit_ap(n, r) for n, r in ap_cases],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"guest cases {len(data['guest'])}, apartment cases {len(data['apartment'])}")
    print(f"wrote {OUT.relative_to(APP.parent)}")


if __name__ == "__main__":
    main()
