"""Golden visible text for GET /submissions, GET /submissions/{id}, GET /reservations/{id}.

Run from App/:

    .venv/bin/python scripts/go_go_submissions_reservations_read_golden.py
    .venv/bin/python scripts/go_go_submissions_reservations_read_golden.py --check

The Go test in go/internal/web/submissions/visible_text_test.go replays the
same seed on PostgreSQL when UBYHOST_TEST_DATABASE_URL is set.
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
OUT = (
    APP.parent
    / "go"
    / "internal"
    / "web"
    / "submissions"
    / "testdata"
    / "submissions_read_golden.json"
)

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 6, 15)

DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
SPACE = re.compile(r"[ \t\n\r\f\v]+")

STATES = (
    "ok", "ok_duplicate", "partial", "error", "failed", "transport_error",
    "outcome_unknown", "not_configured", "running", "noop",
)


def visible_list(page: str) -> list[str]:
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
    out, skip = [], False
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


def visible_detail(page: str) -> list[str]:
    mark = '<div class="e-page"'
    start = page.find(mark)
    if start < 0:
        return []
    page = page[start:]
    end = page.find('class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    tech = page.find('<details class="panel technical"')
    if tech >= 0:
        page = page[:tech]
    for pattern in DROP:
        page = pattern.sub("", page)
    out, skip = [], False
    for tok in TOKEN.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text and not skip:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m:
            continue
        if m.group(1) == "/":
            if m.group(2).lower() == "a":
                skip = False
            continue
        if 'class="sr-only"' in tok:
            skip = True
    return out


def visible_stay_head(page: str) -> list[str]:
    mark = '<div class="e-page"'
    start = page.find(mark)
    if start < 0:
        return []
    page = page[start:]
    guests = page.find('id="guests"')
    if guests >= 0:
        page = page[:guests]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    for tok in TOKEN.findall(page):
        if tok.startswith("<"):
            continue
        text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
        if text:
            out.append(text)
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def _seed():
    from app import acceptance, auth, db, login_link

    db.init_db()
    stamp = NOW.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    owner_id = auth.create_account("reports-parity@example.test", "Reports parity", username="reports-parity")
    db.execute("UPDATE user_account SET session_version = 1 WHERE id = ?", (owner_id,))
    versions = acceptance.current_versions()
    for i, doc in enumerate(("terms", "privacy", "dpa")):
        db.execute(
            "INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) "
            "VALUES (?,?,?,?,?,?)",
            (9100 + i, owner_id, doc, versions[doc], stamp, "clickwrap"),
        )
    entity_id = db.insert("legal_entity", {"owner_user_id": owner_id, "name": "Entity", "created_at": stamp})
    apt_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "legal_entity_id": entity_id,
            "internal_name": "Chrome Flat",
            "permalink_token": "tokreports",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": stamp,
        },
    )
    res_id = db.insert(
        "reservation",
        {
            "apartment_id": apt_id,
            "uid": "uid-parity-stay",
            "date_from": "2026-06-15",
            "date_to": "2026-06-17",
            "status": "active",
            "source": "manual",
            "created_at": stamp,
            "updated_at": stamp,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": res_id,
            "first_name": "Lead",
            "surname": "Guest",
            "nationality": "CZE",
            "doc_number": "AB123456",
            "is_lead": 1,
            "entered_by": "guest",
            "created_at": stamp,
            "updated_at": stamp,
        },
    )
    submission_ids = []
    for i, state in enumerate(STATES):
        sid = db.insert(
            "submission",
            {
                "apartment_id": apt_id,
                "created_at": stamp,
                "mode": "manual",
                "guest_ids": json.dumps([guest_id]),
                "state": "running",
            },
        )
        if state == "running":
            submission_ids.append(sid)
            continue
        db.update(
            "submission",
            sid,
            {
                "state": state,
                "pseudo_stamp": f"ST{i:02d}" if state in ("ok", "ok_duplicate", "partial") else None,
                "header_errors": None if state != "error" else "112;",
                "record_errors": json.dumps(["112;"]) if state == "error" else json.dumps([""]),
                "finished_at": stamp,
                "error_text": "smtp timeout" if state == "transport_error" else None,
                "receipt_pdf": "e==" if state in ("ok", "ok_duplicate", "partial") else None,
            },
        )
        submission_ids.append(sid)
    return owner_id, submission_ids[0], submission_ids[4], res_id


def render() -> str:
    from fastapi.testclient import TestClient

    from app import db, deadlines
    from app.main import app
    from app.routes import admin as routes

    owner_id, ok_id, err_id, res_id = _seed()
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
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", ("reports-parity",))
    resp = client.post(
        "/login/link",
        data={"t": login_link.issue(account), "_csrf": csrf(client)},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    cases = []
    client.cookies.set("ubyhost_lang", "en")
    for path, kind, name, fn in (
        ("/submissions?lang=en", "list", "list en", visible_list),
        (f"/submissions/{ok_id}?lang=en", "detail", "detail ok en", visible_detail),
        (f"/submissions/{err_id}?lang=en", "detail", "detail error en", visible_detail),
        (f"/reservations/{res_id}?lang=en", "stay", "stay detail en head", visible_stay_head),
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200, (path, response.status_code, response.text[:400])
        cases.append({"name": name, "lang": "en", "path": path, "kind": kind, "lines": fn(response.text)})
    golden = {"now": NOW.isoformat(), "today": str(TODAY), "owner_id": owner_id, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_go_submissions_reservations_read_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-submissions-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "submissions_read.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_TERMS_VERSION", "t1")
    os.environ.setdefault("UBYHOST_PRIVACY_VERSION", "p1")
    os.environ.setdefault("UBYHOST_DPA_VERSION", "d1")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))