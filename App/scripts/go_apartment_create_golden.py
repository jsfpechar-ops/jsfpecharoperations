"""Write go/internal/web/properties/testdata/apartment_create_golden.json from the real Python route.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_apartment_create_golden.py          write the file
    .venv/bin/python scripts/go_apartment_create_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the made-up rows in SEED, sends
every POST /apartments of CASES, in order, through the real FastAPI app
(TestClient), and records each answer: status and Location; for a create the
written apartment row (COLUMNS, as text), the length of the permalink token,
the PIN, the decrypted web-service password, the stay_fee_rate rows, the
property_setup setting, the readable part of the guest slug and the audit row;
for a page the error fragments of FRAGMENTS. go/internal/web/properties/
apartment_create_test.go seeds PostgreSQL from the same file, sends the same
requests to the Go handler and compares. App/tests/test_go_apartment_create_golden.py
fails when this file is stale. Brief 1700b2.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "properties" / "testdata" / "apartment_create_golden.json"

STAMP = "2026-01-01T00:00:00+00:00"
CSRF_NONCE = "golden-apartment-create-csrf-nonce-0123"
VERSIONS = {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}

# User 1 is an admin, 2 and 3 are hosts with operators, 4 a host with none.
# Host 2: operators 21 (with an e-mail) and 22, archived 23, and property 201
# with a stay fee (the copy source). Host 3: operator 31 and property 301.
SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[uid, f"create{uid}@example.test", "x", "admin" if uid == 1 else "host", STAMP] for uid in (1, 2, 3, 4)]},
    {"table": "legal_acceptance", "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in (1, 2, 3, 4) for doc, version in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "contact_email", "archived_at", "created_at"],
     "rows": [[21, 2, "Alpha s.r.o.", "  provoz.alpha.s.r.o.dlouhy.kontakt@example.test  ", None, STAMP],
              [22, 2, "Beta Správa", None, None, STAMP], [23, 2, "Gone Co", "gone@example.test", "2026-01-02", STAMP],
              [31, 3, "Gamma Host", "gamma@example.test", None, STAMP]]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "internal_name", "legal_entity_id", "stay_fee_rate_czk", "stay_fee_council_account",
                 "created_at"],
     "rows": [[201, 2, "Loft Karlín", 21, 50, "19-2000145399/0800", STAMP],
              [301, 3, "Other host flat", 31, 0, None, STAMP]]},
]

# What the Go test reads back from the apartment row, as text (NULL is null).
COLUMNS = [
    "owner_user_id", "internal_name", "city_en", "addr_okres", "addr_obec", "addr_obec_cast", "addr_street",
    "addr_house_no", "addr_orient_no", "addr_zip", "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user",
    "guest_message", "notes", "legal_entity_id", "data_controller_entity_id", "automation_mode", "submit_after_hours",
    "permalink_window_days", "permalink_reachback_days", "passport_photo_policy", "ocr_scan", "default_purpose",
    "active", "archived_at", "stay_fee_rate_czk", "stay_fee_vs", "stay_fee_cadence", "stay_fee_authority_name",
    "stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction",
    "stay_fee_council_account", "stay_fee_council_iban",
]

# The parts of a refused page both sides must show alike.
FRAGMENTS = [
    r'id="([a-z_]+-error)"[^>]*>([^<]*)<',
    r'id="((?:operator|controller)-message)"[^>]*>([^<]*)<',
    r'name="(copy_from)" value="([^"]*)"',
    r'<option value="([0-9]+)" (selected)>',
    r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"',
]
# The CSRF token differs on every page; the Go test skips it too.
SKIP_FRAGMENT = "_csrf"

ADDRESS = {"addr_street": "Vinohradská", "addr_house_no": "12", "addr_zip": "120 00", "addr_obec": "Praha 2"}
POLICE = {"uby_ws_user": "UBY-WS_MLJNO", "uby_ws_password": "  golden-ws-pass  "}
COPY = {
    "copy_from": "201", "automation_mode": "scheduled", "submit_after_hours": "60", "default_purpose": "01",
    "permalink_window_days": "3", "permalink_reachback_days": "9999", "stay_fee_rate_czk": "50",
    "stay_fee_cadence": "quarterly", "stay_fee_authority_name": "  Městský úřad Plzeň  ",
    "stay_fee_authority_address": "", "stay_fee_authority_contact": "poplatky@example.test",
    "stay_fee_payee": "P" * 70, "stay_fee_instruction": "Pay by the 15th.", "stay_fee_council_account": "19-2000145399/0800",
}


def _form(**extra):
    form = {"internal_name": "Studio Žižkov", "legal_entity_id": "21", **ADDRESS}
    form.update(extra)
    return form


# name, user, previewed workspace (0: none), language, with a CSRF token, the form.
CASES = [
    ("signed out", 0, 0, "en", True, _form()),
    ("no CSRF token", 2, 0, "en", False, _form()),
    ("valid minimal with police defaults", 2, 0, "en", True, _form(**POLICE)),
    ("copy with stay fee and council account", 2, 0, "cs", True, _form(
        **COPY, internal_name=" Plzeň flat ", data_controller_entity_id="22", addr_obec="Plzeň", addr_okres="Plzeň-město",
        addr_orient_no="5a", addr_obec_cast="Jižní Předměstí", uby_idub="ABC123456789", uby_mark="aakli",
        uby_name="Penzion Plzeň", uby_contact="me@example.test", uby_ws_user="uby-tws_test", guest_message="  Hello  ",
        notes=" a note ", stay_fee_vs="12/34-5678901234", passport_photo_policy="required_foreign", ocr_scan="1",
        account_prefix="", account_number="", account_bank="")),
    ("controller equal to operator, blank message in Czech", 2, 0, "cs", True, _form(
        data_controller_entity_id="21", automation_mode="nonsense", submit_after_hours="-5", permalink_window_days="0",
        permalink_reachback_days="-1", default_purpose="", stay_fee_rate_czk="0", passport_photo_policy="always",
        addr_obec="  Brno   město ")),
    ("evidence number E12", 2, 0, "en", True, _form(internal_name="Chata", addr_house_no="E12", stay_fee_rate_czk="abc",
                                                   default_purpose="  ", automation_mode="",
                                                   stay_fee_cadence="", stay_fee_payee="")),
    ("č.ev. 12 typed in the house number", 2, 0, "en", True, _form(addr_house_no="č.ev. 12")),
    ("foreign operator", 2, 0, "en", True, _form(legal_entity_id="31")),
    ("foreign controller", 2, 0, "en", True, _form(data_controller_entity_id="31")),
    ("malformed controller", 2, 0, "en", True, _form(data_controller_entity_id="x")),
    ("archived operator", 2, 0, "en", True, _form(legal_entity_id="23")),
    ("no operator chosen", 2, 0, "en", True, _form(legal_entity_id="")),
    ("no operator at all", 4, 0, "en", True, _form(legal_entity_id="")),
    ("blank name keeps the copy", 2, 0, "en", True, _form(**COPY, internal_name="   ", data_controller_entity_id="22")),
    ("blank name, foreign copy source", 2, 0, "en", True, _form(internal_name="", copy_from="301")),
    ("every address field missing", 2, 0, "en", True, _form(addr_street="", addr_house_no="", addr_zip="", addr_obec="")),
    ("address errors in Czech", 2, 0, "cs", True, _form(addr_zip="1200", addr_okres="O" * 33, addr_orient_no="12345",
                                                       addr_street=" ")),
    ("address errors in Vietnamese", 2, 0, "vi", True, _form(addr_zip="12", addr_house_no="12345")),
    ("operator refresh writes nothing", 2, 0, "en", True, _form(internal_name="", operator_refresh="1", **COPY)),
    ("admin preview creates for the previewed host", 1, 3, "en", True, _form(
        legal_entity_id="31", automation_mode="immediate", submit_after_hours="1_0", default_purpose="93", **POLICE)),
    ("admin preview cannot use another host's operator", 1, 3, "en", True, _form(legal_entity_id="21")),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row))


def _text(value):
    return None if value is None else str(value)


def _fragments(body: str):
    found = []
    for pattern in FRAGMENTS:
        # Whitespace is collapsed: the two template engines indent differently.
        found += [[" ".join(part.split()) for part in m] for m in re.findall(pattern, body) if m[0] != SKIP_FRAGMENT]
    return found


def _written(db, apartment_id: int):
    row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    slug = db.query_one("SELECT slug FROM apartment_slug WHERE apartment_id = ? AND is_current = 1", (apartment_id,))
    audit = db.query_one(
        "SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit "
        "WHERE action = 'apartment_created' AND detail = ?", (f"id={apartment_id}",))
    return {
        "row": {col: _text(row[col]) for col in COLUMNS},
        "token_length": len(row["permalink_token"] or ""),
        "pin": bool(re.fullmatch(r"[0-9]{6}", row["permalink_pin"] or "")),
        "password": db.decrypt_secret(row["uby_ws_password_enc"]) if row["uby_ws_password_enc"] else None,
        "rates": [[r["rate_czk"], r["effective_from"]] for r in db.query(
            "SELECT rate_czk, effective_from FROM stay_fee_rate WHERE apartment_id = ? ORDER BY effective_from",
            (apartment_id,))],
        "setup": db.get_setting(f"property_setup:{apartment_id}"),
        "slug_readable": slug["slug"].rsplit("-", 1)[0],
        "slug_code_length": len(slug["slug"].rsplit("-", 1)[1]),
        "audit": dict(audit),
    }


def render() -> str:
    from fastapi.testclient import TestClient

    from app import auth, db, security
    from app.main import app

    db.init_db()
    _seed(db)
    client = TestClient(app)
    cases = []
    for name, user, workspace, lang, csrf, form in CASES:
        client.cookies.clear()
        cookies = {"ubyhost_lang": lang, security.CSRF_COOKIE: CSRF_NONCE}
        if user:
            cookies[auth.SESSION_COOKIE] = auth.issue_session(
                user, 1, workspace_user_id=workspace or None,
                impersonation_started_at=int(time.time()) if workspace else None)
        data = dict(form)
        if csrf:
            data["_csrf"] = security._csrf_serializer().dumps({"nonce": security._nonce_binding(CSRF_NONCE)})
        before = db.query_one("SELECT COALESCE(MAX(id), 0) AS n FROM apartment")["n"]
        header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        response = client.post("/apartments", data=data, headers={"Cookie": header}, follow_redirects=False)
        after = db.query_one("SELECT COALESCE(MAX(id), 0) AS n FROM apartment")["n"]
        case = {"name": name, "user": user, "workspace": workspace, "lang": lang, "csrf": csrf, "form": form,
                "status": response.status_code, "location": response.headers.get("location")}
        if after != before:
            case["created"] = _written(db, after)
        elif response.status_code == 200 or response.status_code == 400:
            case["fragments"] = _fragments(response.text)
        cases.append(case)
    golden = {"csrf_nonce": CSRF_NONCE, "seed": SEED, "columns": COLUMNS, "fragments": FRAGMENTS, "cases": cases,
              "apartments": [r["id"] for r in db.query("SELECT id FROM apartment ORDER BY id")]}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_apartment_create_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "apartment_create_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
