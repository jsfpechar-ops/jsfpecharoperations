"""Write go/internal/web/onboarding/testdata/demo_reset_golden.json from the real Python route.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_demo_reset_golden.py          write the file
    .venv/bin/python scripts/go_demo_reset_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the fixed rows in SEED and the
passport photo files in PHOTOS, sends every POST /demo/reset of CASES, in
order, through the real FastAPI app (TestClient), and records each answer and,
at the end, the ids left in every seeded table, the photo files left and the
audit rows written. go/internal/web/onboarding/demo_reset_test.go seeds
PostgreSQL and a temporary data directory from the same file, sends the same
requests to the Go handler and compares. App/tests/test_go_demo_reset_golden.py
fails when this file is stale. Brief 1596.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "onboarding" / "testdata" / "demo_reset_golden.json"

STAMP = "2026-01-01T00:00:00+00:00"
CSRF_NONCE = "golden-demo-csrf-nonce-0123456789"
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}
USERS = (1, 2, 3, 4, 5)
STUDIO = "Vinohrady Studio (demo)"
LOFT = "Karlín Loft (demo)"
ENTITY = "Josef Novák (demo)"
CONTROLLER = "Demo Controller s.r.o."


def _apt(aid, owner, name, entity, controller=None, archived=None):
    return [aid, owner, name, entity, controller, archived, STAMP]


# Host 2: the demo (entities 21, 22) with 201 studio, 202 loft, 204 a renamed
# property whose controller is the demo one, 205 an archived property with the
# demo name; 203 is a real property of a real entity 23 and stays. Host 3: a
# second demo (31, 301) and a real property 302. Host 4: a demo entity and no
# property. Host 5: no demo. Every apartment-bound table Python clears has a
# row on 201 and on 203.
SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[uid, f"host{uid}@example.test", "x", "admin" if uid == 1 else "host", STAMP] for uid in USERS]},
    {"table": "legal_acceptance", "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in USERS for doc, version in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "created_at"],
     "rows": [[21, 2, ENTITY, STAMP], [22, 2, CONTROLLER, STAMP], [23, 2, "Real s.r.o.", STAMP],
              [31, 3, ENTITY, STAMP], [32, 3, "Real Three", STAMP], [41, 4, CONTROLLER, STAMP],
              [51, 5, "Real Five", STAMP]]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "legal_entity_id", "data_controller_entity_id",
                 "archived_at", "created_at"],
     "rows": [_apt(201, 2, STUDIO, 21), _apt(202, 2, LOFT, 21, 22), _apt(203, 2, "Real flat", 23),
              _apt(204, 2, "Renamed", 23, 22), _apt(205, 2, STUDIO, 23, None, "2026-01-02"),
              _apt(301, 3, LOFT, 31), _apt(302, 3, "Real Three flat", 32), _apt(501, 5, STUDIO + " copy", 51)]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status", "created_at", "updated_at"],
     "rows": [[rid, apt, f"golden-{rid}", "2026-02-01", "2026-02-03", "active", STAMP, STAMP]
              for rid, apt in ((2011, 201), (2021, 202), (2031, 203), (3011, 301), (3021, 302))]},
    {"table": "guest", "columns": ["id", "reservation_id", "created_at", "updated_at"],
     "rows": [[gid, rid, STAMP, STAMP] for gid, rid in ((20111, 2011), (20112, 2011), (20211, 2021),
                                                         (20311, 2031), (30111, 3011), (30211, 3021))]},
    {"table": "alert", "columns": ["id", "apartment_id", "level", "kind", "message", "created_at"],
     "rows": [[1, 201, "warning", "golden", "m", STAMP], [2, 203, "warning", "golden", "m", STAMP],
              [3, None, "info", "golden", "m", STAMP]]},
    {"table": "apartment_slug", "columns": ["slug", "apartment_id", "is_current", "created_at"],
     "rows": [["studio-aaa222", 201, 1, STAMP], ["real-bbb333", 203, 1, STAMP]]},
    {"table": "ical_feed", "columns": ["id", "apartment_id", "url", "created_at"],
     "rows": [[1, 201, "https://cal.example.test/1.ics", STAMP], [2, 203, "https://cal.example.test/2.ics", STAMP]]},
    {"table": "payment_request",
     "columns": ["id", "owner_user_id", "apartment_id", "reason", "amount_czk", "rail", "expires_at", "created_at",
                 "updated_at"],
     "rows": [[1, 2, 201, "cleaning", 100, "qr", STAMP, STAMP, STAMP], [2, 2, 203, "cleaning", 100, "qr", STAMP, STAMP, STAMP]]},
    {"table": "stay_fee_rate", "columns": ["id", "apartment_id", "rate_czk", "effective_from", "created_at"],
     "rows": [[1, 201, 50, "2026-01-01", STAMP], [2, 203, 50, "2026-01-01", STAMP]]},
    {"table": "door_code", "columns": ["id", "reservation_id", "apartment_id", "lock_id", "created_at", "updated_at"],
     "rows": [[1, 2011, 201, "L1", STAMP, STAMP], [2, 2031, 203, "L2", STAMP, STAMP]]},
    {"table": "cleaning_event", "columns": ["id", "apartment_id", "scheduled_date", "created_at", "updated_at"],
     "rows": [[1, 201, "2026-02-03", STAMP, STAMP], [2, 203, "2026-02-03", STAMP, STAMP]]},
    {"table": "cleaning_property", "columns": ["apartment_id", "updated_at"], "rows": [[201, STAMP], [203, STAMP]]},
    {"table": "property_page", "columns": ["id", "apartment_id", "created_at", "updated_at"],
     "rows": [[1, 201, STAMP, STAMP], [2, 203, STAMP, STAMP]]},
    {"table": "booking_hold", "columns": ["id", "apartment_id", "date_from", "date_to", "expires_at", "created_at"],
     "rows": [[1, 201, "2026-03-01", "2026-03-02", STAMP, STAMP], [2, 203, "2026-03-01", "2026-03-02", STAMP, STAMP]]},
]

# Photo files under <data dir>/passport_photos; a guest of a cleared property loses all of its own.
PHOTOS = ["20111.jpg.enc", "20111.png", "20112.pdf.enc", "20211.webp.enc", "20311.jpg.enc", "30111.png.enc",
          "30211.jpg.enc", "20111.gif", "notes.txt"]

# name, user, previewed workspace (0: none), language, with a CSRF token.
CASES = [
    ("signed out", 0, 0, "en", True),
    ("no CSRF token", 2, 0, "en", False),
    ("host without a demo", 5, 0, "en", True),
    ("demo entity without a property", 4, 0, "cs", True),
    ("clear the demo", 2, 0, "en", True),
    ("clear again in Czech", 2, 0, "cs", True),
    ("admin clears a previewed demo in Vietnamese", 1, 3, "vi", True),
]

TABLES = [("legal_entity", "id"), ("apartment", "id"), ("reservation", "id"), ("guest", "id"), ("alert", "id"),
          ("apartment_slug", "slug"), ("ical_feed", "id"), ("payment_request", "id"), ("stay_fee_rate", "id"),
          ("door_code", "id"), ("cleaning_event", "id"), ("cleaning_property", "apartment_id"),
          ("property_page", "id"), ("booking_hold", "id")]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row))


def render() -> str:
    from fastapi.testclient import TestClient

    from app import auth, config, db, security
    from app.main import app

    db.init_db()
    _seed(db)
    photos = config.DATA_DIR / "passport_photos"
    photos.mkdir(parents=True, exist_ok=True)
    for name in PHOTOS:
        (photos / name).write_bytes(b"golden")
    client = TestClient(app)
    cases = []
    for name, user, workspace, lang, csrf in CASES:
        client.cookies.clear()
        cookies = {"ubyhost_lang": lang, security.CSRF_COOKIE: CSRF_NONCE}
        if user:
            cookies[auth.SESSION_COOKIE] = auth.issue_session(
                user, 1, workspace_user_id=workspace or None,
                impersonation_started_at=int(time.time()) if workspace else None)
        form = {}
        if csrf:
            form["_csrf"] = security._csrf_serializer().dumps({"nonce": security._nonce_binding(CSRF_NONCE)})
        header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        response = client.post("/demo/reset", data=form, headers={"Cookie": header}, follow_redirects=False)
        cases.append({"name": name, "user": user, "workspace": workspace, "lang": lang, "csrf": csrf,
                      "status": response.status_code, "location": response.headers.get("location")})
    final = {table: [row[col] for row in db.query(f"SELECT {col} FROM {table} ORDER BY {col}")]
             for table, col in TABLES}
    audits = [dict(row) for row in db.query(
        "SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit "
        "WHERE action LIKE 'demo%' ORDER BY id")]
    golden = {"versions": VERSIONS, "csrf_nonce": CSRF_NONCE, "seed": SEED, "photos": PHOTOS, "cases": cases,
              "final": final, "photos_left": sorted(p.name for p in photos.iterdir()), "audit": audits}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_demo_reset_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "demo_reset_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
