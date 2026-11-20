"""Write go/internal/web/stays/testdata/edit_posts_golden.json from Python POST routes.

Run from App/:

    .venv/bin/python scripts/go_edit_posts_golden.py
    .venv/bin/python scripts/go_edit_posts_golden.py --check
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "edit_posts_golden.json"

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
OWNER_ID = 9001
STAMP = NOW.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _seed():
    from app import acceptance, auth, db

    db.init_db()
    db.execute(
        "INSERT INTO user_account (id, username, password_hash, role, active, session_version, created_at, email) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (OWNER_ID, "edit-posts-golden", "x", "host", 1, 1, STAMP, "edit-posts@example.test"),
    )
    versions = acceptance.current_versions()
    for i, doc in enumerate(("terms", "privacy", "dpa")):
        db.execute(
            "INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) "
            "VALUES (?,?,?,?,?,?)",
            (9100 + i, OWNER_ID, doc, versions[doc], STAMP, "clickwrap"),
        )
    entity_id = db.insert("legal_entity", {"owner_user_id": OWNER_ID, "name": "Entity", "created_at": STAMP})
    apt_id = db.insert(
        "apartment",
        {
            "owner_user_id": OWNER_ID,
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "permalink_token": "tok-edit",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": STAMP,
        },
    )
    db.insert(
        "reservation",
        {
            "id": 801,
            "apartment_id": apt_id,
            "source": "manual",
            "uid": "uid-0",
            "date_from": "2026-07-01",
            "date_to": "2026-07-03",
            "status": "active",
            "declared_guests": 2,
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    db.insert(
        "reservation",
        {
            "id": 802,
            "apartment_id": apt_id,
            "source": "demo",
            "uid": "uid-1",
            "date_from": "2026-07-01",
            "date_to": "2026-07-03",
            "status": "active",
            "declared_guests": 2,
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return OWNER_ID, apt_id


def _client(owner_id: int):
    import re

    from app import db, login_link
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    def page_csrf() -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    resp = client.post(
        "/login/link",
        data={"t": login_link.issue(account), "_csrf": page_csrf()},
        follow_redirects=False,
    )
    if resp.status_code != 303:
        raise RuntimeError(f"login failed: {resp.status_code}")
    return client


def _csrf(client, path: str) -> str:
    page = client.get(path).text
    start = page.find('name="_csrf" value="')
    if start < 0:
        raise RuntimeError("csrf missing")
    start += len('name="_csrf" value="')
    end = page.find('"', start)
    return page[start:end]


def _case(name, method, path, fields, status, **extra):
    row = {"name": name, "method": method, "path": path, "fields": fields, "owner_id": OWNER_ID, "status": status}
    row.update(extra)
    return row


def _write_cases(owner_id: int):
    client = _client(owner_id)
    cases = []
    token = _csrf(client, "/reservations/801")
    headers = {"X-Requested-With": "fetch"}
    r = client.post(
        "/reservations/801/quick-edit",
        data={"_csrf": token, "summary": "Weekend"},
        headers=headers,
        follow_redirects=False,
    )
    cases.append(
        _case("quick-edit fetch", "POST", "/reservations/801/quick-edit", {"summary": "Weekend"}, r.status_code, headers=headers, body=r.text)
    )
    token = _csrf(client, "/reservations/801")
    r = client.post("/reservations/801/archive", data={"_csrf": token}, follow_redirects=False)
    cases.append(_case("archive stay", "POST", "/reservations/801/archive", {}, r.status_code, location_prefix=r.headers.get("location", "")[:20]))
    token = _csrf(client, "/reservations/801")
    r = client.post("/reservations/801/unarchive", data={"_csrf": token}, follow_redirects=False)
    cases.append(_case("unarchive stay", "POST", "/reservations/801/unarchive", {}, r.status_code, location_prefix=r.headers.get("location", "")[:20]))
    token = _csrf(client, "/reservations/802")
    r = client.post("/reservations/802/delete-demo", data={"_csrf": token}, follow_redirects=False)
    cases.append(_case("delete demo", "POST", "/reservations/802/delete-demo", {}, r.status_code, location_prefix=r.headers.get("location", "")[:12]))
    token = _csrf(client, "/reservations/801")
    r = client.post("/reservations/801/remove-empty-slot", data={"_csrf": token, "expected": "1"}, follow_redirects=False)
    cases.append(_case("remove slot bad count", "POST", "/reservations/801/remove-empty-slot", {"expected": "1"}, r.status_code, location_prefix=r.headers.get("location", "")[:20]))
    return {"now": NOW.isoformat(), "cases": cases}


def main() -> int:
    sys.path.insert(0, str(APP))
    db_path = tempfile.mkdtemp()
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_TERMS_VERSION", "t1")
    os.environ.setdefault("UBYHOST_PRIVACY_VERSION", "p1")
    os.environ.setdefault("UBYHOST_DPA_VERSION", "d1")
    os.environ["UBYHOST_DB"] = str(Path(db_path) / "golden.sqlite3")
    _seed()
    data = _write_cases(OWNER_ID)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if "--check" in sys.argv:
        if not OUT.exists():
            print("missing", OUT, file=sys.stderr)
            return 1
        current = json.loads(OUT.read_text(encoding="utf-8"))
        if current != data:
            print("stale golden", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())