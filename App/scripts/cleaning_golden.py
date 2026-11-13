"""Write go/internal/web/cleaning/testdata/cleaning_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/cleaning_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED, sends every
request in CASES, in order, through the real FastAPI app (TestClient), and
records each answer and, at the end, the cleaning rows. A column named in a
table's "encrypt" list holds plain text here; each side stores it encrypted
with its own key (db.encrypt_field here, secure.MultiFernet in Go).
go/internal/web/cleaning/golden_test.go seeds PostgreSQL from the same file,
sends the same requests to the Go handlers and compares.
App/tests/test_go_cleaning_golden.py fails when this file is stale.

cleaning.today() is pinned to TODAY and the page's random CSRF value is blanked. Share expiry dates are far in the past or
the future, so the real clock does not change the result.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "cleaning" / "testdata" / "cleaning_golden.json"

TODAY = "2026-05-10"
STAMP = "2026-01-01T00:00:00+00:00"
LIVE = "2099-01-01T00:00:00+00:00"
CSRF_NONCE = "golden-csrf-nonce-0123456789"
# The rendered CSRF token is random; the golden keeps the field, value blanked.
CSRF_FIELD = re.compile(r'name="_csrf" value="[^"]*"')
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}


def share_token(n: int) -> str:
    return (f"share{n}" + "x" * 43)[:43]


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _stay(rid, apartment, start, end, status="active", source="host", archived=None):
    return [rid, apartment, f"u{rid}", start, end, f"Stay {rid}", status, source, 1, archived, STAMP, STAMP]


def _event(eid, apartment, source, source_date, day, start=None, end=None, notes=None,
           overridden=0, state="scheduled", revision=1):
    return [eid, apartment, source, source_date, day, start, end, notes, overridden, state,
            revision, STAMP, STAMP]


SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[1, "owner@example.test", "x", "host", STAMP], [2, "other@example.test", "x", "host", STAMP]]},
    {"table": "legal_acceptance",
     "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in (1, 2) for doc, version in VERSIONS.items()]},
    # 11 hours 10-15, manual code. 12 no hours, TTLock code plus a pending one.
    # 13 archived. 14 checkout after check-in (no valid default window). 21 owner 2.
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "city_en", "uby_name", "permalink_token",
                 "created_at", "checkin_hour", "checkout_hour", "active", "archived_at",
                 "lock_provider", "lock_id"],
     "rows": [
         [11, 1, "Alfa", "Brno", "UBY", "tok11", STAMP, 15, 10, 1, None, None, None],
         [12, 1, "Beta", "Brno", "UBY", "tok12", STAMP, None, None, 1, None, "ttlock", "L12"],
         [13, 1, "Gama", "Brno", "UBY", "tok13", STAMP, 15, 10, 1, "2026-01-02", None, None],
         [14, 1, "Delta", "Brno", "UBY", "tok14", STAMP, 9, 10, 1, None, None, None],
         [21, 2, "Cizi", "Brno", "UBY", "tok21", STAMP, 14, 11, 1, None, None, None],
     ]},
    {"table": "lock_account",
     "columns": ["id", "owner_user_id", "provider", "username", "created_at", "updated_at"],
     "rows": [[1, 1, "ttlock", "lock@example.test", STAMP, STAMP]]},
    {"table": "cleaning_code",
     "columns": ["id", "apartment_id", "source", "pin_enc", "lock_account_id", "lock_id",
                 "operation_ref", "state", "created_at", "updated_at"],
     "encrypt": ["pin_enc"],
     "rows": [
         [1, 11, "manual", "4711", None, None, "op1", "active", STAMP, STAMP],
         [2, 12, "ttlock", "9090", 1, "L12", "op2", "active", STAMP, STAMP],
         [3, 12, "ttlock", None, 1, "L12", "op3", "pending", STAMP, STAMP],
         [4, 21, "manual", "1234", None, None, "op4", "revoke_failed", STAMP, STAMP],
     ]},
    {"table": "cleaning_property",
     "columns": ["apartment_id", "instructions", "code_id", "pending_code_id", "updated_at"],
     "rows": [
         [11, "Vyměnit ručníky & <povlečení>", 1, None, STAMP],
         [12, "", 2, 3, STAMP],
         [21, "Cizí pokyny", 4, None, STAMP],
     ]},
    # 201 (owner 2's only stay) has no cleaning yet: the first case inserts one.
    # It is the only stay that request reconciles, so PostgreSQL and SQLite hand
    # out the same new id (both burn an id on every ON CONFLICT). 103 crosses the shared
    # period end, 104 its start. 106 is cancelled, 107 is demo, 109 is on the
    # archived apartment.
    {"table": "reservation",
     "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "summary", "status", "source",
                 "declared_guests", "archived_at", "created_at", "updated_at"],
     "rows": [
         _stay(100, 12, "2026-05-14", "2026-05-15"),
         _stay(101, 11, "2026-05-05", "2026-05-10"),
         _stay(102, 11, "2026-05-12", "2026-05-16"),
         _stay(103, 11, "2026-05-16", "2026-06-20"),
         _stay(104, 12, "2026-04-28", "2026-05-11"),
         _stay(105, 12, "2026-05-11", "2026-05-13"),
         _stay(106, 12, "2026-05-20", "2026-05-22", status="cancelled"),
         _stay(107, 11, "2026-05-25", "2026-05-27", source="demo"),
         _stay(108, 14, "2026-05-08", "2026-05-12"),
         _stay(109, 13, "2026-05-01", "2026-05-03"),
         _stay(201, 21, "2026-05-08", "2026-05-12"),
     ]},
    # 502 has a stale source date and a malformed start time. 506 belongs to the
    # cancelled stay. 505 is on the archived apartment, 507 is manual (the delete
    # cases), 508 is before every period, 509 is owner 2's manual one.
    {"table": "cleaning_event",
     "columns": ["id", "apartment_id", "source_reservation_id", "source_date", "scheduled_date",
                 "start_time", "end_time", "notes_enc", "overridden", "state", "revision",
                 "created_at", "updated_at"],
     "encrypt": ["notes_enc"],
     "rows": [
         _event(501, 11, 101, "2026-05-10", "2026-05-10", notes="Klíč je u sousedky <b>"),
         _event(502, 11, 102, "2026-05-15", "2026-05-15", start="x9:00", end="10:00", revision=2),
         _event(503, 11, 103, "2026-06-20", "2026-06-20"),
         _event(504, 12, 104, "2026-05-11", "2026-05-11", start="11:00", end="13:00", notes="Okna", overridden=1),
         _event(505, 13, None, None, "2026-05-12"),
         _event(506, 12, 106, "2026-05-22", "2026-05-22"),
         _event(507, 11, None, None, "2026-05-13", revision=3),
         _event(508, 11, None, None, "2026-04-30"),
         _event(509, 21, None, None, "2026-05-09", notes="Cizí poznámka"),
         _event(510, 12, 100, "2026-05-15", "2026-05-15"),
         _event(511, 12, 105, "2026-05-13", "2026-05-14", overridden=1),
         _event(512, 14, 108, "2026-05-12", "2026-05-12"),
     ]},
    # 1 live (also links owner 2's apartment, which is dropped), 2 revoked,
    # 3 expired, 4 owner 2's, 5 only the archived apartment.
    {"table": "cleaning_share",
     "columns": ["id", "owner_user_id", "token_hash", "expires_at", "revoked_at", "created_at"],
     "rows": [
         [1, 1, _digest(share_token(1)), LIVE, None, STAMP],
         [2, 1, _digest(share_token(2)), LIVE, "2026-05-01T00:00:00+00:00", STAMP],
         [3, 1, _digest(share_token(3)), "2020-01-01T00:00:00+00:00", None, STAMP],
         [4, 2, _digest(share_token(4)), LIVE, None, STAMP],
         [5, 1, _digest(share_token(5)), LIVE, None, STAMP],
     ]},
    {"table": "cleaning_share_property", "columns": ["share_id", "apartment_id"],
     "rows": [[1, 11], [1, 12], [1, 21], [2, 11], [3, 11], [4, 21], [5, 13]]},
]

RANGE = "from=2026-05-01&to=2026-06-30"


def _case(name, method, path, query="", user=None, lang=None, form=None, csrf=False, private=False):
    return {"name": name, "method": method, "path": path, "query": query, "user": user,
            "lang_cookie": lang, "form": form, "csrf": csrf, "private": private}


T1, T2, T3, T4, T5 = (share_token(n) for n in range(1, 6))
CASES = [
    _case("schedule_owner2_first", "GET", "/cleaning/schedule", RANGE, user=2, private=True),
    _case("schedule_en", "GET", "/cleaning/schedule", RANGE, user=1, private=True),
    _case("schedule_cs", "GET", "/cleaning/schedule", RANGE + "&lang=cs", user=1, private=True),
    _case("schedule_vi_property", "GET", "/cleaning/schedule", RANGE + "&property=12", user=1, lang="vi", private=True),
    _case("schedule_cal_property", "GET", "/cleaning/schedule", RANGE + "&cal_property=14", user=1, private=True),
    _case("schedule_foreign_property", "GET", "/cleaning/schedule", RANGE + "&property=21", user=1),
    _case("schedule_archived_property", "GET", "/cleaning/schedule", RANGE + "&property=13", user=1),
    _case("schedule_bad_property", "GET", "/cleaning/schedule", RANGE + "&property=abc", user=1, private=True),
    _case("schedule_empty_range", "GET", "/cleaning/schedule", "from=2026-05-01&to=2026-05-01", user=1, private=True),
    _case("schedule_bad_date", "GET", "/cleaning/schedule", "from=2026-02-30&to=2026-03-30", user=1, private=True),
    _case("schedule_missing_dates", "GET", "/cleaning/schedule", "", user=1, private=True),
    _case("schedule_signed_out", "GET", "/cleaning/schedule", RANGE),
    _case("shared_schedule_default", "GET", f"/cleaning/shared/{T1}/schedule", "", private=True),
    _case("shared_schedule_clamped", "GET", f"/cleaning/shared/{T1}/schedule", "from=2026-05-12&to=2026-07-30", private=True),
    _case("shared_schedule_property", "GET", f"/cleaning/shared/{T1}/schedule", "property=12&lang=vi", private=True),
    _case("shared_schedule_foreign_property", "GET", f"/cleaning/shared/{T1}/schedule", "property=21"),
    _case("shared_schedule_bad_dates", "GET", f"/cleaning/shared/{T1}/schedule", "from=2026-05-12", private=True),
    _case("shared_schedule_revoked", "GET", f"/cleaning/shared/{T2}/schedule"),
    _case("shared_schedule_expired", "GET", f"/cleaning/shared/{T3}/schedule"),
    _case("shared_schedule_archived_only", "GET", f"/cleaning/shared/{T5}/schedule"),
    _case("shared_schedule_malformed", "GET", "/cleaning/shared/short/schedule"),
    _case("shared_page_en", "GET", f"/cleaning/shared/{T1}", "", private=True),
    _case("shared_page_cs", "GET", f"/cleaning/shared/{T1}", "lang=cs", private=True),
    _case("shared_page_vi", "GET", f"/cleaning/shared/{T1}", "", lang="vi", private=True),
    _case("shared_page_owner2", "GET", f"/cleaning/shared/{T4}", "", private=True),
    _case("shared_page_bad_dates", "GET", f"/cleaning/shared/{T1}", "to=2026-05-12"),
    _case("shared_page_revoked", "GET", f"/cleaning/shared/{T2}"),
    _case("shared_page_expired", "GET", f"/cleaning/shared/{T3}"),
    _case("delete_no_csrf", "POST", "/cleaning/events/507/delete", user=1, form={"revision": "3"}),
    _case("delete_signed_out", "POST", "/cleaning/events/507/delete", form={"revision": "3"}, csrf=True),
    _case("delete_stale_revision", "POST", "/cleaning/events/507/delete", user=1, form={"revision": "2"}, csrf=True),
    _case("delete_bad_revision", "POST", "/cleaning/events/507/delete", user=1, form={"revision": "x"}, csrf=True),
    _case("delete_archived", "POST", "/cleaning/events/505/delete", user=1, form={"revision": "1"}, csrf=True),
    _case("delete_foreign", "POST", "/cleaning/events/509/delete", user=1, form={"revision": "1"}, csrf=True),
    _case("delete_missing", "POST", "/cleaning/events/99999/delete", user=1, form={"revision": "1"}, csrf=True),
    _case("delete_ok", "POST", "/cleaning/events/507/delete", user=1, form={"revision": "3"}, csrf=True, private=True),
    _case("delete_again", "POST", "/cleaning/events/507/delete", user=1, form={"revision": "4"}, csrf=True),
    _case("revoke_foreign", "POST", "/cleaning/shares/4/revoke", user=1, form={}, csrf=True, private=True),
    _case("revoke_ok", "POST", "/cleaning/shares/1/revoke", user=1, form={}, csrf=True, private=True),
    _case("revoke_no_csrf", "POST", "/cleaning/shares/4/revoke", user=1, form={}),
    _case("shared_after_revoke", "GET", f"/cleaning/shared/{T1}/schedule"),
    _case("shared_owner2_after_revoke", "GET", f"/cleaning/shared/{T4}/schedule", "", private=True),
    _case("schedule_after_delete", "GET", "/cleaning/schedule", RANGE, user=1, private=True),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        secret = [table["columns"].index(c) for c in table.get("encrypt", [])]
        for row in table["rows"]:
            row = list(row)
            for i in secret:
                if row[i] is not None:
                    row[i] = db.encrypt_field(row[i])
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _cookie_header(db, auth, security, case) -> str:
    parts = []
    if case["user"]:
        version = db.query_one("SELECT session_version FROM user_account WHERE id = ?", (case["user"],))
        parts.append(f"{auth.SESSION_COOKIE}={auth.issue_session(case['user'], version['session_version'])}")
    if case["lang_cookie"]:
        parts.append(f"ubyhost_lang={case['lang_cookie']}")
    if case["csrf"]:
        parts.append(f"{security.CSRF_COOKIE}={CSRF_NONCE}")
    return "; ".join(parts)


def _send(client, db, auth, security, case) -> dict:
    url = case["path"] + ("?" + case["query"] if case["query"] else "")
    headers = {}
    cookie = _cookie_header(db, auth, security, case)
    if cookie:
        headers["Cookie"] = cookie
    client.cookies.clear()
    if case["method"] == "GET":
        response = client.get(url, headers=headers, follow_redirects=False)
    else:
        form = dict(case["form"] or {})
        if case["csrf"]:
            form["_csrf"] = security._csrf_serializer().dumps({"nonce": security._nonce_binding(CSRF_NONCE)})
        response = client.post(url, data=form, headers=headers, follow_redirects=False)
    private = {k: response.headers.get(k) for k in ("cache-control", "referrer-policy", "x-robots-tag")}
    if case["private"] and private != {"cache-control": "no-store", "referrer-policy": "no-referrer",
                                       "x-robots-tag": "noindex, nofollow"}:
        raise SystemExit(f"{case['name']}: PRIVATE headers missing: {private}")
    return {"status": response.status_code, "location": response.headers.get("location"),
            "content_type": response.headers.get("content-type"),
            "body": "" if 300 <= response.status_code < 400
            else CSRF_FIELD.sub('name="_csrf" value=""', response.text)}


def _final(db) -> dict:
    events = [{"id": r["id"], "apartment_id": r["apartment_id"], "source_reservation_id": r["source_reservation_id"],
               "source_date": r["source_date"], "scheduled_date": r["scheduled_date"], "state": r["state"],
               "revision": r["revision"], "overridden": r["overridden"]}
              for r in db.query("SELECT * FROM cleaning_event ORDER BY id")]
    shares = [{"id": r["id"], "revoked": r["revoked_at"] is not None}
              for r in db.query("SELECT id, revoked_at FROM cleaning_share ORDER BY id")]
    return {"cleaning_event": events, "cleaning_share": shares}


def render() -> str:
    """Seed a fresh database, send every case, and return the golden JSON text."""
    from fastapi.testclient import TestClient

    from app import auth, cleaning, db, security
    from app.main import app

    db.init_db()
    _seed(db)
    pinned = date.fromisoformat(TODAY)
    original = cleaning.today
    cleaning.today = lambda: pinned
    try:
        client = TestClient(app)
        results = [{**case, **_send(client, db, auth, security, case)} for case in CASES]
    finally:
        cleaning.today = original
    golden = {"today": TODAY, "csrf_nonce": CSRF_NONCE, "versions": VERSIONS, "seed": SEED,
              "cases": results, "final": _final(db)}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "cleaning_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    sys.path.insert(0, str(APP))
    main()
