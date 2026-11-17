"""Write go/internal/guestcontract/testdata/guest_form_golden.json from the real Python.

Brief 1835. Run from App/ (no database needed):

    .venv/bin/python scripts/guest_form_golden.py

For each made-up case it runs the database-free part of the guest save route
(App/app/routes/guest.py guest_form_save, a new guest): guest_form_raw,
normalise_guest(clamp=False), validate_guest, validate_stay_dates,
validate_stay_date_text, the party-size check, guest_signature_issue with the
English catalog and allow_imported=False, and the legal_ack check. The Go test
in go/internal/guestcontract/ compares the normalised values and the issues.
The clock is pinned to 2026-11-01, as in scripts/validation_golden.py.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from PIL import Image  # noqa: E402

from app import i18n, reporting, validation  # noqa: E402
from app.routes import admin_helpers  # noqa: E402

OUT = APP.parent / "go" / "internal" / "guestcontract" / "testdata" / "guest_form_golden.json"


class PinnedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 1)


validation.date = PinnedDate  # the only clock read in validation.py


def _png_data_url() -> str:
    buf = io.BytesIO()
    Image.new("L", (40, 20), 255).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


SIG = _png_data_url()
STAY = {"reservation_id": 1, "date_from": "2026-11-10", "date_to": "2026-11-12",
        "expected_guests": 2, "registered_guests": 0}
ADULT = {
    "surname": "Novák", "first_name": "Jan", "birth_date": "01.02.1990",
    "nationality": "DEU", "doc_number": "C01X00T47", "res_street": "Hauptstraße 5",
    "res_city": "Berlin", "res_country": "DEU", "signature": SIG, "legal_ack": "1",
}


def case(name, changes=None, stay=None, default_purpose="10"):
    form = dict(ADULT)
    for key, value in (changes or {}).items():
        if value is None:
            form.pop(key, None)
        else:
            form[key] = value
    return {"name": name, "form": form, "stay": {**STAY, **(stay or {})},
            "default_purpose": default_purpose}


CASES = [
    case("valid adult"),
    case("diacritics fold", {"surname": "nguyễn văn", "first_name": "  øyvind  ærø "}),
    case("eszett upper", {"surname": "straße"}),
    case("pipe and newline", {"surname": "Smith|Jones\nBrown", "note": "a|b\r\nc"}),
    case("empty surname", {"surname": ""}),
    case("cyrillic surname", {"surname": "Иванов"}),
    case("surname too long", {"surname": "A" * 60}),
    case("first name too long", {"first_name": "B" * 30}),
    case("birth slashes two digit year", {"birth_date": "01/02/90"}),
    case("birth six digits", {"birth_date": "010224"}),
    case("birth eight digits", {"birth_date": "01021990"}),
    case("birth arabic indic digits", {"birth_date": "٠١٠٢١٩٩٠"}),
    case("birth unknown day and month", {"birth_date": "0.0.1990"}),
    case("birth long day", {"birth_date": "123.4.1990"}),
    case("birth in future", {"birth_date": "01.01.2030"}),
    case("birth missing", {"birth_date": ""}),
    case("doc with spaces", {"doc_number": "ab 12 34 56"}),
    case("doc too short", {"doc_number": "AB1"}),
    case("inpass child with parent doc", {"doc_number": "INPASS", "parent_doc_number": "c01 x00", "birth_date": "01.01.2020", "signature": ""}),
    case("child under 15 no signature", {"birth_date": "05.05.2015", "signature": ""}),
    case("signature imported", {"signature": "imported"}),
    case("signature missing", {"signature": ""}),
    case("signature bad", {"signature": "data:image/png;base64,AAAA"}),
    case("legal ack missing", {"legal_ack": None}),
    case("party size asked and missing", stay={"expected_guests": None}),
    case("party size asked and given", {"party_size": " 3 "}, stay={"expected_guests": None}),
    case("party size too big", {"party_size": "61"}, stay={"expected_guests": None}),
    case("party size not a number", {"party_size": "abc"}, stay={"expected_guests": None}),
    case("residence dash", {"res_city": "Praha–Řepy", "res_country": "cze", "nationality": "deu "}),
    case("czech national", {"nationality": "CZE", "doc_number": "", "res_street": "", "res_city": "", "res_country": ""}),
    case("empty purpose takes default", {"purpose": ""}, default_purpose="10"),
    case("empty purpose no default", {"purpose": ""}, default_purpose=""),
    case("purpose given", {"purpose": "01"}),
    case("unknown nationality", {"nationality": "XXX"}),
    case("visa given", {"visa_number": "v 123 456"}),
    case("stay date unreadable", stay={"date_from": "2026-13-01"}),
    case("everything empty", {k: "" for k in ADULT}),
]


def run(c):
    form = c["form"]
    apartment = {"default_purpose": c["default_purpose"]}
    stay = c["stay"]
    raw = admin_helpers.guest_form_raw(form, apartment)
    values = validation.normalise_guest(raw, clamp=False)
    stay_from, stay_to = stay["date_from"], stay["date_to"]
    signature = admin_helpers.kept_signature(form.get("signature"), None)
    child = validation.certainly_under_age(
        values["birth_date"], validation.parse_iso_date(stay_from), reporting.UNDER_SIGN_AGE
    )
    if child:
        signature = ""
    issues = validation.validate_guest(
        values, validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to), raw=raw
    )
    issues.extend(validation.validate_stay_dates(
        validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to),
        validation.parse_iso_date(stay_from), validation.parse_iso_date(stay_to),
    ))
    issues.extend(validation.validate_stay_date_text(stay_from, stay_to))
    translate = i18n.translator("en")
    if stay["expected_guests"] is None:
        try:
            party_size = int((form.get("party_size") or "").strip())
        except ValueError:
            party_size = 0
        if party_size < 1 or party_size > 60:
            issues.append(validation.Issue("party_size", translate("error_party_size")))
    sig = reporting.guest_signature_issue(signature, translate, allow_imported=False, under_15=child)
    if sig:
        issues.append(sig)
    if not form.get("legal_ack"):
        issues.append(validation.Issue("legal_ack", translate("legal_ack_missing")))
    return {
        "name": c["name"], "form": form, "stay": stay, "default_purpose": c["default_purpose"],
        "values": values,
        "issues": [{"field": i.field, "message": i.message, "severity": i.severity} for i in issues],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"today": "2026-11-01", "cases": [run(c) for c in CASES]}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
