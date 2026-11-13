"""Write go/internal/web/exports/testdata/exports_golden.json from the real Python.

Briefs 1320 and 1321. Run from App/ with a PostgreSQL server you may create
databases on (the script makes and drops ``ubyhost_exports_golden``):

    UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres \\
        .venv/bin/python scripts/exports_golden.py          write the files
    ... scripts/exports_golden.py --check                   exit 1 when stale

It applies the PostgreSQL schema, seeds the rows in SEED, sends every request
in CASES through the FastAPI app (TestClient) and records the status, the
headers the routes set, the body (a zip as its entry names and contents) and
the audit rows each request wrote. datetime.now() in the routes and
db.utcnow() are frozen at NOW. Session cookies are minted per run, so the
golden records only who is signed in. go/internal/web/exports/exports_test.go
seeds the same rows, sends the same requests to the Go handlers and compares.
It also writes go/internal/web/exports/i18n.json from i18n_keys.txt, as
scripts/go_host_i18n.py does for go/internal/*/.

PostgreSQL, not SQLite: the Go routes run on PostgreSQL, and SELECT * column
order and boolean results differ between the two backends.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

APP = Path(__file__).resolve().parents[1]
PKG = APP.parent / "go" / "internal" / "web" / "exports"
OUT = PKG / "testdata" / "exports_golden.json"
DB_NAME = "ubyhost_exports_golden"

# Test-only keys: they protect nothing but these fixtures.
SECRET = "exports-golden-secret-0123456789-abcdef"
DATA_KEY = base64.urlsafe_b64encode(b"exports-golden-fernet-key-00000!").decode()
NOW = "2026-11-13T12:00:00+00:00"
NOW_LOCAL = datetime(2026, 11, 13, 12, 0, 0)
FIXED_IV = b"0123456789abcdef"
FIXED_TS = 1798761600

PDF_A = base64.b64encode(b"%PDF-1.4 receipt A\n").decode()
PDF_B = base64.b64encode(b"%PDF-1.4 receipt B\n").decode()
PDF_C = base64.b64encode(b"%PDF-1.4 receipt C\n").decode()
PDF_ERR = base64.b64encode(b"%PDF-1.4 errors\n").decode()
STAMP = "2026-01-01T00:00:00+00:00"
# A 1x1 PNG: a signature validation.parse_signature_data_url accepts.
SIGNATURE = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
             "DwAChwGA60e6kgAAAABJRU5ErkJggg==")


def token(text: str) -> str:
    """A Fernet token with a fixed time and IV, so the golden is stable."""
    from cryptography.fernet import Fernet

    return Fernet(DATA_KEY)._encrypt_from_parts(text.encode("utf-8"), FIXED_TS, FIXED_IV).decode()


def seed() -> list:
    users = [
        [1, "owner@example.test", "x", "host", 1, 0, 0, 0, STAMP],
        [2, "other@example.test", "x", "host", 1, 0, 0, 0, STAMP],
        [3, "admin@example.test", "x", "admin", 1, 0, 0, 0, STAMP],
    ]
    acceptance = []
    n = 0
    for uid in (1, 2, 3):
        # Both 1.7 and 1.8: go/internal/session defaults every document to
        # 1.7, config.py has privacy and dpa at 1.8 (see brief 1320 risks).
        for doc in ("terms", "privacy", "dpa"):
            for version in ("1.7", "1.8"):
                n += 1
                acceptance.append([n, uid, doc, version, STAMP, "clickwrap"])
    return [
        {
            "table": "user_account",
            "columns": ["id", "username", "password_hash", "role", "active",
                        "must_change_password", "session_version", "totp_enabled", "created_at"],
            "rows": users,
        },
        {
            "table": "legal_acceptance",
            "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
            "rows": acceptance,
        },
        {
            "table": "apartment",
            "columns": ["id", "owner_user_id", "internal_name", "uby_idub", "created_at"],
            "rows": [
                [7, 1, "Byt Dole", "IDUB7", STAMP],
                [6, 1, "=Attic", None, STAMP],
                [8, 2, "Other Flat", "IDUB8", STAMP],
            ],
        },
        {
            "table": "reservation",
            "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to", "summary",
                        "declared_guests", "expected_guests_override", "lead_reduced_guests",
                        "guest_email", "status", "archived_at", "created_at", "updated_at"],
            "rows": [
                [1, 7, "ical", "u1", "2026-05-01", "2026-05-04", "Anna; \"Ann\" B", 3, None, None,
                 "anna@example.test", "confirmed", None, STAMP, STAMP],
                [2, 7, "manual", "u2", "2026-05-10", "2026-05-12", "=SUM(A1)", 4, 2, None,
                 None, "confirmed", None, STAMP, STAMP],
                [3, 8, "ical", "u3", "2026-05-02", "2026-05-03", "Other", 1, None, None,
                 None, "confirmed", None, STAMP, STAMP],
                [4, 7, "demo", "u4", "2026-05-02", "2026-05-03", "Demo", 2, None, None,
                 None, "confirmed", None, STAMP, STAMP],
                [5, 7, "ical", "u5", "2026-05-02", "2026-05-03", "Archived", 2, None, None,
                 None, "confirmed", STAMP, STAMP, STAMP],
                [6, 6, "ical", "u6", "2026-06-01", "2026-06-03", " +420 777", 0, None, None,
                 " x@example.test", "confirmed", None, STAMP, STAMP],
                [9, 7, "ical", "u9", "2026-07-01", "2026-07-05", None, 5, None, 3,
                 None, "confirmed", None, STAMP, STAMP],
            ],
        },
        {
            "table": "submission",
            "columns": ["id", "apartment_id", "created_at", "state", "pseudo_stamp", "receipt_pdf",
                        "error_pdf", "request_xml", "request_xml_enc", "response_xml"],
            "rows": [
                [1, 7, "2026-05-02T10:00:00+00:00", "ok", "ABC/123 čx", PDF_A, None,
                 None, token("<req>DOC123</req>"), "<resp>1</resp>"],
                [2, 7, "2026-05-03T10:00:00+00:00", "ok", None, PDF_B, PDF_ERR,
                 "<req>plain</req>", None, None],
                [3, 7, "2026-05-04T10:00:00+00:00", "ok", "S3", "abc", None, None, None, None],
                [4, 8, "2026-05-02T11:00:00+00:00", "ok", "S4", PDF_C, None,
                 "<req>other</req>", None, "<resp>4</resp>"],
                [5, 7, "2026-05-11T10:00:00+00:00", "error", None, None, None, None, None, None],
                [10, 7, "2026-05-11T09:00:00+00:00", "ok", "S10", PDF_C, None, None, None, None],
            ],
        },
        {
            "table": "guest",
            "columns": ["id", "reservation_id", "surname", "first_name", "nationality",
                        "submit_state", "submission_id", "receipt_submission_id",
                        "created_at", "updated_at"],
            "rows": [
                [1, 1, "Novak", "Jan", "DEU", "sent", 1, None, STAMP, STAMP],
                [2, 1, "Novak", "Eva", "DEU", "sent", 2, 1, STAMP, STAMP],
                [3, 2, "Smith", "Al", "GBR", "sent", 10, None, STAMP, STAMP],
                [4, 3, "Other", "Op", "AUT", "sent", 4, None, STAMP, STAMP],
                [5, 9, "Bad", "Bo", "AUT", "sent", 3, None, STAMP, STAMP],
            ],
        },
        {
            # Brief 1321: the house book and the guest bundle.
            "table": "guest",
            "columns": ["id", "reservation_id", "surname", "first_name", "birth_date", "birth_date_enc",
                        "nationality", "doc_number_enc", "res_street_enc", "res_city_enc", "res_country",
                        "purpose", "note", "stay_from", "stay_to", "signature_png", "signature_png_enc",
                        "submit_state", "submitted_at", "submission_id", "manual_filed_at",
                        "manual_reference", "signed_for_guest_id", "entered_by", "passport_photo_at",
                        "archived_at", "restricted_at", "notice_version", "notice_lang", "notice_ack_at",
                        "created_at", "updated_at"],
            "rows": [
                [11, 1, "M\u00fcller", "Hans", None, token("15061980"), "DEU", token("C01X00T47"),
                 token("Hauptstr. 1"), token("Berlin"), "deu", "10", "=cmd", None, None,
                 None, token(SIGNATURE), "sent", "2026-05-02T10:00:00+00:00", 1, None, None, None,
                 "guest", STAMP, None, None, "2", "de", STAMP, STAMP, STAMP],
                [12, 1, "M\u00fcller", "Kid", "01012020", None, "DEU", None, None, None, "DEU",
                 "10", None, None, None, None, None, "pending", None, None, None, None, 11,
                 "guest", None, None, None, None, None, None, STAMP, STAMP],
                [13, 1, "M\u00fcller", "Baby", "00002019", None, "DEU", None, None, None, None,
                 "03", "line\nbreak", None, None, None, None, "pending", None, None, None, None, None,
                 "guest", None, None, None, None, None, None, STAMP, STAMP],
                [14, 2, "Dvo\u0159\u00e1k", "Petr", "02031975", None, "CZE", None, None, None, "CZE",
                 "77", None, "2026-05-11", None, "imported", None, "sent", None, 10,
                 "2026-05-11T08:00:00+00:00", "MAN-1", None, "host", STAMP, None, None,
                 None, None, None, STAMP, STAMP],
                [15, 6, "Tab\tName", "Q\"uote", "1990", None, "AUT", None, None, None, "xxx",
                 None, None, None, "2026-06-02", "data:image/png;base64,xx", None, "error", None,
                 None, None, None, None, "guest", None, None, None, None, None, None, STAMP, STAMP],
                [16, 1, "Archived", "A", None, None, "DEU", None, None, None, None, None, None,
                 None, None, None, None, "pending", None, None, None, None, None, "guest", None,
                 STAMP, None, None, None, None, STAMP, STAMP],
                [17, 1, "Restricted", "R", None, None, "DEU", None, None, None, None, None, None,
                 None, None, None, None, "pending", None, None, None, None, None, "guest", None,
                 None, STAMP, None, None, None, STAMP, STAMP],
                [18, 4, "Demo", "D", None, None, "DEU", None, None, None, None, None, None,
                 None, None, None, None, "pending", None, None, None, None, None, "guest", None,
                 None, None, None, None, None, STAMP, STAMP],
                [20, 9, "Paper", "Adult", "01011980", None, "AUT", None, None, None, None, None, None,
                 None, None, "imported", None, "pending", None, None, None, None, None, "guest", None,
                 None, None, None, None, None, STAMP, STAMP],
                [19, 9, "Paper", "Child", "01012021", None, "AUT", None, None, None, None, None, None,
                 None, None, None, None, "not_required", None, None, None, None, 20, "guest", None,
                 None, None, None, None, None, STAMP, STAMP],
            ],
        },
        {
            "table": "audit",
            "columns": ["at", "actor", "action", "detail", "owner_user_id"],
            "rows": [
                [STAMP, "owner@example.test", "guest_saved", "id=11", 1],
                [STAMP, "owner@example.test", "export_registration_pdf", "guest_id=11", 1],
                [STAMP, "owner@example.test", "export_registration_pdf", "guest_id=111", 1],
                [STAMP, "guest", "guest_form_saved", "guest=11 lang=de", 1],
                [STAMP, "owner@example.test", "other_action", "id=11", 1],
                [STAMP, "other@example.test", "export_registration_pdf", "guest_id=11", 2],
                [STAMP, "owner@example.test", "note", "guest_id=11 extra", 1],
            ],
        },
    ]


# Passport photo files in $UBYHOST_DATA_DIR/passport_photos (content is not read).
PHOTOS: list = ["11.jpg.enc", "14.png"]

OWNER = {"uid": 1}
OTHER = {"uid": 2}
ADMIN = {"uid": 3}
SUPPORT = {"uid": 3, "as": 1}

# name, path, session (None = signed out), language cookie
CASES = [
    ("signed_out_receipt", "/submissions/1/receipt.pdf", None, None),
    ("receipt_owned", "/submissions/1/receipt.pdf", OWNER, None),
    ("receipt_no_pdf", "/submissions/5/receipt.pdf", OWNER, None),
    ("receipt_bad_base64", "/submissions/3/receipt.pdf", OWNER, None),
    ("receipt_other_owner", "/submissions/4/receipt.pdf", OWNER, None),
    ("receipt_missing", "/submissions/999/receipt.pdf", OWNER, None),
    ("receipt_supporting", "/submissions/1/receipt.pdf", SUPPORT, None),
    ("errors_owned", "/submissions/2/errors.pdf", OWNER, None),
    ("errors_none", "/submissions/1/errors.pdf", OWNER, None),
    ("xml_request_encrypted", "/submissions/1/request.xml", OWNER, None),
    ("xml_response", "/submissions/1/response.xml", OWNER, None),
    ("xml_request_plain", "/submissions/2/request.xml", OWNER, None),
    ("xml_response_empty", "/submissions/2/response.xml", OWNER, None),
    ("xml_other_owner", "/submissions/4/request.xml", OWNER, None),
    ("xml_unknown", "/submissions/1/foo.xml", OWNER, None),
    ("xml_supporting", "/submissions/1/request.xml", SUPPORT, None),
    ("receipts_zip_all", "/submissions/receipts.zip", OWNER, None),
    ("receipts_zip_range", "/submissions/receipts.zip?from=2026-05-03&to=2026-05-10", OWNER, None),
    ("receipts_zip_bad_dates", "/submissions/receipts.zip?from=nope&to=2026-13-01", OWNER, None),
    ("receipts_zip_empty_range", "/submissions/receipts.zip?from=2027-01-01", OWNER, None),
    ("receipts_zip_empty_cs", "/submissions/receipts.zip?from=2027-01-01", OWNER, "cs"),
    ("receipts_zip_only_bad", "/submissions/receipts.zip?from=2026-05-04&to=2026-05-04", OWNER, None),
    ("receipts_zip_other", "/submissions/receipts.zip", OTHER, None),
    ("receipts_zip_admin_none", "/submissions/receipts.zip", ADMIN, None),
    ("stay_zip_two", "/reservations/1/dorucenka.zip", OWNER, None),
    ("stay_zip_one", "/reservations/2/dorucenka.zip", OWNER, None),
    ("stay_zip_bad_only", "/reservations/9/dorucenka.zip", OWNER, None),
    ("stay_zip_other_owner", "/reservations/3/dorucenka.zip", OWNER, None),
    ("stay_zip_none", "/reservations/4/dorucenka.zip", OWNER, None),
    ("stay_zip_supporting", "/reservations/1/dorucenka.zip", SUPPORT, None),
    ("stays_csv_no_range", "/reservations.csv", OWNER, None),
    ("stays_csv_no_range_vi", "/reservations.csv?from=2026-05-01", OWNER, "vi"),
    ("stays_csv_range", "/reservations.csv?from=2026-01-01&to=2026-12-31", OWNER, None),
    ("stays_csv_apartment", "/reservations.csv?from=2026-01-01&to=2026-12-31&apartment=6", OWNER, None),
    ("stays_csv_apartment_last", "/reservations.csv?from=2026-01-01&to=2026-12-31&apartment=6&apartment=7", OWNER, None),
    ("stays_csv_narrow", "/reservations.csv?from=2026-05-04&to=2026-05-09", OWNER, None),
    ("stays_csv_other", "/reservations.csv?from=2026-01-01&to=2026-12-31", OTHER, None),
    # Brief 1321
    ("housebook_signed_out", "/housebook.csv", None, None),
    ("housebook_all", "/housebook.csv", OWNER, None),
    ("housebook_apartment", "/housebook.csv?apartment=6", OWNER, None),
    ("housebook_range", "/housebook.csv?from=2026-05-02&to=2026-05-10", OWNER, None),
    ("housebook_other", "/housebook.csv", OTHER, None),
    ("housebook_supporting", "/housebook.csv", SUPPORT, None),
    ("guest_json_fresh", "/guests/11/export.json", OWNER, None),
    ("guest_json_plain", "/guests/14/export.json", OWNER, None),
    ("guest_json_child", "/guests/15/export.json", OWNER, None),
    ("guest_json_stale", "/guests/11/export.json", {"uid": 1, "stale": 1}, None),
    ("guest_json_stale_cs", "/guests/11/export.json", {"uid": 1, "stale": 1}, "cs"),
    ("guest_json_other_owner", "/guests/4/export.json", OWNER, None),
    ("guest_json_missing", "/guests/999/export.json", OWNER, None),
    ("guest_json_supporting", "/guests/11/export.json", SUPPORT, None),
]

# The response headers a route itself sets (plus the middleware's Cache-Control).
HEADERS = ("content-type", "content-disposition", "location", "cache-control")


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D102
        return NOW_LOCAL


def render_catalog() -> str:
    sys.path.insert(0, str(APP / "scripts"))
    from go_host_i18n import read_keys, render

    return render(read_keys(PKG / "i18n_keys.txt"))


def build(base_url: str) -> dict:
    import psycopg

    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {DB_NAME}")
    url = urlunsplit(urlsplit(base_url)._replace(path="/" + DB_NAME))
    data_dir = tempfile.mkdtemp(prefix="exports-golden-")
    os.environ.update({
        "UBYHOST_DATABASE_URL": url,
        "UBYHOST_SECRET_KEY": SECRET,
        "UBYHOST_DATA_KEYS": DATA_KEY,
        "UBYHOST_DATA_DIR": data_dir,
    })
    sys.path.insert(0, str(APP))
    from fastapi.testclient import TestClient

    from app import auth, db
    from app.main import app
    from app.routes import exports

    db.apply_postgresql_schema()
    photo_dir = Path(data_dir) / "passport_photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    for name in PHOTOS:
        (photo_dir / name).write_bytes(b"x")
    rows = seed()
    with psycopg.connect(url, autocommit=True) as conn:
        for table in rows:
            cols = ", ".join(table["columns"])
            marks = ", ".join(["%s"] * len(table["columns"]))
            for row in table["rows"]:
                conn.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)

    def audit_rows(conn, after: int) -> list:
        cur = conn.execute(
            "SELECT id, at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id "
            "FROM audit WHERE id > %s ORDER BY id", (after,))
        return [list(r) for r in cur.fetchall()]

    cases = []
    with mock.patch.object(exports, "datetime", FrozenDatetime), \
            mock.patch.object(db, "utcnow", lambda: NOW), \
            psycopg.connect(url, autocommit=True) as conn:
        client = TestClient(app, follow_redirects=False)
        last = conn.execute("SELECT COALESCE(MAX(id), 0) FROM audit").fetchone()[0]
        for name, path, sess, lang in CASES:
            client.cookies.clear()
            if sess is not None:
                now = int(time.time())
                # "stale": a login an hour old, past auth.FRESH_LOGIN_SECONDS.
                client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(
                    sess["uid"], 0, workspace_user_id=sess.get("as"),
                    impersonation_started_at=now if sess.get("as") else None,
                    issued_at=now - 3600 if sess.get("stale") else now))
            if lang:
                client.cookies.set("ubyhost_lang", lang)
            resp = client.get(path)
            written = audit_rows(conn, last)
            if written:
                last = written[-1][0]
            case = {
                "name": name, "path": path, "session": sess, "lang": lang,
                "status": resp.status_code,
                "headers": {h: resp.headers[h] for h in HEADERS if h in resp.headers},
                "audit": [r[1:] for r in written],
            }
            if resp.headers.get("content-type") == "application/zip":
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    case["zip"] = [[i.filename, i.compress_type, base64.b64encode(zf.read(i)).decode()]
                                   for i in zf.infolist()]
            else:
                case["body_b64"] = base64.b64encode(resp.content).decode()
            cases.append(case)
    with psycopg.connect(base_url, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)")
    return {
        "secret": SECRET, "data_keys": DATA_KEY, "now": NOW,
        "seed": rows, "photos": PHOTOS, "cases": cases,
    }


def main(argv: list) -> int:
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL", "")
    if not base:
        print("set UBYHOST_TEST_DATABASE_URL to a PostgreSQL server URL")
        return 2
    outputs = {
        OUT: json.dumps(build(base), ensure_ascii=False, indent=1) + "\n",
        PKG / "i18n.json": render_catalog(),
    }
    stale = []
    for path, text in outputs.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if "--check" in argv:
            stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}")
    for path in stale:
        print(f"stale: {path}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
