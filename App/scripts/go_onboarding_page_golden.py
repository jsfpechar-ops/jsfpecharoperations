"""Write go/internal/web/onboarding/testdata/onboarding_page_golden.json from the real Python page.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_onboarding_page_golden.py          write the file
    .venv/bin/python scripts/go_onboarding_page_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the fixed rows in SEED, signs each
case in with auth.issue_session and renders GET /onboarding through the real
FastAPI app (TestClient). A case keeps visible_lines() of the page area
(div.ui-page): the visible text and the key attributes, not the bytes.
go/internal/web/onboarding/onboarding_page_test.go seeds PostgreSQL from the
same SEED, renders the Go page and compares with the same normaliser. A column
named in a table's "encrypt" list holds plain text here; each side stores it
encrypted with its own key (db.encrypt_secret here, secure.MultiFernet in Go).
App/tests/test_go_onboarding_page_golden.py fails when this file is stale.
Brief 1595.
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
OUT = APP.parent / "go" / "internal" / "web" / "onboarding" / "testdata" / "onboarding_page_golden.json"

STAMP = "2026-01-01T00:00:00+00:00"
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}
PUBLIC_BASE = "https://golden.example.test"
USERS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


def _apartment(aid, owner, name, *, entity=None, idub="100227887600", mark="ABCDE", house="1234", zipcode="12000",
               obec="Praha", ws_user="UBY-WS12cdef", password="pw-golden", token=None, pin=None,
               policy="off", archived=None):
    return [aid, owner, name, entity, idub, mark, "Golden stay", "host@example.test", "Praha 2", obec, "Vinohrady",
            "Korunni", house, "", zipcode, ws_user, password, token, pin, policy, 1, archived, STAMP]


def _stay(rid, apartment, source="manual", status="active"):
    return [rid, apartment, f"golden-{rid}", "2026-02-01", "2026-02-03", source, status, STAMP, STAMP]


# Hosts: 1 admin (previews 5); 2 empty; 3 entity without ICO, checklist skipped;
# 4 ready entity, property without house number, an archived ready one; 5 one
# finished property with a slug (also previewed by the admin); 6 two finished
# properties; 7 a password no key opens, an active feed; 8 one finished
# property without a permanent token or PIN; 9 only an iCal stay and a
# cancelled manual one, an inactive feed.
SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[uid, f"host{uid}@example.test", "x", "admin" if uid == 1 else "host", STAMP] for uid in USERS]},
    {"table": "legal_acceptance", "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in USERS for doc, version in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "seat", "ico", "contact_email", "created_at"],
     "rows": [
         [31, 3, "Half Entity", "Praha", None, "e3@example.test", STAMP],
         [41, 4, "Ready Four", "Praha", "12345678", "e4@example.test", STAMP],
         [51, 5, "Ready Five", "Brno", "23456789", "e5@example.test", STAMP],
         [61, 6, "Ready Six", "Brno", "34567890", "e6@example.test", STAMP],
         [71, 7, "Ready Seven", "Brno", "45678901", "e7@example.test", STAMP],
         [81, 8, "Ready Eight", "Brno", "56789012", "e8@example.test", STAMP],
         [91, 9, "Ready Nine", "Brno", "67890123", "e9@example.test", STAMP],
         [99, 2, "  ", "Brno", "1", "x@example.test", STAMP],
     ]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "legal_entity_id", "uby_idub", "uby_mark", "uby_name",
                 "uby_contact", "addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no",
                 "addr_orient_no", "addr_zip", "uby_ws_user", "uby_ws_password_enc", "permalink_token",
                 "permalink_pin", "passport_photo_policy", "active", "archived_at", "created_at"],
     "encrypt": ["uby_ws_password_enc"],
     "rows": [
         _apartment(41, 4, "Four <Loft>", entity=41, house="", token="tok41"),
         _apartment(42, 4, "Four archived", entity=41, token="tok42", archived="2026-01-02"),
         _apartment(51, 5, "Five & Studio", entity=51, token="tok51", pin="246810", policy="required_foreign"),
         _apartment(61, 6, "Six A", entity=61, token="tok61", pin="111111"),
         _apartment(62, 6, "Six B", entity=61, token="tok62", pin="222222"),
         _apartment(71, 7, "Seven", entity=71, password=None, token="tok71", pin="777777"),
         _apartment(81, 8, "Eight", entity=81, token=None, pin=None),
         _apartment(91, 9, "Nine", entity=91, token="tok91", pin="999999"),
     ]},
    # A token that is not Fernet: decrypt_secret gives "" (password missing).
    {"table": "apartment_update", "columns": ["id", "uby_ws_password_enc"], "rows": [[71, "gAAAAAnot-a-token"]]},
    {"table": "apartment_slug", "columns": ["slug", "apartment_id", "is_current", "created_at"],
     "rows": [["five-studio-abc234", 51, 1, STAMP], ["five-old-xyz789", 51, 0, STAMP],
              ["six-a-def456", 61, 1, STAMP]]},
    {"table": "ical_feed", "columns": ["id", "apartment_id", "url", "active", "created_at"],
     "rows": [[1, 61, "https://cal.example.test/61.ics", 1, STAMP], [2, 71, "https://cal.example.test/71.ics", 1, STAMP],
              [3, 91, "https://cal.example.test/91.ics", 0, STAMP]]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "source", "status", "created_at", "updated_at"],
     "rows": [_stay(1, 42), _stay(2, 51), _stay(3, 62), _stay(4, 81), _stay(5, 91, source="ical"),
              _stay(6, 91, status="cancelled")]},
    {"table": "settings", "columns": ["key", "value"], "rows": [["onboarding_dismissed_3", "1"], ["onboarding_dismissed_4", "0"]]},
]

# name, user, previewed workspace (0: none), language, UBYHOST_UBYPORT_ENV (None: unset).
CASES = [
    ("signed out", 0, 0, "en", None),
    ("empty workspace", 2, 0, "en", None),
    ("empty workspace in Czech, demo off", 2, 0, "cs", "test"),
    ("entity without ICO, skipped", 3, 0, "en", "prod"),
    ("property without house number", 4, 0, "en", "mock"),
    ("finished single property", 5, 0, "en", None),
    ("finished single property in Czech", 5, 0, "cs", "test"),
    ("finished single property in Vietnamese", 5, 0, "vi", "MOCK"),
    ("admin previews the finished host", 1, 5, "en", "test"),
    ("two finished properties", 6, 0, "en", "test"),
    ("password no key opens", 7, 0, "vi", "test"),
    ("finished without token or PIN", 8, 0, "en", "test"),
    ("only an iCal stay", 9, 0, "cs", ""),
]

# visible_lines: keep in step with onboardingPageVisibleLines in onboarding_page_test.go.
DROP = [re.compile(p, re.S | re.I) for p in (
    r"<!--.*?-->", r"<script\b.*?</script>", r"<style\b.*?</style>", r"<svg\b.*?</svg>")]
TOKEN = re.compile(r"<[^>]*>|[^<]+")
TAG = re.compile(r"^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)")
ATTR = re.compile(
    r"""([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?""")
SPACE = re.compile(r"[ \t\n\r\f\v]+")
KEPT = {"id", "href", "action", "method", "name", "value", "type", "selected", "checked", "required", "for",
        "aria-current", "class", "aria-label", "aria-controls", "data-copy", "target"}


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


def _seed(db) -> None:
    for table in SEED:
        if table["table"] == "apartment_update":
            for aid, value in table["rows"]:
                db.execute("UPDATE apartment SET uby_ws_password_enc = ? WHERE id = ?", (value, aid))
            continue
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        secret = [table["columns"].index(c) for c in table.get("encrypt", [])]
        for row in table["rows"]:
            row = list(row)
            for i in secret:
                if row[i] is not None:
                    row[i] = db.encrypt_secret(row[i])
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def render() -> str:
    from fastapi.testclient import TestClient

    from app import auth, config, db
    from app.main import app

    db.init_db()
    _seed(db)
    client = TestClient(app)
    cases = []
    for name, user, workspace, lang, env in CASES:
        config.UBYPORT_ENV = "mock" if env is None else env.lower()
        client.cookies.clear()
        cookies = {"ubyhost_lang": lang}
        if user:
            cookies[auth.SESSION_COOKIE] = auth.issue_session(
                user, 1, workspace_user_id=workspace or None,
                impersonation_started_at=int(time.time()) if workspace else None)
        header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        response = client.get("/onboarding", headers={"Cookie": header}, follow_redirects=False)
        cases.append({"name": name, "user": user, "workspace": workspace, "lang": lang, "env": env,
                      "status": response.status_code, "location": response.headers.get("location"),
                      "lines": visible_lines(response.text) if response.status_code == 200 else []})
    golden = {"public_base": PUBLIC_BASE, "versions": VERSIONS, "seed": SEED, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_onboarding_page_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "onboarding_page_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
