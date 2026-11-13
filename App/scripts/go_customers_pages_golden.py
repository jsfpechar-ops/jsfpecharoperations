"""Write go/internal/web/customers/testdata/customers_pages_golden.json from the real Python pages.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_customers_pages_golden.py          write the file
    .venv/bin/python scripts/go_customers_pages_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the seed of admin_customers_golden.py
(the Go tests seed PostgreSQL from that script's JSON), signs in as the admin
through TestClient with the route clock frozen at NOW, and renders each page
case. A case keeps visible_lines() of the page: the visible text and the key
attributes of the page area (div.ui-page), not the bytes. pages_test.go renders
the Go pages and compares with the same normaliser. The "utcnow" section is
db.utcnow() at a fixed instant, for the audit "at" format.
App/tests/test_go_customers_pages_golden.py fails when this file is stale.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "customers" / "testdata" / "customers_pages_golden.json"

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
STAMP_AT = datetime(2026, 11, 13, 12, 0, 7, 654321, tzinfo=timezone.utc)

# name, language, billing on, path. Seed: 45 hosts (ids 2-16, 101-130), page size 25.
CASES = [
    ("list first page", "en", True, "/admin/customers"),
    ("list in Czech, billing off", "cs", False, "/admin/customers"),
    ("list older page", "en", True, "/admin/customers?after=110"),
    ("list newer page", "en", True, "/admin/customers?before=105"),
    ("list ending", "en", True, "/admin/customers?state=ending"),
    ("list search special characters", "en", True, "/admin/customers?q=anna_100%25&plan=standard"),
    ("list max active in Vietnamese", "vi", True, "/admin/customers?plan=max&state=active&q=Bulk"),
    ("list empty, non-ASCII search", "en", True, "/admin/customers?q=%C5%BDlu%C5%A5+%26+co"),
    ("list bad cursor, repeated q", "en", True, "/admin/customers?after=abc&q=x&q=+Nov+"),
]

# visible_lines: keep in step with visibleLines in go/internal/web/customers/pages_test.go.
DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked",
        "required", "for", "aria-current"}


def visible_lines(page: str) -> list[str]:
    """The page area as lines: each text run, and each tag that has a KEPT attribute."""
    start = page.find('<div class="ui-page"')
    if start < 0:
        return []
    page = page[start:]
    end = page.find('<div class="page-skeleton"')
    if end >= 0:
        page = page[:end]
    for pattern in DROP:
        page = pattern.sub("", page)
    out = []
    skip = False  # inside the header back link: Python shows an icon, Go a label (gap)
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
        attrs = {}
        for a in ATTR.finditer(tok[m.end():]):
            key = a.group(1).lower()
            has_value = "=" in a.group(0)
            value = html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))
            attrs[key] = (has_value, value)
        if "ui-ph-back" in attrs.get("class", (False, ""))[1].split():
            skip = True
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


class _FrozenStamp(datetime):
    @classmethod
    def now(cls, tz=None):
        return STAMP_AT if tz is None else STAMP_AT.astimezone(tz)


def render() -> str:
    from fastapi.testclient import TestClient

    import admin_customers_golden as base
    from app import acceptance, config, db, login_link
    from app.main import app
    from app.routes import admin_customers as routes

    db.init_db()
    versions = acceptance.current_versions()
    for table in base._seed():
        for row in table["rows"]:
            if table["table"] == "legal_acceptance":
                row["version"] = versions[row["document"]]
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row.values()))

    def csrf(client) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    def admin_client(lang):
        client = TestClient(app)
        client.cookies.set("ubyhost_lang", lang)
        account = db.query_one("SELECT * FROM user_account WHERE username = ?", ("admin",))
        response = client.post("/login/link", data={"t": login_link.issue(account), "_csrf": csrf(client)},
                               follow_redirects=False)
        assert response.status_code == 303 and "/login" not in response.headers["location"]
        return client

    clients = {lang: admin_client(lang) for lang in ("en", "cs", "vi")}
    routes.datetime = _Frozen
    cases = []
    for name, lang, billing_on, path in CASES:
        config.BILLING_ENABLED = billing_on
        response = clients[lang].get(path, follow_redirects=False)
        cases.append({"name": name, "lang": lang, "billing": billing_on, "path": path,
                      "status": response.status_code, "lines": visible_lines(response.text)})
    real = db.datetime
    db.datetime = _FrozenStamp
    try:
        stamp = db.utcnow()
    finally:
        db.datetime = real
    golden = {"utcnow": {"at": STAMP_AT.isoformat(), "stamp": stamp}, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_customers_pages_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "customers_pages_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
