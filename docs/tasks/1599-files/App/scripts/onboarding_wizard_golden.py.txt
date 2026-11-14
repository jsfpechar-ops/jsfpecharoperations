"""Write go/internal/web/onboarding/testdata/wizard_golden_<part>.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt):

    .venv/bin/python scripts/onboarding_wizard_golden.py

This file is the shared part of the setup wizard goldens (briefs 1599 to
1602) and also writes the first one, part "entry" (GET /apartments/{id}/setup,
the step redirects and the calendar and guest link pages). The later briefs add
scripts/onboarding_wizard_golden_<part>.py, which import render() from here
with their own CASES.

It seeds a throwaway SQLite database with the fixed rows in SEED, sends every
request of a part, in order, through the real FastAPI app (TestClient), and
records each answer: the status, the Location, and for an HTML page its title
and the wizard markup (<div class="setup-wizard wiz-page"> to its closing tag,
CSRF values blanked). At the end it records the rows the wizard writes
(property_setup:* settings, PIN presence, audit lines, demo stays).
go/internal/web/onboarding/wizard_golden_test.go seeds PostgreSQL from the same
file, sends the same requests to the Go routes and compares.
App/tests/test_go_onboarding_wizard.py fails when a file is stale.

Pinned: claim.prague_today() and the date_short filter's year (TODAY), the
public base URL, the door-code switch and its TTLock credentials (on, so the
lock window shows), billing off, the mock UbyPort environment.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
TESTDATA = APP.parent / "go" / "internal" / "web" / "onboarding" / "testdata"
OUT = TESTDATA / "wizard_golden_entry.json"

TODAY = "2026-05-10"
STAMP = "2026-01-01T00:00:00+00:00"
BASE = "https://app.example.test"
CSRF_NONCE = "golden-csrf-nonce-0123456789"
CSRF_FIELD = re.compile(r'name="_csrf" value="[^"]*"')
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}
WIZARD_START = '<div class="setup-wizard wiz-page"'
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def _state(steps=None, *, finished=False, hidden=False, legacy=False, celebrated=False, tested=False) -> str:
    """property_setup._save's JSON."""
    return json.dumps({"celebrated": celebrated, "finished": finished, "hidden": hidden, "legacy": legacy,
                       "steps": steps or {}, "tested": tested}, sort_keys=True)


def _apt(aid, owner, name, entity=None, *, done=False, police=False, pin="123456", token=True,
         archived=None, active=1, mode="manual", hours=24, lock=None, cin=None, cout=None, window=2):
    """One apartment row. done: the property details are complete; police: the UbyPort fields too."""
    street, house, zipc, obec = ("Vinohradská", "12", "12000", "Praha") if done else (None, None, None, None)
    idub, mark, uby, user, password = (
        ("123456789012", "AAKLI", f"BYT {aid}", "UBY-WS_ABCDE", "heslo-golden") if police else (None,) * 5)
    return [aid, owner, name, entity, "Prague" if done else None, street, house, zipc, obec, idub, mark, uby,
            user, password, mode, hours, f"tok{aid}" if token else None, pin, archived, active, lock, cin, cout,
            window, STAMP]


def _stay(rid, apartment, start, end, source="host", status="active", archived=None):
    return [rid, apartment, f"u{rid}", start, end, f"Stay {rid}", status, source, None, archived, STAMP, STAMP]


# Owner 1: 11 guide on the guest link step (details, calendar and police done),
# 12 a new property (legacy guide, property step), 13 finished, 14 hidden, 15 no
# PIN yet, 16 archived without a guide, 17 everything answered but the police
# login (waiting), 18 an old legacy guide that is now set up, 19 a company with
# a signatory, a TTLock lock and a stay a month out, tested, 20 a demo stay
# without guests, 22 a demo stay with a complete guest, 23 guide on the police
# step, 24 a guide at the property step with an operator chosen and no guest
# link token, 27 a second guide on the police step (for the POST cases). 21
# and 26 (one operator, none chosen) are owner 2's; 25 is owner 3's, who has
# no operator yet.
SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[1, "owner@example.test", "x", "host", STAMP], [2, "other@example.test", "x", "host", STAMP],
              [3, "third@example.test", "x", "host", STAMP]]},
    {"table": "legal_acceptance",
     "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in (1, 2, 3) for doc, version in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "signature_name", "archived_at", "created_at"],
     "rows": [
         [31, 1, "Jana Nováková", None, None, STAMP],
         [32, 1, "Beta s.r.o.", "Petr Svoboda", None, STAMP],
         [33, 2, "Cizí s.r.o.", None, None, STAMP],
         [35, 1, "Archiv a.s.", None, "2026-02-01T00:00:00+00:00", STAMP],
     ]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "legal_entity_id", "city_en", "addr_street",
                 "addr_house_no", "addr_zip", "addr_obec", "uby_idub", "uby_mark", "uby_name", "uby_ws_user",
                 "uby_ws_password_enc", "automation_mode", "submit_after_hours", "permalink_token",
                 "permalink_pin", "archived_at", "active", "lock_provider", "checkin_hour", "checkout_hour",
                 "permalink_window_days", "created_at"],
     "secret": ["uby_ws_password_enc"],
     "rows": [
         _apt(11, 1, "Alfa byt", 31, done=True, police=True, cin=15, cout=10),
         _apt(12, 1, "Beta", None),
         _apt(13, 1, "Gama", 31, done=True),
         _apt(14, 1, "Delta", 31, done=True),
         _apt(15, 1, "Epsilon", None, pin=None),
         _apt(16, 1, "Zeta", 31, archived="2026-03-01T00:00:00+00:00"),
         _apt(17, 1, "Eta", 31, done=True, mode="scheduled", hours=6),
         _apt(18, 1, "Theta", 31, done=True, police=True),
         _apt(19, 1, "Iota <b>", 32, done=True, police=True, mode="immediate", lock="ttlock", cin=14, cout=11, window=3),
         _apt(20, 1, "Kappa", 31, done=True, police=True),
         _apt(21, 2, "Cizí", 33, done=True),
         _apt(22, 1, "Lambda", 32, done=True, police=True, mode="scheduled", hours=12),
         _apt(23, 1, "My", 31, done=True),
         _apt(24, 1, "Ny", 32, mode="manual", token=False),
         _apt(25, 3, "Omikron", None),
         _apt(26, 2, "Xi", None, cin=0, cout=23),
         _apt(27, 1, "Pí", 31, done=True),
     ]},
    {"table": "apartment_slug", "columns": ["slug", "apartment_id", "is_current", "created_at"],
     "rows": [[f"slug-{aid}", aid, 1, STAMP] for aid in (11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27)]},
    {"table": "ical_feed", "columns": ["id", "apartment_id", "url", "created_at"],
     "rows": [[1, 11, "https://example.test/a.ics", STAMP], [2, 18, "https://example.test/b.ics", STAMP],
              [3, 19, "https://example.test/c.ics", STAMP]]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "summary", "status", "source",
                 "declared_guests", "archived_at", "created_at", "updated_at"],
     "rows": [
         _stay(101, 11, "2026-05-11", "2026-05-13"),
         _stay(102, 11, "2026-05-20", "2026-05-22", status="cancelled"),
         _stay(103, 19, "2026-06-10", "2026-06-12"),
         _stay(104, 19, "2026-05-01", "2026-05-03"),
         _stay(105, 20, TODAY, "2026-05-11", source="demo"),
         _stay(106, 22, TODAY, "2026-05-11", source="demo"),
         _stay(107, 23, "2026-07-01", "2026-07-04"),
     ]},
    {"table": "guest",
     "columns": ["id", "reservation_id", "is_lead", "surname", "first_name", "birth_date", "nationality",
                 "doc_number", "res_street", "res_city", "res_country", "purpose", "signature_png",
                 "entered_by", "created_at", "updated_at"],
     "rows": [[501, 106, 1, "Mustermann", "Erika", "01011980", "DEU", "C01X00T47", "Hauptstr. 1", "Berlin",
               "DEU", "10", "imported", "guest", STAMP, STAMP]]},
    {"table": "settings", "columns": ["key", "value"],
     "rows": [
         ["property_setup:11", _state()],
         ["property_setup:13", _state({"guest_link": "done"}, finished=True)],
         ["property_setup:14", _state(hidden=True)],
         ["property_setup:17", _state({"calendar": "skipped", "police": "waiting", "guest_link": "done"})],
         ["property_setup:18", _state(legacy=True)],
         ["property_setup:19", _state({"guest_link": "done"}, finished=True, tested=True)],
         ["property_setup:20", _state({"calendar": "done", "guest_link": "done"}, finished=True)],
         ["property_setup:22", _state({"calendar": "done", "guest_link": "done"}, finished=True, tested=True,
                                      celebrated=True)],
         ["property_setup:23", _state({"calendar": "skipped"})],
         ["property_setup:24", _state()],
         ["property_setup:27", _state({"calendar": "done"})],
     ]},
]


def case(name, method, path, user=1, lang=None, form=None, csrf=False):
    return {"name": name, "method": method, "path": path, "user": user, "lang_cookie": lang,
            "form": form, "csrf": csrf}


CASES = [
    case("entry_signed_out", "GET", "/apartments/11/setup", user=None),
    case("entry_bad_id", "GET", "/apartments/abc/setup"),
    case("entry_foreign", "GET", "/apartments/21/setup"),
    case("entry_missing", "GET", "/apartments/999/setup"),
    case("entry_guide", "GET", "/apartments/11/setup"),
    case("entry_new_property", "GET", "/apartments/12/setup"),
    case("entry_finished", "GET", "/apartments/13/setup"),
    case("entry_hidden", "GET", "/apartments/14/setup"),
    case("entry_pin_backfill", "GET", "/apartments/15/setup"),
    case("entry_archived", "GET", "/apartments/16/setup"),
    case("entry_all_answered", "GET", "/apartments/17/setup"),
    case("entry_legacy_set_up", "GET", "/apartments/18/setup"),
    case("step_signed_out", "GET", "/apartments/11/setup/calendar", user=None),
    case("step_bad_id", "GET", "/apartments/1x/setup/calendar"),
    case("step_foreign", "GET", "/apartments/21/setup/calendar"),
    case("step_retired_stay_fee", "GET", "/apartments/11/setup/stay_fee"),
    case("step_retired_door_lock", "GET", "/apartments/11/setup/door_lock"),
    case("step_retired_automation", "GET", "/apartments/11/setup/automation"),
    case("step_unknown", "GET", "/apartments/11/setup/nope"),
    case("step_ahead_of_guide", "GET", "/apartments/12/setup/calendar"),
    case("step_police_ahead", "GET", "/apartments/23/setup/guest_link"),
    case("calendar_back", "GET", "/apartments/11/setup/calendar"),
    case("calendar_cs", "GET", "/apartments/11/setup/calendar", lang="cs"),
    case("calendar_vi_finished", "GET", "/apartments/13/setup/calendar", lang="vi"),
    case("calendar_skipped_guide", "GET", "/apartments/23/setup/calendar"),
    case("guest_link_current", "GET", "/apartments/11/setup/guest_link"),
    case("guest_link_cs", "GET", "/apartments/11/setup/guest_link", lang="cs"),
    case("guest_link_company", "GET", "/apartments/19/setup/guest_link"),
    case("guest_link_no_slug", "GET", "/apartments/12/setup/guest_link"),
    case("guest_link_no_stay_vi", "GET", "/apartments/20/setup/guest_link", lang="vi"),
    case("guest_link_no_token", "GET", "/apartments/24/setup/guest_link"),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        secret = [table["columns"].index(c) for c in table.get("secret", [])]
        for row in table["rows"]:
            row = list(row)
            for i in secret:
                if row[i] is not None:
                    row[i] = db.encrypt_secret(row[i])
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _cookie_header(db, auth, security, c) -> str:
    parts = []
    if c["user"]:
        version = db.query_one("SELECT session_version FROM user_account WHERE id = ?", (c["user"],))
        parts.append(f"{auth.SESSION_COOKIE}={auth.issue_session(c['user'], version['session_version'])}")
    if c["lang_cookie"]:
        parts.append(f"ubyhost_lang={c['lang_cookie']}")
    parts.append(f"{security.CSRF_COOKIE}={CSRF_NONCE}")
    return "; ".join(parts)


def wizard_fragment(html: str) -> str:
    """<div class="setup-wizard wiz-page"> up to its matching </div>, or ""."""
    start = html.find(WIZARD_START)
    if start < 0:
        return ""
    depth, i = 0, start
    tag = re.compile(r"<(/?)div\b")
    for m in tag.finditer(html, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            i = html.index(">", m.end()) + 1
            return CSRF_FIELD.sub('name="_csrf" value=""', html[start:i])
    raise SystemExit("unbalanced wizard markup")


def _send(client, db, auth, security, c) -> dict:
    headers = {"Cookie": _cookie_header(db, auth, security, c)}
    client.cookies.clear()
    if c["method"] == "GET":
        response = client.get(c["path"], headers=headers, follow_redirects=False)
    else:
        form = dict(c["form"] or {})
        if c["csrf"]:
            form["_csrf"] = security._csrf_serializer().dumps({"nonce": security._nonce_binding(CSRF_NONCE)})
        response = client.post(c["path"], data=form, headers=headers, follow_redirects=False)
    out = {"status": response.status_code, "location": response.headers.get("location"),
           "content_type": response.headers.get("content-type"), "title": "", "fragment": "", "body": ""}
    text = response.text
    if (out["content_type"] or "").startswith("text/html") and response.status_code < 300 or WIZARD_START in text:
        match = TITLE.search(text)
        out["title"] = match.group(1).strip() if match else ""
        out["fragment"] = wizard_fragment(text)
    elif not 300 <= response.status_code < 400:
        out["body"] = text
    return out


def _final(db) -> dict:
    settings = {r["key"]: r["value"] for r in
                db.query("SELECT key, value FROM settings WHERE key LIKE 'property_setup:%' ORDER BY key")}
    pins = {str(r["id"]): bool(re.fullmatch(r"\d{6}", r["permalink_pin"] or ""))
            for r in db.query("SELECT id, permalink_pin FROM apartment ORDER BY id")}
    audit = [{"actor": r["actor"], "action": r["action"], "detail": r["detail"], "owner_user_id": r["owner_user_id"],
              "actor_user_id": r["actor_user_id"]}
             for r in db.query("SELECT * FROM audit WHERE action IN ('property_setup_step', 'apartment_updated') "
                               "ORDER BY id")]
    demo = [{"apartment_id": r["apartment_id"], "date_from": r["date_from"], "date_to": r["date_to"],
             "summary": r["summary"], "status": r["status"], "expected_guests_override": r["expected_guests_override"],
             "uid_demo": (r["uid"] or "").startswith("demo-")}
            for r in db.query("SELECT * FROM reservation WHERE source = 'demo' ORDER BY id")]
    timing = [{"id": r["id"], "automation_mode": r["automation_mode"], "submit_after_hours": r["submit_after_hours"]}
              for r in db.query("SELECT id, automation_mode, submit_after_hours FROM apartment ORDER BY id")]
    return {"settings": settings, "pins": pins, "audit": audit, "demo_stays": demo, "timing": timing}


def render(cases) -> str:
    """Seed a fresh database, send every case, and return the golden JSON text."""
    from fastapi.testclient import TestClient

    from app import auth, claim, config, db, security, validation
    from app.main import app
    from app.templating import templates

    db.init_db()
    _seed(db)
    pinned = date.fromisoformat(TODAY)
    patches = {
        (claim, "prague_today"): lambda: pinned,
        (config, "PUBLIC_BASE_URL"): BASE,
        (config, "DOOR_CODES_ENABLED"): True,
        (config, "TTLOCK_CLIENT_ID"): "golden-id",
        (config, "TTLOCK_CLIENT_SECRET"): "golden-secret",
        (config, "BILLING_ENABLED"): False,
        (config, "UBYPORT_ENV"): "mock",
        (config, "SUBMIT_SWEEP_MINUTES"): 10,
        (config, "ICAL_POLL_MINUTES"): 60,
    }
    saved = {key: getattr(*key) for key in patches}
    saved_filter = templates.env.filters["date_short"]
    for (module, name), value in patches.items():
        setattr(module, name, value)
    templates.env.filters["date_short"] = lambda value, today=None: validation.fmt_date_short(value, today=pinned)
    try:
        client = TestClient(app)
        results = [{**c, **_send(client, db, auth, security, c)} for c in cases]
    finally:
        for (module, name), value in saved.items():
            setattr(module, name, value)
        templates.env.filters["date_short"] = saved_filter
    golden = {"today": TODAY, "base": BASE, "csrf_nonce": CSRF_NONCE, "versions": VERSIONS, "seed": SEED,
              "cases": results, "final": _final(db)}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def cli(out: Path, cases) -> None:
    """Set up a throwaway app environment, render, and write out."""
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "wizard_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    sys.path.insert(0, str(APP))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(cases), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    cli(OUT, CASES)
