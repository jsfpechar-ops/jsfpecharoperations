"""Golden HTTP answers for brief 1741 filing POST routes.

Run from App/:

    .venv/bin/python scripts/go_submit_golden.py
    .venv/bin/python scripts/go_submit_golden.py --check

Seeds a throwaway database, posts through admin submit routes with CSRF
and a fixed actor, and writes go/internal/web/stays/testdata/submit_golden.json.
The Go test in submit_test.go replays on PostgreSQL when UBYHOST_TEST_DATABASE_URL is set.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "submit_golden.json"

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
OWNER_ID = 1741001
STAMP = NOW.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _seed():
    from app import acceptance, db

    db.init_db()
    db.execute(
        "INSERT INTO user_account (id, username, password_hash, role, active, session_version, created_at, email) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (OWNER_ID, "submit-golden", "x", "host", 1, 1, STAMP, "submit-golden@example.test"),
    )
    versions = acceptance.current_versions()
    for i, doc in enumerate(("terms", "privacy", "dpa")):
        db.execute(
            "INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) "
            "VALUES (?,?,?,?,?,?)",
            (1741100 + i, OWNER_ID, doc, versions[doc], STAMP, "clickwrap"),
        )
    entity_id = db.insert("legal_entity", {"owner_user_id": OWNER_ID, "name": "Entity", "created_at": STAMP})
    apt_id = db.insert(
        "apartment",
        {
            "owner_user_id": OWNER_ID,
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "permalink_token": "tok-submit",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": STAMP,
        },
    )
    db.insert(
        "reservation",
        {
            "id": 101,
            "apartment_id": apt_id,
            "source": "manual",
            "uid": "uid-submit",
            "date_from": "2026-06-20",
            "date_to": "2026-06-22",
            "status": "active",
            "declared_guests": 2,
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    )
    return OWNER_ID


def _client(owner_id: int):
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


def _flash_key(_resp) -> str:
    return ""


def _case(name, method, path, body, user, status, location, flash_key):
    return {
        "name": name,
        "method": method,
        "path": path,
        "body": body,
        "user": user,
        "status": status,
        "location": location,
        "flash_key": flash_key,
    }


def _signed_out_cases():
    from app.main import app
    from fastapi.testclient import TestClient

    cases = []
    anon_client = TestClient(app)
    csrf = _csrf(anon_client, "/login")
    for name, path in (
        ("signed_out_submit_ready", "/reservations/submit-ready"),
        ("signed_out_submit_one", "/reservations/101/submit"),
    ):
        body = f"_csrf={csrf}"
        if "submit-ready" in path:
            body += "&return_to=%2Freservations"
        resp = anon_client.post(path, data=body, follow_redirects=False)
        cases.append(
            _case(name, "POST", path, body, 0, resp.status_code, resp.headers.get("location", ""), "")
        )
    return cases


def _signed_in_cases(owner_id: int):
    cases = []
    client = _client(owner_id)
    csrf = _csrf(client, "/reservations")
    resp = client.post("/reservations/99999/submit", data={"_csrf": csrf}, follow_redirects=False)
    cases.append(
        _case(
            "no_such_stay",
            "POST",
            "/reservations/99999/submit",
            f"_csrf={csrf}",
            owner_id,
            resp.status_code,
            resp.headers.get("location", ""),
            "flash.error.no_such_stay",
        )
    )
    csrf = _csrf(client, "/reservations/101")
    resp = client.post(
        "/reservations/101/submit",
        data={"_csrf": csrf, "allow_resend": "1"},
        follow_redirects=False,
    )
    cases.append(
        _case(
            "confirm_duplicate_resend",
            "POST",
            "/reservations/101/submit",
            f"_csrf={csrf}&allow_resend=1",
            owner_id,
            resp.status_code,
            resp.headers.get("location", ""),
            "flash.error.confirm_duplicate_resend",
        )
    )
    return cases


def main() -> int:
    check = "--check" in sys.argv
    sys.path.insert(0, str(APP))
    db_path = tempfile.mkdtemp()
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_TERMS_VERSION", "t1")
    os.environ.setdefault("UBYHOST_PRIVACY_VERSION", "p1")
    os.environ.setdefault("UBYHOST_DPA_VERSION", "d1")
    os.environ["UBYHOST_DB"] = str(Path(db_path) / "golden.sqlite3")
    from app import db

    db.init_db()
    cases = _signed_out_cases()
    owner_id = _seed()
    cases.extend(_signed_in_cases(owner_id))
    doc = {"now": NOW.isoformat(), "seed": [], "cases": cases}
    golden = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if check:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == golden:
            return 0
        print("stale golden", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(golden, encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())