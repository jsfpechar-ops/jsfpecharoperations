"""Write go/internal/web/stays/testdata/stays_visible_golden.json from Python GET /reservations.

Run from App/:

    .venv/bin/python scripts/go_stays_list_golden.py
    .venv/bin/python scripts/go_stays_list_golden.py --check

Seeds the same six stays as go/internal/web/stays/query_test.go (range=all,
clock 2026-06-15 UTC). visible_lines() matches staysVisibleLines in visible_text.go.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "stays" / "testdata" / "stays_visible_golden.json"

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 6, 15)

DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
SPACE = re.compile(r"[ \t\n\r\f\v]+")

CASES = [
    ("list all en page 1", "en", "/reservations?range=all&lang=en"),
    ("list all en page 2", "en", "/reservations?range=all&lang=en&page=2"),
]


def visible_lines(page: str) -> list[str]:
    mark = '<div class="head stays-head"'
    start = page.find(mark)
    if start < 0:
        return []
    gt = page.find(">", start)
    page = page[gt + 1 :] if gt >= 0 else page[start:]
    end = page.find('class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    skip = False
    for tok in TOKEN.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text and not skip:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m:
            continue
        name = m.group(2).lower()
        if m.group(1) == "/":
            if name == "a":
                skip = False
            continue
        if 'class="sr-only"' in tok or "ui-ph-back" in tok:
            skip = True
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def _seed():
    from app import acceptance, auth, db, login_link

    db.init_db()
    stamp = NOW.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    owner_id = auth.create_account("stays-parity@example.test", "Stays parity", username="stays-parity")
    db.execute("UPDATE user_account SET session_version = 1 WHERE id = ?", (owner_id,))
    versions = acceptance.current_versions()
    for i, doc in enumerate(("terms", "privacy", "dpa")):
        db.execute(
            "INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) "
            "VALUES (?,?,?,?,?,?)",
            (9000 + i, owner_id, doc, versions[doc], stamp, "clickwrap"),
        )
    entity_id = db.insert("legal_entity", {"owner_user_id": owner_id, "name": "Entity", "created_at": stamp})
    apt_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "legal_entity_id": entity_id,
            "internal_name": "Chrome Flat",
            "permalink_token": "tokparity",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": stamp,
        },
    )
    specs = [
        ("2026-06-10", "2026-06-12", "airbnb", "Sofia", "Costa"),
        ("2026-06-13", "2026-06-14", "booking", None, None),
        ("2026-06-15", "2026-06-17", "manual", "Lead", "Three"),
        ("2026-06-18", "2026-06-20", "manual", "Lead", "Four"),
        ("2026-06-21", "2026-06-23", "manual", "Lead", "Five"),
        ("2026-06-24", "2026-06-26", "manual", None, None),
    ]
    for i, (d_from, d_to, source, gn, sn) in enumerate(specs):
        res_id = db.insert(
            "reservation",
            {
                "apartment_id": apt_id,
                "uid": f"uid-{i}",
                "date_from": d_from,
                "date_to": d_to,
                "status": "active" if i < 5 else "cancelled",
                "source": source,
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        if gn:
            db.insert(
                "guest",
                {
                    "reservation_id": res_id,
                    "first_name": gn,
                    "surname": sn or "",
                    "is_lead": 1,
                    "entered_by": "guest",
                    "created_at": stamp,
                    "updated_at": stamp,
                },
            )
    return owner_id


def render() -> str:
    from fastapi.testclient import TestClient

    from app import db, deadlines
    from app.main import app
    from app.routes import admin as routes

    _seed()
    routes.datetime = _Frozen
    _frozen_local = datetime(2026, 6, 15, 12, 0, 0)
    _real_local_now = deadlines.local_now

    def _local_now(now=None):
        if now is None:
            return _frozen_local
        return _real_local_now(now)

    deadlines.local_now = _local_now

    def csrf(client: TestClient) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    from app import login_link

    client = TestClient(app)
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", ("stays-parity",))
    resp = client.post(
        "/login/link",
        data={"t": login_link.issue(account), "_csrf": csrf(client)},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    out_cases = []
    for name, lang, path in CASES:
        client.cookies.set("ubyhost_lang", lang)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200, response.text[:500]
        out_cases.append({"name": name, "lang": lang, "path": path, "lines": visible_lines(response.text)})
    golden = {"now": NOW.isoformat(), "today": str(TODAY), "cases": out_cases}
    return json.dumps(golden, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_stays_list_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-stays-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "stays_visible.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_TERMS_VERSION", "t1")
    os.environ.setdefault("UBYHOST_PRIVACY_VERSION", "p1")
    os.environ.setdefault("UBYHOST_DPA_VERSION", "d1")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))