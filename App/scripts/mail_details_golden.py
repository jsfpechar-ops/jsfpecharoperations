#!/usr/bin/env python3
"""Write the Python oracle for the Go receipt details renderer (brief 2067).

Dev tool, never run in production. Invented data only: a fixed test Fernet key,
no .env, no database. db.query and db.query_one are replaced by in-memory rows,
and the real mail_notify.render_receipt_details produces the expected text and
HTML. The stub returns doc_number already decrypted (as db.query does after
hydration); the Fernet token is written too, so Go can seed the same stored form.
Output: go/internal/maildetails/testdata/receipt_golden.json, byte-stable.
Usage: mail_details_golden.py [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "maildetails" / "testdata" / "receipt_golden.json"

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
    return FERNET._encrypt_from_parts(text.encode("utf-8"), FIXED_TS, FIXED_IV).decode("ascii")


CLAIM_AT = "2026-11-13T09:00:00Z"
BEFORE_CLAIM = "2026-11-12T08:00:00Z"
AFTER_CLAIM = "2026-11-13T10:00:00Z"


def guest(res_id: int, idx: int, first: str, surname: str, doc: str, entered_by: str,
          created_at: str, is_lead: bool) -> dict:
    return {
        "id": res_id * 10 + idx,
        "reservation_id": res_id,
        "first_name": first,
        "surname": surname,
        "doc_number": doc,
        "doc_number_enc": enc(doc),
        "entered_by": entered_by,
        "created_at": created_at,
        "is_lead": 1 if is_lead else 0,
    }


def lead_and_host(res_id: int) -> list:
    return [
        guest(res_id, 0, "Ada", "Tester", "AB12345CD", "guest", AFTER_CLAIM, True),
        guest(res_id, 1, "Bo", "", "ZZ999999", "host", AFTER_CLAIM, False),
    ]


# (name, reservation_id, lang, claimed_at or None, guests, seeded)
CASES = [
    ("lead_typed_here_9_chars", 101, "en", CLAIM_AT, lead_and_host(101), True),
    ("typed_here_3_chars", 102, "en", CLAIM_AT,
     [guest(102, 0, "Cy", "Dee", "X1Y", "guest", AFTER_CLAIM, True)], True),
    ("host_entered_name_only", 103, "en", CLAIM_AT,
     [guest(103, 0, "Eve", "Host", "123456789", "host", AFTER_CLAIM, True)], True),
    ("typed_before_claim_name_only", 104, "en", CLAIM_AT,
     [guest(104, 0, "Fay", "Early", "FAY00001", "guest", BEFORE_CLAIM, True)], True),
    ("no_claim_row_name_only", 105, "en", None,
     [guest(105, 0, "Gus", "Noclaim", "NOCLAIM1", "guest", AFTER_CLAIM, True)], True),
    ("unnamed_guest", 106, "en", CLAIM_AT,
     [guest(106, 0, "", "", "", "host", AFTER_CLAIM, True)], True),
    ("claim_no_guests", 107, "en", CLAIM_AT, [], True),
    ("stay_does_not_exist", 108, "en", None, [], False),
    ("lead_typed_here_cs", 109, "cs", CLAIM_AT, lead_and_host(109), True),
    ("lead_typed_here_de", 110, "de", CLAIM_AT, lead_and_host(110), True),
    ("html_escaping", 111, "en", CLAIM_AT,
     [guest(111, 0, "Gi<b>", "A&B", "Q7654321", "guest", AFTER_CLAIM, True)], True),
]


def install_stub(claims: dict, guests: dict) -> None:
    def query_one(sql, params=()):
        if "FROM reservation_claim" in sql:
            return claims.get(int(params[0]))
        raise AssertionError(f"unexpected query_one: {sql}")

    def query(sql, params=()):
        if "FROM guest" in sql:
            rows = guests.get(int(params[0]), [])
            return sorted(rows, key=lambda r: (-r["is_lead"], r["id"]))
        raise AssertionError(f"unexpected query: {sql}")

    db.query_one = query_one
    db.query = query


def build() -> dict:
    out = []
    for name, res_id, lang, claimed_at, guests, seeded in CASES:
        claims = {res_id: {"claimed_at": claimed_at}} if claimed_at is not None else {}
        rows = {res_id: guests} if seeded else {}
        install_stub(claims, rows)
        text = mail_notify.render_receipt_details(res_id, lang=lang, as_html=False)
        html = mail_notify.render_receipt_details(res_id, lang=lang, as_html=True)
        out.append({
            "name": name,
            "reservation_id": res_id,
            "lang": lang,
            "claimed_at": claimed_at,
            "seeded": seeded,
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
