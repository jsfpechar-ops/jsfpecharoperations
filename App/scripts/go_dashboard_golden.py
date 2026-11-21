"""Write go/internal/web/hostweb/testdata/dashboard_golden.json from Python GET /.

Run from App/:
    .venv/bin/python scripts/go_dashboard_golden.py
    .venv/bin/python scripts/go_dashboard_golden.py --check
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "hostweb" / "testdata" / "dashboard_golden.json"

STAMP = "2026-06-15T12:00:00+00:00"
PUBLIC = "https://ubyhost.example"
APP_HOST = "app.ubyhost.example"
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}

DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "aria-current", "class", "aria-label"}


def visible_lines(page: str) -> list[str]:
    start = page.find('<div class="ui-page"')
    if start < 0:
        start = page.find('<main id="content"')
    if start < 0:
        return []
    page = page[start:]
    end = page.find('<div class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    for tok in TOKEN.findall(page):
        if not tok.startswith("<"):
            text = SPACE.sub(" ", html.unescape(tok)).strip(" ")
            if text:
                out.append(text)
            continue
        m = TAG.match(tok)
        if not m or m.group(1) == "/":
            continue
        name = m.group(2).lower()
        attrs = {}
        for a in ATTR.finditer(tok[m.end():]):
            key = a.group(1).lower()
            has = "=" in a.group(0)
            value = html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))
            if key == "class":
                value = " ".join(value.split())
            attrs[key] = (has, value)
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "session_version", "created_at"],
     "rows": [
         [880001, "empty-host", "x", "host", 1, STAMP],
         [880002, "stay-host", "x", "host", 1, STAMP],
     ]},
    {"table": "legal_acceptance", "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, ver, STAMP, "clickwrap"] for uid in (880001, 880002) for doc, ver in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "created_at"],
     "rows": [[880010, 880002, "Entity", STAMP]]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "legal_entity_id", "permalink_token", "active", "created_at"],
     "rows": [[880100, 880002, "Chrome Flat", 880010, "tokdash", 1, STAMP]]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status", "source", "created_at", "updated_at"],
     "rows": [[8801001, 880100, "golden-1001", "2026-06-15", "2026-06-17", "active", "manual", STAMP, STAMP]]},
]

CASES = [
    ("signed_out_landing", 0, "en", PUBLIC),
    ("signed_in_empty", 880001, "en", PUBLIC),
    ("signed_in_with_stay", 880002, "en", PUBLIC),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row))


def render() -> str:
    from fastapi.testclient import TestClient

    from app import auth, config, db
    from app.main import app

    db.init_db()
    _seed(db)
    config.PUBLIC_BASE_URL = PUBLIC
    config.APP_BASE_URL = f"https://{APP_HOST}"
    client = TestClient(app, raise_server_exceptions=True)
    cases = []
    for name, user, lang, host in CASES:
        client.cookies.clear()
        cookies = {"ubyhost_lang": lang}
        if user:
            cookies[auth.SESSION_COOKIE] = auth.issue_session(user, 1)
        host_name = host.split("://", 1)[-1].split("/", 1)[0]
        headers = {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()), "Host": host_name}
        response = client.get("/", headers=headers, follow_redirects=False)
        cases.append({
            "name": name, "path": "/", "user": user, "lang": lang,
            "headers": {"Host": headers["Host"]},
            "status": response.status_code,
            "lines": visible_lines(response.text) if response.status_code == 200 else [],
        })
    return json.dumps({
        "env": {
            "UBYHOST_PUBLIC_BASE_URL": PUBLIC,
            "UBYHOST_APP_BASE_URL": f"https://{APP_HOST}",
            "UBYHOST_SIGNUP_ENABLED": "0",
        },
        "seed": SEED, "cases": cases,
    }, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    os.environ.pop("UBYHOST_DATABASE_URL", None)
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-dashboard-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ["UBYHOST_DB"] = str(tmp / "dash.sqlite3")
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))