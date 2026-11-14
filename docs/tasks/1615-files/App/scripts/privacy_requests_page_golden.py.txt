"""Write go/internal/web/privacy/testdata/privacy_requests_page_golden.json from the real Python page.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/privacy_requests_page_golden.py          write the file
    .venv/bin/python scripts/privacy_requests_page_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with SEED, signs each host in through
TestClient with a real login link (legal versions t1, p1, d1, as the Go tests
set them) and renders GET /privacy-requests for each CASES entry. A case keeps
visible_lines() of the page: the visible text and the key attributes of the
page area (div.ui-page), not the bytes. go/internal/web/privacy/page_test.go
seeds PostgreSQL from the same SEED, renders the Go page and compares with the
same normaliser. App/tests/test_go_privacy_requests_page.py fails when this
file is stale.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "privacy" / "testdata" / "privacy_requests_page_golden.json"

STAMP = "2026-09-01T00:00:00+00:00"
VERSIONS = {"terms": "t1", "privacy": "p1", "dpa": "d1"}

# Hosts 1 and 2 own the requests; 49 has no owner and 70 is host 2's, so
# neither may show on host 1's page. received_at and due_at cover the formats
# the create route stores (date with midnight UTC, a space separator, an
# offset, a naive value, a fraction) and two it never writes (passed through).
SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "email", "password_hash", "role", "active", "session_version", "created_at"],
        "rows": [
            [1, "owner@example.test", "owner@example.test", "x", "host", 1, 1, STAMP],
            [2, "other@example.test", "other@example.test", "x", "host", 1, 1, STAMP],
            [3, "empty@example.test", "empty@example.test", "x", "host", 1, 1, STAMP],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [101, 1, "terms", "t1", STAMP, "clickwrap"],
            [102, 1, "privacy", "p1", STAMP, "clickwrap"],
            [103, 1, "dpa", "d1", STAMP, "clickwrap"],
            [104, 2, "terms", "t1", STAMP, "clickwrap"],
            [105, 2, "privacy", "p1", STAMP, "clickwrap"],
            [106, 2, "dpa", "d1", STAMP, "clickwrap"],
            [107, 3, "terms", "t1", STAMP, "clickwrap"],
            [108, 3, "privacy", "p1", STAMP, "clickwrap"],
            [109, 3, "dpa", "d1", STAMP, "clickwrap"],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "created_at"],
        "rows": [[1, 1, "Byt A", STAMP], [2, 2, "Byt B", STAMP], [3, 3, "Byt C", STAMP]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to",
                    "status", "created_at", "updated_at"],
        "rows": [[1, 1, "manual", "r1", "2026-10-01", "2026-10-03", "active", STAMP, STAMP]],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "created_at", "updated_at"],
        "rows": [[7, 1, STAMP, STAMP], [8, 1, STAMP, STAMP]],
    },
    {
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel", "request_type",
                    "subject_kind", "guest_id", "identity_checked_at", "status", "closed_at",
                    "outcome_note", "created_at", "updated_at"],
        "rows": [
            [49, None, STAMP, "2026-10-01T00:00:00+00:00", "other", "other", "other",
             None, None, "open", None, None, STAMP, STAMP],
            [61, 1, "2026-11-01T00:00:00+00:00", "2026-12-01T00:00:00+00:00", "email", "access",
             "guest", 7, None, "open", None, None, STAMP, STAMP],
            [62, 1, "2026-10-02 08:00", "2026-11-02T08:00:00", "post", "erasure",
             "guest", 8, STAMP, "extended", None, 'Sent "the export" <b>&</b> it\'s done', STAMP, STAMP],
            [63, 1, "2026-03-31T23:15:00+02:00", "2026-04-30T23:15:00+02:00", "in_person", "rectification",
             "host_user", None, STAMP, "fulfilled", STAMP, "Done", STAMP, STAMP],
            [64, 1, "garbage", "2027-01-31T10:00:00.500000", "support", "portability",
             "other", None, None, "open", None, "", STAMP, STAMP],
            [65, 1, "2026-05-31T10:00:00.5Z", "2026-07-01T00:00:00+00:00", "other", "objection",
             "guest", None, None, "withdrawn", STAMP, "Asked to stop", STAMP, STAMP],
            [66, 1, "2026-02-28", "2026-03-28T00:00:00", "email", "restriction",
             "guest", None, None, "refused", STAMP, None, STAMP, STAMP],
            [67, 1, "2026-11-01", "2026-12-01T00:00:00+00:00", "email", "other",
             "other", None, None, "open", None, "Žluťoučký kůň", STAMP, STAMP],
            [70, 2, STAMP, "2026-10-01T00:00:00+00:00", "email", "access",
             "guest", None, None, "open", None, None, STAMP, STAMP],
        ],
    },
]

# name, account, language cookie, path.
CASES = [
    ("host with requests", 1, "en", "/privacy-requests"),
    ("host with requests in Czech", 1, "cs", "/privacy-requests"),
    ("host with requests in Vietnamese", 1, "vi", "/privacy-requests"),
    ("host with one request, query ignored", 2, "en", "/privacy-requests?status=open&page=2"),
    ("host without requests", 3, "en", "/privacy-requests"),
    ("host without requests in Czech", 3, "cs", "/privacy-requests"),
]

# visible_lines: keep in step with visibleLines in go/internal/web/privacy/page_test.go
# (the same normaliser as scripts/go_customers_pages_golden.py, plus "open").
DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked",
        "required", "for", "aria-current", "aria-label", "open", "inputmode", "class"}


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
            has_value = "=" in a.group(0)
            value = html.unescape((a.group(2) or "") + (a.group(3) or "") + (a.group(4) or ""))
            if key == "class":
                value = " ".join(value.split())
            attrs[key] = (has_value, value)
        if attrs.get("name", (False, ""))[1] == "_csrf":
            attrs["value"] = (True, "*")
        parts = [k + ("=" + v if has else "") for k, (has, v) in sorted(attrs.items()) if k in KEPT]
        if parts:
            out.append("<" + name + " " + " ".join(parts) + ">")
    return out


def render() -> str:
    from fastapi.testclient import TestClient

    from app import config, db, login_link
    from app.main import app

    config.TERMS_VERSION = VERSIONS["terms"]
    config.PRIVACY_VERSION = VERSIONS["privacy"]
    config.DPA_VERSION = VERSIONS["dpa"]
    db.init_db()
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)

    def csrf(client) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    def host_client(account_id: int, lang: str):
        client = TestClient(app)
        client.cookies.set("ubyhost_lang", lang)
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (account_id,))
        response = client.post("/login/link", data={"t": login_link.issue(account), "_csrf": csrf(client)},
                               follow_redirects=False)
        assert response.status_code == 303 and "/login" not in response.headers["location"], response.headers
        return client

    cases = []
    for name, account, lang, path in CASES:
        response = host_client(account, lang).get(path, follow_redirects=False)
        cases.append({"name": name, "account": account, "lang": lang, "path": path,
                      "status": response.status_code, "location": response.headers.get("location", ""),
                      "lines": visible_lines(response.text)})
    golden = {"versions": VERSIONS, "seed": SEED, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/privacy_requests_page_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "privacy_requests_page_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
