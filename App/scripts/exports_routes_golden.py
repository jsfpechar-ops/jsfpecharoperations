"""Write go/internal/web/exports/testdata/exports_routes_golden.json (briefs 1606-1609).

The request cases of GET /housebook/pdfs.zip, POST /settings/workspace-export,
GET /settings/archived and POST /settings/purge-expired (and the refusals of
GET /guests/{id}/form.pdf) against the Python app on PostgreSQL: status, the
compared headers, every audit row written, the zip entries, the <main> of the
archive page and, after each purge, the database state and the photo files.
The rows are the made-up seed of scripts/exports_golden.py plus EXTRAS below;
the clock is frozen at exports_golden.NOW everywhere the routes read it.

    UBYHOST_TEST_DATABASE_URL=postgresql://... python scripts/exports_routes_golden.py
    ... scripts/exports_routes_golden.py --check     exit 1 when stale
"""

import base64
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "scripts"))
import exports_golden as eg  # noqa: E402

OUT = APP.parent / "go" / "internal" / "web" / "exports" / "testdata" / "exports_routes_golden.json"
_AT = datetime.fromisoformat(eg.NOW)


class _Clock(datetime):
    """datetime.now() at the golden instant: naive local (UTC in the golden) or in tz."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102
        return eg.NOW_LOCAL if tz is None else _AT.astimezone(tz)


class _Today(date):
    @classmethod
    def today(cls):  # noqa: D102
        return eg.NOW_LOCAL.date()


DB = "exports_routes_golden"
def extras():
    """The rows these cases add to the exports_golden seed (all made up)."""
    tok = eg.token
    def bt(s):  # bytea literal of a fernet token
        return "convert_to('" + tok(s) + "', 'UTF8')"
    sql = [
        "UPDATE user_account SET deletion_due_at = '2026-12-13T00:00:00+00:00' WHERE id = 1",
        "INSERT INTO legal_entity (id, owner_user_id, name, ico, archived_at, created_at) VALUES "
        "(1, 1, 'Novák & syn s.r.o.', '12345678', '2026-03-01T10:00:00+00:00', '2026-01-01'),"
        "(2, 1, 'Aktivní', NULL, NULL, '2026-01-01'),"
        "(3, 1, 'Bez IČO <b>', NULL, '2026-04-01T10:00:00+00:00', '2026-01-01')",
        "INSERT INTO apartment (id, owner_user_id, internal_name, archived_at, created_at) VALUES "
        "(9, 1, 'Stará chata', '2026-02-01T00:00:00+00:00', '2026-01-01')",
        "INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, archived_at, created_at, updated_at) VALUES "
        "(10, 9, 'ical', 'u10', '2025-07-01', '2025-07-04', 'confirmed', '2026-02-02T00:00:00+00:00', '2026-01-01', '2026-01-01'),"
        "(20, 7, 'ical', 'u20', '2019-03-01', '2019-03-05', 'confirmed', NULL, '2019-01-01', '2019-01-01'),"
        "(50, 50, 'ical', 'u50', '2026-09-01', '2026-09-03', 'confirmed', NULL, '2026-01-01', '2026-01-01')",
        "INSERT INTO guest (id, reservation_id, surname, first_name, nationality, submit_state, created_at, updated_at) VALUES "
        "(30, 20, 'Old', 'Stay', 'AUT', 'sent', '2019-01-01', '2019-01-01'),"
        "(31, 20, 'Old', 'Two', 'AUT', 'sent', '2019-01-01', '2019-01-01')",
        "INSERT INTO guest (id, reservation_id, surname, first_name, nationality, submit_state, created_at, updated_at) "
        "SELECT 500 + n, 50, 'Many', 'G' || n, 'AUT', 'pending', '2026-01-01', '2026-01-01' FROM generate_series(1, 101) n",
        "INSERT INTO guest (id, reservation_id, surname, first_name, nationality, doc_number_enc, submit_state, archived_at, created_at, updated_at) VALUES "
        "(401, 40, 'Broken', 'Archived', 'AUT', '" + eg.CORRUPT_TOKEN + "', 'pending', '2026-05-05T00:00:00+00:00', '2026-01-01', '2026-01-01')",
        "INSERT INTO invoice (id, legal_entity_id, owner_user_id, kind, seq_year, seq_no, number, vs, lang, vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler, created_at, pdf_blob) VALUES "
        "(1, 2, 1, 'invoice', 2026, 1, '2026-0001', '2026000100', 'cs', 'non_payer', '2026-05-01', 'S', 'Seat', 'B', 100, '2026-05-01', convert_to('%PDF-1.4 invoice one', 'UTF8')),"
        "(2, 2, 1, 'invoice', 2026, 2, '2026-0002', '2026000200', 'cs', 'non_payer', '2026-05-02', 'S', 'Seat', 'B', 100, '2026-05-02', NULL)",
        "INSERT INTO stay_fee_filing (id, apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days, total_due_czk, total_collected_czk, pdf_enc, csv_enc, created_at, superseded_at) VALUES "
        f"(1, 7, '2026-10', 2, 'monthly', 50, 3, 0, 150, 150, {bt('%PDF-1.4 stay fee')}, {bt('a;b')}, '2026-11-01', NULL),"
        f"(2, 7, '2026-10', 1, 'monthly', 50, 3, 0, 150, 150, {bt('%PDF old')}, NULL, '2026-10-31', '2026-11-01'),"
        f"(3, 6, '2026-Q3', 1, 'quarterly', 50, 3, 0, 150, 150, NULL, {bt('only;csv')}, '2026-10-01', NULL)",
        "INSERT INTO alert (id, level, kind, owner_user_id, message, created_at) VALUES "
        "(1, 'warning', 'calendar_sync_failed', 1, 'Calendar sync failed', '2026-11-10T00:00:00+00:00')",
    ]
    return sql

O, S, OT, AD, B, M = {"uid": 1}, {"uid": 1, "stale": 1}, {"uid": 2}, {"uid": 3}, {"uid": 4}, {"uid": 5}
SUP = {"uid": 3, "as": 1}
G, P = "GET", "POST"
CASES = [
    ("form_signed_out", G, "/guests/11/form.pdf", None, None, True),
    ("form_11", G, "/guests/11/form.pdf", O, None, True),
    ("form_12_child", G, "/guests/12/form.pdf", O, None, True),
    ("form_15", G, "/guests/15/form.pdf", O, None, True),
    ("form_19", G, "/guests/19/form.pdf", O, None, True),
    ("form_missing", G, "/guests/999/form.pdf", O, None, True),
    ("form_missing_cs", G, "/guests/999/form.pdf", O, "cs", True),
    ("form_other_owner", G, "/guests/4/form.pdf", O, None, True),
    ("form_other_ws", G, "/guests/11/form.pdf", OT, None, True),
    ("form_broken", G, "/guests/400/form.pdf", B, None, True),
    ("form_support", G, "/guests/11/form.pdf", SUP, None, True),
    ("zip_signed_out", G, "/housebook/pdfs.zip", None, None, True),
    ("zip_all", G, "/housebook/pdfs.zip", O, None, True),
    ("zip_apartment", G, "/housebook/pdfs.zip?apartment=6", O, None, True),
    ("zip_range", G, "/housebook/pdfs.zip?from=2026-05-02&to=2026-05-10", O, None, True),
    ("zip_empty", G, "/housebook/pdfs.zip?from=2027-01-01", O, None, True),
    ("zip_empty_cs", G, "/housebook/pdfs.zip?from=2027-01-01", O, "cs", True),
    ("zip_too_many", G, "/housebook/pdfs.zip", M, None, True),
    ("zip_too_many_vi", G, "/housebook/pdfs.zip", M, "vi", True),
    ("zip_limit_ok", G, "/housebook/pdfs.zip?to=2026-08-31", M, None, True),
    ("zip_broken", G, "/housebook/pdfs.zip", B, None, True),
    ("zip_support", G, "/housebook/pdfs.zip?apartment=6", SUP, None, True),
    ("arch_signed_out", G, "/settings/archived", None, None, True),
    ("arch_all", G, "/settings/archived", O, None, True),
    ("arch_all_cs", G, "/settings/archived", O, "cs", True),
    ("arch_stays", G, "/settings/archived?type=stays", O, None, True),
    ("arch_properties", G, "/settings/archived?type=properties", O, None, True),
    ("arch_housebook", G, "/settings/archived?type=housebook", O, None, True),
    ("arch_entities", G, "/settings/archived?type=entities", O, None, True),
    ("arch_bogus", G, "/settings/archived?type=bogus&type=entities", O, None, True),
    ("arch_empty_other", G, "/settings/archived", OT, None, True),
    ("arch_empty_type_other", G, "/settings/archived?type=stays", OT, "vi", True),
    ("arch_broken", G, "/settings/archived", B, None, True),
    ("arch_broken_stays", G, "/settings/archived?type=stays", B, None, True),
    ("ws_signed_out", P, "/settings/workspace-export", None, None, True),
    ("ws_no_csrf", P, "/settings/workspace-export", O, None, False),
    ("ws_stale", P, "/settings/workspace-export", S, None, True),
    ("ws_not_scheduled", P, "/settings/workspace-export", OT, None, True),
    ("ws_owner", P, "/settings/workspace-export", O, None, True),
    ("ws_support", P, "/settings/workspace-export", SUP, None, True),
    ("ws_broken", P, "/settings/workspace-export", B, None, True),
    ("purge_signed_out", P, "/settings/purge-expired", None, None, True),
    ("purge_no_csrf", P, "/settings/purge-expired", O, None, False),
    ("purge_other", P, "/settings/purge-expired", OT, None, True),
    ("purge_owner", P, "/settings/purge-expired", O, None, True),
    ("purge_owner_again", P, "/settings/purge-expired", O, "cs", True),
    ("purge_many", P, "/settings/purge-expired", M, None, True),
    ("purge_support", P, "/settings/purge-expired", SUP, None, True),
]
HEADERS = ("content-type", "content-disposition", "location", "cache-control")
NOW = eg.NOW

def main_part(html):
    m = re.search(r'<main id="main-content".*?</main>', html, re.S)
    s = m.group(0) if m else html
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'> <', '><', s)
    return s

def run(base):
    import psycopg
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {DB}")
    url = urlunsplit(urlsplit(base)._replace(path="/" + DB))
    data_dir = tempfile.mkdtemp(prefix="exports-routes-")
    os.environ.update({"UBYHOST_DATABASE_URL": url, "UBYHOST_SECRET_KEY": eg.SECRET,
                       "UBYHOST_DATA_KEYS": eg.DATA_KEY, "UBYHOST_DATA_DIR": data_dir})
    sys.path.insert(0, str(APP))
    from fastapi.testclient import TestClient
    from itsdangerous import URLSafeTimedSerializer
    from app import auth, db, housebook, security
    from app.main import app
    from app.routes import exports
    db.apply_postgresql_schema()
    pdir = Path(data_dir) / "passport_photos"; pdir.mkdir(parents=True, exist_ok=True)
    for name in eg.PHOTOS + ["30.jpg"]:
        (pdir / name).write_bytes(b"x")
    rows = eg.seed()
    ex = extras()
    with psycopg.connect(url, autocommit=True) as conn:
        for table in rows:
            cols = ", ".join(table["columns"]); marks = ", ".join(["%s"] * len(table["columns"]))
            for row in table["rows"]:
                conn.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)
        for s in ex:
            conn.execute(s)
    nonce = "harness-nonce"
    token = URLSafeTimedSerializer(eg.SECRET, salt="ubyhost-csrf").dumps({"nonce": security._nonce_binding(nonce)})
    out = []
    from app import deadlines, passport_photos, reporting, retention
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(exports, "datetime", eg.FrozenDatetime))
        stack.enter_context(mock.patch.object(housebook, "datetime", eg.FrozenDatetime))
        stack.enter_context(mock.patch.object(db, "utcnow", lambda: NOW))
        for module in (retention, reporting, deadlines):
            stack.enter_context(mock.patch.object(module, "datetime", _Clock))
        for module in (retention, passport_photos):
            stack.enter_context(mock.patch.object(module, "date", _Today))
        stack.enter_context(mock.patch.object(retention, "time", types.SimpleNamespace(time=lambda: _AT.timestamp())))
        conn = stack.enter_context(psycopg.connect(url, autocommit=True))
        client = TestClient(app, follow_redirects=False, raise_server_exceptions=False)
        last = conn.execute("SELECT COALESCE(MAX(id), 0) FROM audit").fetchone()[0]
        for name, method, path, sess, lang, csrf in CASES:
            client.cookies.clear()
            if sess is not None:
                now = int(time.time())
                client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(
                    sess["uid"], 0, workspace_user_id=sess.get("as"),
                    impersonation_started_at=now if sess.get("as") else None,
                    issued_at=now - 3600 if sess.get("stale") else now))
            if lang:
                client.cookies.set("ubyhost_lang", lang)
            if method == "POST":
                headers = {}
                if csrf:
                    client.cookies.set(security.CSRF_COOKIE, nonce)
                    headers["x-csrf-token"] = token
                resp = client.post(path, headers=headers)
            else:
                resp = client.get(path)
            written = [list(r) for r in conn.execute(
                "SELECT id, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit WHERE id > %s ORDER BY id", (last,)).fetchall()]
            if written:
                last = written[-1][0]
            case = {"name": name, "method": method, "path": path, "session": sess, "lang": lang, "csrf": csrf,
                    "status": resp.status_code,
                    "headers": {h: resp.headers[h] for h in HEADERS if h in resp.headers},
                    "audit": [r[1:] for r in written]}
            ct = resp.headers.get("content-type", "")
            if ct == "application/zip":
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    ents = []
                    for i in zf.infolist():
                        b = zf.read(i)
                        if b.startswith(b"%PDF") and i.filename.endswith(".pdf") and (i.filename.startswith("guests/") or "/" not in i.filename):
                            ents.append([i.filename, "PDF"])
                        elif i.filename == "manifest.json":
                            ents.append([i.filename, b.decode()])
                        else:
                            ents.append([i.filename, base64.b64encode(b).decode()])
                    case["zip"] = ents
            elif ct.startswith("application/pdf"):
                case["body"] = "PDF" if resp.content.startswith(b"%PDF") else "NOT PDF"
            elif ct.startswith("text/html") and resp.status_code == 200:
                case["body"] = main_part(resp.text)
            else:
                case["body"] = resp.text
            if name.startswith("purge"):
                st = {}
                for q in ["SELECT COUNT(*) FROM guest", "SELECT COUNT(*) FROM guest WHERE passport_photo_at IS NOT NULL",
                          "SELECT COUNT(*) FROM submission WHERE request_xml IS NOT NULL OR request_xml_enc IS NOT NULL OR response_xml IS NOT NULL",
                          "SELECT COUNT(*) FROM submission", "SELECT COUNT(*) FROM invoice", "SELECT COUNT(*) FROM reservation",
                          "SELECT string_agg(id::text, ',' ORDER BY id) FROM guest WHERE id < 500"]:
                    st[q] = conn.execute(q).fetchone()[0]
                st["photos"] = sorted(p.name for p in pdir.iterdir())
                case["state"] = st
            out.append(case)
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
    shutil.rmtree(data_dir, ignore_errors=True)
    return {"extras": ex, "photos": eg.PHOTOS + ["30.jpg"], "cases": out}


def main(argv: list) -> int:
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL", "")
    if not base:
        print("set UBYHOST_TEST_DATABASE_URL to a PostgreSQL server URL")
        return 2
    text = json.dumps(run(base), ensure_ascii=False, indent=1, default=str) + "\n"
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if current == text:
        return 0
    if "--check" in argv:
        print(f"stale: {OUT}")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
