"""Write the stay-fee action golden files for go/internal/web/stayfees from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/stay_fee_actions_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED, sends every
request in CASES through FastAPI's TestClient (the CSRF dependency is switched
off; the Go test sends a valid token), and records the status, the Location
header, the CSV headers and body, and the rows each request changed. The clock
is frozen: db.utcnow is NOW_STAMP and claim.prague_today is TODAY.

Files written:
  go/internal/web/stayfees/testdata/actions_golden.json
  go/internal/web/stayfees/i18n.json   (the flash texts the routes use)

go/internal/web/stayfees/actions_test.go seeds PostgreSQL from the golden file,
runs the Go handlers and compares. App/tests/test_go_stay_fee_actions_golden.py
fails when either file is stale.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT_DIR = APP.parent / "go" / "internal" / "web" / "stayfees"
OUT = OUT_DIR / "testdata" / "actions_golden.json"
OUT_I18N = OUT_DIR / "i18n.json"

NOW_STAMP = "2026-11-13T10:00:00+00:00"
TODAY = date(2026, 11, 13)
STAMP = "2026-09-01T00:00:00+00:00"
CSV_TEXT = "Evidencni kniha;1\nJan Novak;AB123\n"
# The Fernet timestamp and IV of the seeded csv_enc, fixed so the file is stable.
FERNET_TIME = 1790000000
FERNET_IV = bytes(range(16))

# The flash keys the eight routes raise.
FLASH_KEYS = [
    "flash.error.identity_hidden_export",
    "flash.error.no_such_apartment",
    "flash.error.no_such_guest",
    "flash.stay_fees.adjust_sealed",
    "flash.stay_fees.copy_done",
    "flash.stay_fees.copy_failed",
    "flash.stay_fees.marked_paid",
    "flash.stay_fees.marked_sent",
    "flash.stay_fees.not_saved",
    "flash.stay_fees.paid",
    "flash.stay_fees.reason_required",
    "flash.stay_fees.report_blocked",
    "flash.stay_fees.saved",
    "flash.stay_fees.scope_invalid",
]

FEE_FIELDS = [
    "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs",
    "stay_fee_council_account", "stay_fee_council_iban",
    "stay_fee_authority_name", "stay_fee_authority_address",
    "stay_fee_authority_contact", "stay_fee_authority_databox",
    "stay_fee_payee", "stay_fee_instruction",
    "stay_fee_scope_rule", "stay_fee_scope_reference",
]
APARTMENT_COLUMNS = [
    "id", "owner_user_id", "internal_name", "uby_name", "permalink_token", "created_at",
    "addr_obec", "archived_at", *FEE_FIELDS,
]


def _apt(aid, owner, name, obec, rate=0, cadence="monthly", archived=None, full=False):
    """One apartment row; full=True fills every council field with values of its own."""
    texts = [None] * 9
    scope = [None, None]
    if full:
        texts = [f"vs{aid}", f"acct-{aid}", f"CZ{aid:02d}IBAN", f"Authority {aid}",
                 f"Street {aid}, Praha", f"mail{aid}@example.test", f"box{aid}",
                 f"Payee {aid}", f"Instruction {aid}"]
        scope = ["nights", f"Vyhlaska {aid}"]
    return [aid, owner, name, "UBY", f"tok{aid}", STAMP, obec, archived,
            rate, cadence, *texts, *scope]


def _filing(fid, apt, key, cadence="monthly", *, csv=None, superseded=None, sent=None, paid=None):
    return [fid, apt, key, 1, cadence, 50, 10, 0, 500, 500, csv, STAMP, superseded, sent, paid]


def _adjustment(aid, apt, key="2026-10", *, reversed_at=None, reversed_by=None, filing=None):
    return [aid, apt, key, "add", "bed_days", 3, "enc-placeholder", 1, STAMP,
            reversed_at, reversed_by, filing]


def _guest(gid, rid, decision=None, reason=None):
    return [gid, rid, STAMP, STAMP, decision, reason]


def _csv_token(data: bytes) -> str:
    """A Fernet token of data with a fixed time and IV, as db.encrypt_blob makes it."""
    from unittest import mock

    from cryptography import fernet as fernet_module

    from app import db

    with mock.patch.object(fernet_module.time, "time", lambda: FERNET_TIME), \
            mock.patch.object(fernet_module.os, "urandom", lambda n: FERNET_IV[:n]):
        return db.encrypt_blob(data).decode("ascii")


def _seed(csv_token: str) -> list:
    blob = {"b64": base64.b64encode(csv_token.encode("ascii")).decode("ascii")}
    return [
        {"table": "user_account",
         "columns": ["id", "username", "password_hash", "role", "created_at"],
         "rows": [
             [1, "host1@example.test", "x", "host", STAMP],
             [2, "host2@example.test", "x", "host", STAMP],
             [3, "admin@example.test", "x", "admin", STAMP],
         ]},
        {"table": "apartment", "columns": APARTMENT_COLUMNS,
         "rows": [
             _apt(11, 1, "Byt A", "Praha 3"),
             _apt(12, 1, "Byt B č", "Praha 3", rate=50, full=True),
             _apt(13, 1, "Byt C", "PRAHA 3"),
             _apt(14, 1, "Byt D", "Brno"),
             _apt(16, 1, "Byt E", "Praha 3", rate=40, archived=STAMP, full=True),
             _apt(17, 1, "Byt Q", "Kladno", rate=50, cadence="quarterly", full=True),
             _apt(18, 1, "Byt F", "Praha 3"),
             _apt(19, 1, "Byt G", "Ř\xcdČANY"),
             _apt(20, 2, "Foreign", "Praha 3", rate=50, full=True),
             _apt(21, 1, "Byt H", "řičany", rate=30, full=True),
         ]},
        {"table": "stay_fee_filing",
         "columns": ["id", "apartment_id", "period_key", "version", "cadence", "rate_czk",
                     "liable_days", "exempt_days", "total_due_czk", "total_collected_czk",
                     "csv_enc", "created_at", "superseded_at", "sent_at", "paid_at"],
         "rows": [
             _filing(1, 12, "2026-10", csv=blob),
             _filing(2, 12, "2026-09", sent="2026-10-02T08:00:00+00:00"),
             _filing(3, 12, "2026-08", sent="2026-09-02T08:00:00+00:00", paid="2026-09-05T08:00:00+00:00"),
             _filing(4, 12, "2026-07", superseded="2026-08-01T00:00:00+00:00"),
             _filing(5, 17, "2026-Q3", "quarterly", csv=blob),
             _filing(6, 13, "2026-10"),
             _filing(7, 21, "2026-06"),
             _filing(8, 12, "2026-Q2", "quarterly"),
             _filing(9, 17, "2026-Q4", "quarterly"),
         ]},
        {"table": "stay_fee_adjustment",
         "columns": ["id", "apartment_id", "period_key", "direction", "mode", "bed_days",
                     "reason_enc", "created_by", "created_at", "reversed_at", "reversed_by",
                     "filing_id"],
         "rows": [
             _adjustment(1, 12),
             _adjustment(2, 12, reversed_at="2026-10-05T00:00:00+00:00", reversed_by=1),
             _adjustment(3, 12, filing=1),
             _adjustment(4, 20),
             _adjustment(5, 12),
             _adjustment(6, 12),
         ]},
        {"table": "reservation",
         "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "created_at", "updated_at"],
         "rows": [
             [1, 12, "u1", "2026-10-01", "2026-10-05", STAMP, STAMP],
             [2, 11, "u2", "2026-10-01", "2026-10-05", STAMP, STAMP],
             [3, 20, "u3", "2026-10-01", "2026-10-05", STAMP, STAMP],
         ]},
        {"table": "guest",
         "columns": ["id", "reservation_id", "created_at", "updated_at",
                     "fee_host_decision", "fee_host_reason"],
         "rows": [
             _guest(1, 1), _guest(2, 1, "charge"), _guest(3, 2), _guest(4, 3),
             _guest(5, 1, "exempt", "disability"), _guest(6, 1), _guest(7, 1), _guest(8, 1),
             _guest(9, 1), _guest(10, 1), _guest(11, 1), _guest(12, 1),
         ]},
    ]


def _c(name, method, path, form=None, who="host1", lang=None, hidden=False):
    """One request. hidden=True makes access.identity_visible answer False, the
    case a session cannot reach today (only an admin can be inside another workspace)."""
    return {"name": name, "method": method, "path": path, "form": form or {},
            "who": who, "lang": lang, "identity_hidden": hidden}


def _cases() -> list:
    cases = []
    add = cases.append

    # --- adjustment undo ---
    undo = "/stay-fees/12/adjustment/{}/undo"
    add(_c("undo ok", "POST", undo.format(1), {"month": "2026-10"}))
    add(_c("undo twice is a plain redirect", "POST", undo.format(1), {"month": "2026-10"}))
    add(_c("undo already reversed", "POST", undo.format(2), {"month": "2026-10"}))
    add(_c("undo sealed", "POST", undo.format(3), {"month": "2026-10"}))
    add(_c("undo missing row", "POST", undo.format(999), {"month": "2026-10"}))
    add(_c("undo row of another apartment", "POST", undo.format(4), {"month": "2026-10"}))
    add(_c("undo foreign apartment", "POST", "/stay-fees/20/adjustment/4/undo", {"month": "2026-10"}))
    add(_c("undo as impersonating admin, bad month", "POST", undo.format(5),
           {"month": "2026-13"}, who="admin_imp"))
    add(_c("undo default month, Czech", "POST", undo.format(6), {}, lang="cs"))
    add(_c("undo not signed in", "POST", undo.format(6), {"month": "2026-10"}, who=None))

    # --- guest decision ---
    gd = "/stay-fees/guest-decision"

    def decision(guest, **form):
        return {"apartment_id": "12", "month": "2026-10", "guest_id": str(guest), **form}

    add(_c("decision exempt disability", "POST", gd, decision(1, decision="exempt", reason="disability")))
    add(_c("decision exempt padded fields", "POST", gd,
           decision(6, decision=" exempt ", reason="  diplomat  ")))
    add(_c("decision local_rule short reference", "POST", gd,
           decision(7, decision="exempt", reason="local_rule", reason_reference="ab")))
    add(_c("decision local_rule", "POST", gd,
           decision(7, decision="exempt", reason="local_rule", reason_reference="\xa7 5 vyhlasky č. 1")))
    add(_c("decision local_rule long reference", "POST", gd,
           decision(8, decision="exempt", reason="local_rule", reason_reference="r" * 250)))
    add(_c("decision exempt unknown reason", "POST", gd,
           decision(9, decision="exempt", reason="bogus")))
    add(_c("decision exempt no reason", "POST", gd, decision(9, decision="exempt")))
    add(_c("decision charge drops reason", "POST", gd,
           decision(5, decision="charge", reason="disability", reason_reference="x")))
    add(_c("decision auto clears", "POST", gd, decision(2, decision="")))
    add(_c("decision unknown value is auto", "POST", gd, decision(10, decision="weird")))
    add(_c("decision guest of another apartment", "POST", gd, decision(3, decision="charge")))
    add(_c("decision foreign guest", "POST", gd, decision(4, decision="charge")))
    add(_c("decision apartment id not a number", "POST", gd,
           {"apartment_id": "abc", "month": "2026-10", "guest_id": "11", "decision": "charge"}))
    add(_c("decision guest id not a number", "POST", gd,
           {"apartment_id": "12", "month": "2026-10", "guest_id": "x", "decision": "charge"}))
    add(_c("decision foreign apartment", "POST", gd,
           {"apartment_id": "20", "month": "2026-10", "guest_id": "4", "decision": "charge"}))
    add(_c("decision bad month, Czech", "POST", gd,
           decision(11, month="bad", decision="exempt", reason="other_statutory"), lang="cs"))
    add(_c("decision overlong reason is refused", "POST", gd,
           decision(12, decision="exempt", reason="disability" + " x" * 80)))

    # --- scope ruling ---
    sr = "/stay-fees/12/scope-ruling"
    add(_c("scope ok", "POST", sr, {"month": "2026-10", "rule": "nights", "reference": "\xa7 4 vyhlasky"}))
    add(_c("scope padded and long", "POST", sr,
           {"month": "2026-10", "rule": " calendar_days ", "reference": "  " + "q" * 250}))
    add(_c("scope bad rule, Vietnamese", "POST", sr,
           {"month": "2026-10", "rule": "weeks", "reference": "abc"}, lang="vi"))
    add(_c("scope short reference", "POST", sr, {"month": "2026-10", "rule": "nights", "reference": "ab"}))
    add(_c("scope default month", "POST", sr, {"rule": "nights", "reference": "abc"}))
    add(_c("scope foreign apartment", "POST", "/stay-fees/20/scope-ruling",
           {"month": "2026-10", "rule": "nights", "reference": "abc"}))
    add(_c("scope missing apartment", "POST", "/stay-fees/999/scope-ruling",
           {"month": "2026-10", "rule": "nights", "reference": "abc"}))

    # --- copy setup ---
    cp = "/stay-fees/{}/copy-setup"
    add(_c("copy ok", "POST", cp.format(11), {"source_id": "12"}))
    add(_c("copy again is refused (target is active)", "POST", cp.format(11), {"source_id": "12"}))
    add(_c("copy ok with return_to", "POST", cp.format(19), {"source_id": "21", "return_to": "/stay-fees?month=2026-10"}, lang="cs"))
    add(_c("copy target has a filing", "POST", cp.format(13), {"source_id": "12"}))
    add(_c("copy other municipality", "POST", cp.format(14), {"source_id": "12"}))
    add(_c("copy archived source", "POST", cp.format(18), {"source_id": "16", "return_to": "/stay-fees/18"}))
    add(_c("copy foreign source", "POST", cp.format(18), {"source_id": "20"}))
    add(_c("copy source not a number", "POST", cp.format(18), {"source_id": "abc"}))
    add(_c("copy inactive source", "POST", cp.format(18), {"source_id": "14"}))
    add(_c("copy source is the target", "POST", cp.format(18), {"source_id": "18"}))
    add(_c("copy return_to other apartment", "POST", cp.format(18), {"source_id": "20", "return_to": "/stay-fees/99"}))
    add(_c("copy return_to off site", "POST", cp.format(18), {"source_id": "20", "return_to": "https://evil.example/stay-fees"}))
    add(_c("copy foreign target", "POST", cp.format(20), {"source_id": "12"}))

    # --- filing sent and paid ---
    fs = "/stay-fees/{}/filings/{}/sent"
    fp = "/stay-fees/{}/filings/{}/paid"
    add(_c("sent ok", "POST", fs.format(12, 1), {"month": "2026-10"}))
    add(_c("sent twice", "POST", fs.format(12, 1), {"month": "2026-10"}))
    add(_c("sent already sent", "POST", fs.format(12, 2), {"month": "2026-09"}))
    add(_c("sent wrong month", "POST", fs.format(12, 2), {}))
    add(_c("sent superseded", "POST", fs.format(12, 4), {"month": "2026-07"}))
    add(_c("sent filing of another apartment", "POST", fs.format(17, 1), {"month": "2026-10"}))
    add(_c("sent quarterly filing, month in quarter", "POST", fs.format(17, 5), {"month": "2026-08"}))
    add(_c("sent quarterly filing, month outside", "POST", fs.format(17, 5), {"month": "2026-11"}))
    add(_c("sent quarterly Q2 on a monthly apartment", "POST", fs.format(12, 8), {"month": "2026-05"}))
    add(_c("sent quarterly Q2, month in Q3", "POST", fs.format(12, 8), {"month": "2026-07"}))
    add(_c("sent foreign apartment", "POST", fs.format(20, 1), {"month": "2026-10"}))
    add(_c("paid filing sets paid and keeps sent", "POST", fp.format(12, 1), {"month": "2026-10"}, lang="cs"))
    add(_c("paid filing also sets sent", "POST", fp.format(12, 2), {"month": "2026-09"}))
    add(_c("paid filing already paid", "POST", fp.format(12, 3), {"month": "2026-08"}))
    add(_c("paid filing wrong month", "POST", fp.format(12, 3), {"month": "2026-07"}))
    add(_c("paid filing quarterly", "POST", fp.format(17, 5), {"month": "2026-09"}))
    add(_c("paid filing foreign apartment", "POST", fp.format(20, 1), {"month": "2026-10"}))
    add(_c("paid filing as impersonating admin", "POST", fp.format(12, 8), {"month": "2026-06"}, who="admin_imp"))

    # --- paid ---
    pd = "/stay-fees/{}/paid"
    add(_c("paid ok", "POST", pd.format(21), {"month": "2026-06"}))
    add(_c("paid twice", "POST", pd.format(21), {"month": "2026-06"}))
    add(_c("paid already paid", "POST", pd.format(12), {"month": "2026-08", "return_to": "/stay-fees/12?month=2026-08"}))
    add(_c("paid not sealed", "POST", pd.format(12), {"month": "2026-03"}))
    add(_c("paid default month", "POST", pd.format(12), {}))
    add(_c("paid return_to list", "POST", pd.format(12), {"month": "2026-03", "return_to": "/stay-fees?x=1"}))
    add(_c("paid return_to normalised", "POST", pd.format(12), {"month": "2026-03", "return_to": "/stay-fees/./12/?a=b#f"}))
    add(_c("paid return_to backslash", "POST", pd.format(12), {"month": "2026-03", "return_to": "/stay-fees\\12"}))
    add(_c("paid quarterly covers month", "POST", pd.format(17), {"month": "2026-11"}))
    add(_c("paid foreign apartment (python 500)", "POST", pd.format(20), {"month": "2026-10"}))
    add(_c("paid missing apartment (python 500)", "POST", pd.format(999), {"month": "2026-10"}))

    # --- csv ---
    cv = "/stay-fees/{}/csv"
    add(_c("csv ok", "GET", cv.format(12) + "?month=2026-10"))
    add(_c("csv quarterly", "GET", cv.format(17) + "?month=2026-08"))
    add(_c("csv sealed without a body", "GET", cv.format(13) + "?month=2026-10"))
    add(_c("csv future month", "GET", cv.format(12) + "?month=2026-12"))
    add(_c("csv current month is not saved", "GET", cv.format(12)))
    add(_c("csv bad month is the current month", "GET", cv.format(12) + "?month=junk", lang="cs"))
    add(_c("csv inactive apartment without filing", "GET", cv.format(11) + "?month=2026-10"))
    add(_c("csv foreign apartment", "GET", cv.format(20) + "?month=2026-10"))
    add(_c("csv missing apartment", "GET", cv.format(999) + "?month=2026-10"))
    add(_c("csv as impersonating admin", "GET", cv.format(12) + "?month=2026-10", who="admin_imp"))
    add(_c("csv not signed in", "GET", cv.format(12) + "?month=2026-10", who=None))
    add(_c("csv identity hidden", "GET", cv.format(12) + "?month=2026-10", hidden=True))
    return cases


def _snapshot(db) -> dict:
    """The rows the eight routes can change, as plain JSON values."""
    def rows(sql):
        return [dict(zip(row.keys(), tuple(row))) for row in db.query(sql)]

    guests = []
    for row in db.query(
        "SELECT id, fee_host_decision, fee_host_reason, fee_host_reason_enc, "
        "fee_host_reason_reference, updated_at FROM guest ORDER BY id"
    ):
        raw = db.query_one("SELECT fee_host_reason, fee_host_reason_enc FROM guest WHERE id = ?", (row["id"],))
        guests.append({
            "id": row["id"],
            "decision": row["fee_host_decision"],
            "reason": row["fee_host_reason"],
            "reason_plain_column": None,
            "reason_enc_set": bool(raw["fee_host_reason_enc"]) if raw is not None else False,
            "reference": row["fee_host_reason_reference"],
            "updated_at": row["updated_at"],
        })
    return {
        "audit": rows(
            "SELECT at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id "
            "FROM audit ORDER BY id"
        ),
        "stay_fee_adjustment": rows(
            "SELECT id, apartment_id, filing_id, reversed_at, reversed_by "
            "FROM stay_fee_adjustment ORDER BY id"
        ),
        "stay_fee_filing": rows(
            "SELECT id, apartment_id, period_key, superseded_at, sent_at, paid_at "
            "FROM stay_fee_filing ORDER BY id"
        ),
        "guest": guests,
        "apartment": rows(
            "SELECT id, " + ", ".join(FEE_FIELDS) + " FROM apartment ORDER BY id"
        ),
    }


def render() -> tuple[str, str]:
    """Seed a fresh database, run every case, return (golden JSON, i18n JSON)."""
    from fastapi.testclient import TestClient

    from app import acceptance, access, auth, claim, db, host_i18n, main, security

    db.init_db()
    seed = _seed(_csv_token(CSV_TEXT.encode("utf-8")))
    for table in seed:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            values = [
                base64.b64decode(v["b64"]) if isinstance(v, dict) else v for v in row
            ]
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", values)

    async def no_csrf() -> None:
        return None

    saved = (db.utcnow, claim.prague_today, acceptance.pending, access.identity_visible)
    db.utcnow = lambda: NOW_STAMP
    claim.prague_today = lambda: TODAY
    acceptance.pending = lambda user_id: []
    main.app.dependency_overrides[security.protect_host_post] = no_csrf
    try:
        client = TestClient(main.app, raise_server_exceptions=False, follow_redirects=False)
        sessions = {
            None: None,
            "host1": auth.issue_session(1, 1),
            "host2": auth.issue_session(2, 1),
            "admin_imp": auth.issue_session(3, 1, workspace_user_id=1),
        }
        previous = _snapshot(db)
        initial = previous
        results = []
        for case in _cases():
            client.cookies.clear()
            token = sessions[case["who"]]
            if token:
                client.cookies.set(auth.SESSION_COOKIE, token)
            if case["lang"]:
                client.cookies.set("ubyhost_lang", case["lang"])
            access.identity_visible = (lambda *a, **k: False) if case["identity_hidden"] else saved[3]
            response = client.request(case["method"], case["path"], data=case["form"] or None)
            current = _snapshot(db)
            changed = {t: rows for t, rows in current.items() if rows != previous[t]}
            if "audit" in changed:
                # Only the rows this request appended; the Go test compares the same slice.
                changed["audit_new"] = changed.pop("audit")[len(previous["audit"]):]
            previous = current
            body = response.content
            results.append({
                **case,
                "status": response.status_code,
                "location": response.headers.get("location"),
                "content_type": response.headers.get("content-type"),
                "content_disposition": response.headers.get("content-disposition"),
                "cache_control": response.headers.get("cache-control"),
                "body": body.decode("utf-8") if response.status_code == 200 else None,
                "changed": changed,
            })
    finally:
        db.utcnow, claim.prague_today, acceptance.pending, access.identity_visible = saved
        main.app.dependency_overrides.pop(security.protect_host_post, None)

    golden = {
        "now": NOW_STAMP,
        "seed": seed,
        "initial": initial,
        "csv_text": CSV_TEXT,
        "cases": results,
    }
    catalog = {
        lang: {key: strings[key] for key in FLASH_KEYS if key in strings}
        for lang, strings in host_i18n.STRINGS.items()
    }
    return (
        json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
    )


def main_write() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    golden, catalog = render()
    OUT.write_text(golden, encoding="utf-8")
    OUT_I18N.write_text(catalog, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {OUT_I18N}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "stay_fee_actions_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main_write()
