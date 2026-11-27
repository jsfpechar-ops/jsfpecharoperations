#!/usr/bin/env python3
"""Write the Python oracle for the Go guest-details renderer (brief 2068).

Dev tool, never run in production. Invented data only: a fixed test Fernet key,
no .env, no database. db.query and db.query_one are replaced by in-memory rows,
and the real mail_notify.render_guest_details produces expected text and HTML.
Output: go/internal/maildetails/testdata/guest_details_golden.json, byte-stable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "maildetails" / "testdata" / "guest_details_golden.json"

FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="  # invented test key
FIXED_TS = 1700000000
FIXED_IV = bytes(range(16))

os.environ["UBYHOST_DATA_KEYS"] = FERNET_KEY
os.environ["UBYHOST_DATA_KEY_LEGACY"] = "0"
os.environ["UBYHOST_MAIL_BACKEND"] = "console"
os.environ["UBYHOST_DEPLOYMENT"] = "development"
os.environ["UBYHOST_MAIL_FROM"] = "noreply@mail.example.test"
os.environ.setdefault("UBYHOST_SECRET_KEY", "test-secret-key-not-for-real-use")
os.environ.setdefault("UBYHOST_DATA_DIR", "/tmp/ubyhost-mail-details-golden")
os.environ.setdefault("UBYHOST_DB", "/tmp/ubyhost-mail-details-golden/unused.db")
sys.path.insert(0, str(APP_DIR))

from cryptography.fernet import Fernet  # noqa: E402

from app import db, mail_notify  # noqa: E402

FERNET = Fernet(FERNET_KEY.encode("ascii"))


def enc(text: str) -> str:
    if not text:
        return ""
    return FERNET._encrypt_from_parts(text.encode("utf-8"), FIXED_TS, FIXED_IV).decode("ascii")


def make_guest(
    res_id: int,
    idx: int,
    *,
    first: str = "Ada",
    surname: str = "Tester",
    nationality: str = "DEU",
    submit_state: str = "pending",
    doc_type: str = "pas",
    doc_number: str = "AB12345CD",
    birth_date: str = "1990-05-14",
    res_street: str = "Main 1",
    res_city: str = "Berlin",
    res_country: str = "DEU",
    is_lead: bool = True,
    encrypt: bool = True,
    archived: bool = False,
) -> dict:
    return {
        "id": res_id * 10 + idx,
        "reservation_id": res_id,
        "first_name": first,
        "surname": surname,
        "nationality": nationality,
        "submit_state": submit_state,
        "doc_type": doc_type,
        "doc_number": doc_number,
        "doc_number_enc": enc(doc_number) if encrypt else "",
        "birth_date": birth_date,
        "birth_date_enc": enc(birth_date) if encrypt else "",
        "res_street": res_street,
        "res_street_enc": enc(res_street) if encrypt else "",
        "res_city": res_city,
        "res_city_enc": enc(res_city) if encrypt else "",
        "res_country": res_country,
        "is_lead": 1 if is_lead else 0,
        "archived_at": "2026-06-03T12:00:00Z" if archived else None,
    }


CASES = [
    ("full_on_dpa_1_8_en", 201, "en", True, 1, ["1.8"], [
        make_guest(201, 0, first="Bo", surname="Second", is_lead=False, submit_state="sent", doc_type="P", doc_number="X1Y"),
        make_guest(201, 1, first="Ada", surname="Lead", is_lead=True, submit_state="pending", doc_type="pas", doc_number="AB12345CD"),
    ]),
    ("full_on_dpa_1_10_cs", 202, "cs", True, 1, ["1.10"], [
        make_guest(202, 0, first="Eva", surname="Novakova", nationality="CZE", submit_state="not_required", doc_type="ID", doc_number="123456789", birth_date="1988-12-03"),
    ]),
    ("switch_off_with_dpa_1_8", 203, "en", True, 0, ["1.8"], [
        make_guest(203, 0, submit_state="error"),
    ]),
    ("switch_on_without_dpa", 204, "en", True, 1, [], [
        make_guest(204, 0, submit_state="blocked"),
    ]),
    ("switch_on_dpa_1_7_too_old", 205, "en", True, 1, ["1.7"], [
        make_guest(205, 0, submit_state="sent"),
    ]),
    ("plaintext_legacy_and_aliases", 206, "en", True, 1, ["2.0"], [
        make_guest(206, 0, first="", surname="", nationality="", submit_state="custom_state", doc_type="xyz", doc_number="99887766", birth_date="01011990", res_street="", res_city="Prague", res_country="", encrypt=False),
        make_guest(206, 1, first="Cy", surname="Unknown", nationality="ZZZ", submit_state="", doc_type="", doc_number="", birth_date="", res_street="", res_city="", res_country="", is_lead=False, encrypt=False),
        make_guest(206, 2, first="Archived", surname="Skip", is_lead=False, archived=True),
    ]),
    ("html_escaping_and_lang_fallback", 207, "de", True, 1, ["1.8"], [
        make_guest(207, 0, first="Gi<b>", surname="A&B", res_street="Oak <1>", res_city="R&D", res_country="DEU", doc_number="Q7654321"),
    ]),
    ("unsupported_lang_cs_locale", 208, "cs-CZ", True, 1, ["1.8"], [
        make_guest(208, 0, nationality="GBR", doc_type="trvaly_pobyt"),
    ]),
    ("stay_with_no_active_guests", 209, "en", True, 1, ["1.8"], [
        make_guest(209, 0, archived=True),
    ]),
    ("missing_stay_en", 210, "en", False, 1, ["1.8"], []),
    ("missing_stay_cs", 211, "cs", False, 1, ["1.8"], []),
]


def install_stub(stays: dict, guests: dict, switches: dict, dpa_versions: dict) -> None:
    def query_one(sql, params=()):
        if "FROM reservation r" in sql:
            return stays.get(int(params[0]))
        if "FROM user_account" in sql:
            uid = int(params[0])
            return {"guest_details_mail": switches.get(uid, 0)}
        raise AssertionError(f"unexpected query_one: {sql}")

    def query(sql, params=()):
        if "FROM guest" in sql:
            rows = [r for r in guests.get(int(params[0]), []) if not r.get("archived_at")]
            return sorted(rows, key=lambda r: (-r["is_lead"], r["id"]))
        if "FROM legal_acceptance" in sql:
            uid = int(params[0])
            return [{"document": "dpa", "version": v, "accepted_at": "2026-06-01T00:00:00Z", "method": "clickwrap"} for v in dpa_versions.get(uid, [])]
        if "FROM codelist" in sql:
            return []
        raise AssertionError(f"unexpected query: {sql}")

    db.query_one = query_one
    db.query = query


def build() -> dict:
    out = []
    for name, res_id, lang, seeded, sw, dpas, guests in CASES:
        owner_id = 900000 + res_id
        stays = {res_id: {"id": res_id, "owner_user_id": owner_id}} if seeded else {}
        install_stub(stays, {res_id: guests} if seeded else {}, {owner_id: sw}, {owner_id: dpas})
        text = mail_notify.render_guest_details(res_id, lang=lang, as_html=False)
        html = mail_notify.render_guest_details(res_id, lang=lang, as_html=True)
        out.append({
            "name": name,
            "reservation_id": res_id,
            "lang": lang,
            "seeded": seeded,
            "guest_details_mail": sw,
            "dpa_versions": dpas,
            "guests": guests,
            "expect_text": text,
            "expect_html": html,
        })
    return {"fernet_key": FERNET_KEY, "cases": out}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    data = json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(data, encoding="utf-8")
    print(f"wrote {out} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
