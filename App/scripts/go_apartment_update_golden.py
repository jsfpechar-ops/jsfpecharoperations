"""Write go/internal/web/properties/testdata/apartment_update_golden.json from the real Python route.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/go_apartment_update_golden.py          write the file
    .venv/bin/python scripts/go_apartment_update_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the made-up rows in SEED, sends
every POST /apartments/{id} of CASES (settings saves without setup_step), in
order, through the real FastAPI app (TestClient), and records after each one:
status and Location, the target apartment row (COLUMNS, as text), the
decrypted web-service password, the stay_fee_rate rows, the current guest
slug, the audit rows the request added and the open alert keys of the
property. A refused save that draws the page again is marked "page" (brief
1702c1 answers it 501; 1702c2 adds its fragments). Prague's "today" is frozen
to the Go test clock's day. go/internal/web/properties/apartment_update_test.go
seeds PostgreSQL from the same file, sends the same requests to the Go handler
and compares. App/tests/test_go_apartment_update_golden.py fails when this file
is stale. Brief 1702c1, on the harness of go_apartment_create_golden.py.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "properties" / "testdata" / "apartment_update_golden.json"
sys.path.insert(0, str(APP / "scripts"))

from go_apartment_create_golden import VERSIONS, _text  # one harness, not a copy

STAMP = "2026-01-01T00:00:00+00:00"
CSRF_NONCE = "golden-apartment-update-csrf-nonce-0123"
# The Go test clock (properties_test.go testNow, 2026-11-13 10:00 UTC) in Prague.
TODAY = date(2026, 11, 13)
LOCKS = json.dumps([{"lock_id": lid, "alias": alias, "battery": 80, "tz_offset_ms": 3600000, "key_end": 0}
                    for lid, alias in (("L1", "Front"), ("L2", "Back"))])
IBAN = "CZ6508000000192000145399"

APARTMENT_COLUMNS = [
    "id", "owner_user_id", "internal_name", "legal_entity_id", "data_controller_entity_id", "created_at", "archived_at",
    "active", "permalink_token", "permalink_pin", "addr_obec", "addr_street", "addr_house_no", "addr_zip", "city_en",
    "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user", "stay_fee_rate_czk", "stay_fee_council_account",
    "stay_fee_council_iban", "lock_provider", "lock_id", "checkin_hour", "checkout_hour",
]


def _apartment(aid, owner, name, entity, **extra):
    row = {"id": aid, "owner_user_id": owner, "internal_name": name, "legal_entity_id": entity,
           "data_controller_entity_id": None, "created_at": STAMP, "archived_at": None, "active": 1,
           "permalink_token": f"golden-token-{aid}", "permalink_pin": "123456", "addr_obec": "Praha 8",
           "addr_street": "Sokolovská", "addr_house_no": "10", "addr_zip": "18600", "city_en": "Prague",
           "uby_idub": "ABC123456789", "uby_mark": "AAKLI", "uby_name": "Penzion Karlín", "uby_contact": "me@example.test",
           "uby_ws_user": "UBY-WS_OLD", "stay_fee_rate_czk": 0, "stay_fee_council_account": None,
           "stay_fee_council_iban": None, "lock_provider": None, "lock_id": None, "checkin_hour": 15, "checkout_hour": 10}
    row.update(extra)
    return [row[col] for col in APARTMENT_COLUMNS]


# User 1 is an admin, 2 and 3 are hosts. Host 2: operators 21 (with an e-mail),
# 22 and archived 23; properties 201 (fee 50, a guest slug, an open police
# login alert), 202 (archived), 203 and 204 (204 sends codes on lock L2), 205
# (no times, an IBAN-only council account); a TTLock account with L1 and L2.
# Host 3: operator 31 and property 301.
SEED = [
    {"table": "user_account", "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[uid, f"update{uid}@example.test", "x", "admin" if uid == 1 else "host", STAMP] for uid in (1, 2, 3)]},
    {"table": "legal_acceptance", "columns": ["user_account_id", "document", "version", "accepted_at", "method"],
     "rows": [[uid, doc, version, STAMP, "clickwrap"] for uid in (1, 2, 3) for doc, version in VERSIONS.items()]},
    {"table": "legal_entity", "columns": ["id", "owner_user_id", "name", "contact_email", "archived_at", "created_at"],
     "rows": [[21, 2, "Alpha s.r.o.", "  provoz.alpha.s.r.o.dlouhy.kontakt@example.test  ", None, STAMP],
              [22, 2, "Beta Správa", None, None, STAMP], [23, 2, "Gone Co", "gone@example.test", "2026-01-02", STAMP],
              [31, 3, "Gamma Host", "gamma@example.test", None, STAMP]]},
    {"table": "apartment", "columns": APARTMENT_COLUMNS,
     "rows": [_apartment(201, 2, "Loft Karlín", 21, stay_fee_rate_czk=50, stay_fee_council_account="19-2000145399/0800",
                         stay_fee_council_iban="CZ6508000000192000145399"),
              _apartment(202, 2, "Old flat", 21, archived_at="2026-02-01", active=0),
              _apartment(203, 2, "Garden studio", 21, checkin_hour=14, checkout_hour=11),
              _apartment(204, 2, "Back house", 21, lock_provider="ttlock", lock_id="L2"),
              _apartment(205, 2, "Attic", 21, checkin_hour=None, checkout_hour=None, stay_fee_council_account=IBAN,
                         stay_fee_council_iban=IBAN),
              _apartment(301, 3, "Other host flat", 31)]},
    {"table": "apartment_slug", "columns": ["slug", "apartment_id", "is_current", "created_at"],
     "rows": [["loft-karlin-abc234", 201, 1, STAMP], ["old-flat-def567", 202, 1, STAMP],
              ["garden-studio-ghk892", 203, 1, STAMP], ["back-house-mnp345", 204, 1, STAMP], ["attic-qrs678", 205, 1, STAMP],
              ["other-host-flat-tuv923", 301, 1, STAMP]]},
    {"table": "lock_account", "columns": ["id", "owner_user_id", "provider", "username", "status", "locks_json",
                                          "created_at", "updated_at"],
     "rows": [[1, 2, "ttlock", "golden-lock-user", "ok", LOCKS, STAMP, STAMP]]},
    {"table": "alert", "columns": ["id", "level", "kind", "apartment_id", "owner_user_id", "dedupe_key", "message",
                                   "created_at"],
     "rows": [[1, "error", "ubyport_auth_failed", 201, 2, "ubyport_auth_failed:201", "Police login refused.", STAMP]]},
]

# What the Go test reads back from the apartment row, as text (NULL is null).
COLUMNS = [
    "owner_user_id", "internal_name", "city_en", "addr_okres", "addr_obec", "addr_obec_cast", "addr_street",
    "addr_house_no", "addr_orient_no", "addr_zip", "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user",
    "guest_message", "notes", "legal_entity_id", "data_controller_entity_id", "automation_mode", "submit_after_hours",
    "permalink_window_days", "permalink_reachback_days", "passport_photo_policy", "ocr_scan", "default_purpose",
    "active", "archived_at", "stay_fee_rate_czk", "stay_fee_vs", "stay_fee_cadence", "stay_fee_authority_name",
    "stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction",
    "stay_fee_council_account", "stay_fee_council_iban", "permalink_token", "permalink_pin", "lock_provider", "lock_id",
    "checkin_hour", "checkout_hour",
]

# The whole Settings form of the property page, as it posts for a property of host 2.
FULL = {
    "internal_name": "Loft Karlín", "legal_entity_id": "21", "data_controller_entity_id": "",
    "addr_okres": "", "addr_obec": "Praha 8", "addr_obec_cast": "Karlín", "addr_street": "Sokolovská",
    "addr_house_no": "10", "addr_orient_no": "", "addr_zip": "186 00", "uby_idub": "ABC123456789", "uby_mark": "aakli",
    "uby_name": "Penzion Karlín", "uby_contact": "me@example.test", "uby_ws_user": "UBY-WS_OLD", "uby_ws_password": "",
    "automation_mode": "manual", "submit_after_hours": "24", "default_purpose": "99", "permalink_window_days": "1",
    "permalink_reachback_days": "0", "passport_photo_policy": "off", "guest_message": "Welcome.", "notes": "",
    "checkin_hour": "15", "checkout_hour": "10", "stay_fee_rate_czk": "50", "stay_fee_vs": "", "stay_fee_cadence": "monthly",
    "account_prefix": "19", "account_number": "2000145399", "account_bank": "0800", "_stay_fee_account_existing": "",
    "letter_fields": "", "return_to": "/apartments/201?view=settings&section=property",
}


def _full(**extra):
    form = dict(FULL)
    form.update(extra)
    return form


# name, user, previewed workspace (0: none), language, with a CSRF token, property id, the form.
CASES = [
    ("signed out", 0, 0, "en", True, 201, _full()),
    ("no CSRF token", 2, 0, "en", False, 201, _full()),
    ("another host's property", 2, 0, "en", True, 301, _full()),
    ("full save: rename, new login and password, controller, later rate, PIN, times", 2, 0, "en", True, 201, _full(
        internal_name=" Loft Karlín II ", uby_ws_user="UBY-WS_MLJNO", uby_ws_password="  golden-ws-pass  ", uby_mark="",
        uby_contact="", data_controller_entity_id="22", automation_mode="scheduled", submit_after_hours="12",
        default_purpose="01", permalink_window_days="3", permalink_reachback_days="9999", ocr_scan="1",
        passport_photo_policy="required_foreign", stay_fee_rate_czk="40", stay_fee_rate_from="2026-12-01",
        stay_fee_vs="12/34", stay_fee_cadence="quarterly", stay_fee_payee="P" * 70, permalink_pin=" 654321 ",
        checkin_hour="16", checkout_hour="9", guest_message="  Hello  ", notes=" a note ",
        return_to="/apartments/201?view=settings&section=police#ubyport")),
    ("section form: same rate, account cleared, no address, no timing, no controller", 2, 0, "cs", True, 201, {
        "internal_name": "Loft Karlín II", "legal_entity_id": "21", "uby_idub": "ABC123456789", "uby_mark": "MLJNO",
        "uby_name": "Penzion Karlín", "uby_contact": "", "uby_ws_user": "UBY-WS_MLJNO", "stay_fee_rate_czk": "40",
        "stay_fee_council_account": "", "return_to": "/apartments/201?view=settings&section=reporting"}),
    ("rate from a past day applies from today", 2, 0, "en", True, 201, _full(
        internal_name="Loft Karlín II", uby_ws_user="UBY-WS_MLJNO", uby_mark="mljno", stay_fee_rate_czk="30", stay_fee_rate_from="2020-01-01",
        stay_fee_council_account="19-2000145399/0800", account_prefix="", account_number="", account_bank="")),
    ("rate back to the day's rate writes over the same day", 2, 0, "en", True, 201, _full(
        internal_name="Loft Karlín II", uby_ws_user="UBY-WS_MLJNO", uby_mark="mljno", stay_fee_rate_czk="20", stay_fee_rate_from="2026-02-30")),
    ("PIN of five digits", 2, 0, "en", True, 201, _full(internal_name="Renamed?", permalink_pin="12345")),
    ("PIN with a letter", 2, 0, "en", True, 201, _full(permalink_pin="12345a")),
    ("unsafe return_to falls back", 2, 0, "en", True, 202, _full(
        internal_name="Old flat", return_to="https://evil.example/x", stay_fee_rate_czk="0")),
    ("IBAN-only account kept, no times, rate stays 0", 2, 0, "en", True, 205, _full(
        internal_name="Attic", account_prefix="", account_number="", account_bank="", _stay_fee_account_existing=IBAN,
        stay_fee_rate_czk="0", checkin_hour="", checkout_hour="", return_to="/apartments/205")),
    ("door codes on with a listed lock", 2, 0, "en", True, 203, _full(
        internal_name="Garden studio", door_code_section="1", door_codes_fields="1", door_codes="1", lock_id="L1",
        checkin_hour="14", checkout_hour="11", stay_fee_rate_czk="0",
        return_to="/apartments/203?view=settings&section=lock#sec-lock")),
    ("a lock that is not in the list", 2, 0, "en", True, 203, _full(
        internal_name="Garden studio", door_code_section="1", door_codes_fields="1", door_codes="1", lock_id="L9",
        stay_fee_rate_czk="0", notes="must not be saved")),
    ("a lock another property uses", 2, 0, "en", True, 203, _full(
        internal_name="Garden studio", door_code_section="1", door_codes_fields="1", door_codes="1", lock_id="L2",
        stay_fee_rate_czk="0", notes="must not be saved")),
    ("door codes off keeps the lock", 2, 0, "en", True, 203, _full(
        internal_name="Garden studio", door_code_section="1", door_codes_fields="1", lock_id="L1", stay_fee_rate_czk="0")),
    ("lock tab time wins, property tab time stands", 2, 0, "en", True, 204, _full(
        internal_name="Back house", checkin_hour="15", lock_checkin_hour="17", checkout_hour="9", lock_checkout_hour="10",
        stay_fee_rate_czk="0")),
    ("archived property stays off", 2, 0, "vi", True, 202, _full(internal_name="Old flat", uby_idub="", stay_fee_rate_czk="0")),
    ("hour that is not a number", 2, 0, "en", True, 201, _full(checkin_hour="x", notes="must not be saved")),
    ("hour 24", 2, 0, "en", True, 201, _full(checkout_hour="24", notes="must not be saved")),
    ("door codes need both times", 2, 0, "en", True, 205, _full(
        internal_name="Attic", door_code_section="1", door_codes="1", lock_id="L1", checkin_hour="", stay_fee_rate_czk="0",
        return_to="/apartments/205?view=settings&section=lock")),
    ("operator refresh", 2, 0, "en", True, 201, _full(operator_refresh="1", notes="must not be saved")),
    ("another host's operator", 2, 0, "en", True, 201, _full(legal_entity_id="31", notes="must not be saved")),
    ("archived operator", 2, 0, "en", True, 201, _full(legal_entity_id="23", notes="must not be saved")),
    ("another host's controller", 2, 0, "en", True, 201, _full(data_controller_entity_id="31", notes="must not be saved")),
    ("broken address", 2, 0, "cs", True, 201, _full(addr_zip="12", addr_street=" ", notes="must not be saved")),
    ("council account that does not check", 2, 0, "en", True, 201, _full(
        account_prefix="", account_number="124", account_bank="0800", notes="must not be saved")),
    ("rename back reuses the old guest link", 2, 0, "en", True, 201, _full()),
    ("admin preview saves for the previewed host", 1, 3, "en", True, 301, _full(
        internal_name="Other host flat", legal_entity_id="31", uby_idub="", uby_ws_user="", stay_fee_rate_czk="25",
        return_to="/apartments/301")),
    ("admin preview cannot save another host's property", 1, 3, "en", True, 201, _full()),
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row))


def _row(db, apartment_id: int):
    row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    slug = db.query_one("SELECT slug FROM apartment_slug WHERE apartment_id = ? AND is_current = 1", (apartment_id,))
    return {
        "row": {col: _text(row[col]) for col in COLUMNS},
        "password": db.decrypt_secret(row["uby_ws_password_enc"]) if row["uby_ws_password_enc"] else None,
        "rates": [[r["rate_czk"], r["effective_from"]] for r in db.query(
            "SELECT rate_czk, effective_from FROM stay_fee_rate WHERE apartment_id = ? ORDER BY effective_from",
            (apartment_id,))],
        "slug": slug["slug"] if slug else None,
        "alerts": [r["dedupe_key"] for r in db.query(
            "SELECT dedupe_key FROM alert WHERE apartment_id = ? AND resolved_at IS NULL ORDER BY id", (apartment_id,))],
    }


def render() -> str:
    from fastapi.testclient import TestClient

    from app import auth, claim, db, security
    from app.main import app

    claim.prague_today = lambda: TODAY
    db.init_db()
    _seed(db)
    client = TestClient(app)
    cases = []
    for name, user, workspace, lang, csrf, apartment_id, form in CASES:
        client.cookies.clear()
        cookies = {"ubyhost_lang": lang, security.CSRF_COOKIE: CSRF_NONCE}
        if user:
            cookies[auth.SESSION_COOKIE] = auth.issue_session(
                user, 1, workspace_user_id=workspace or None,
                impersonation_started_at=int(time.time()) if workspace else None)
        data = dict(form)
        if csrf:
            data["_csrf"] = security._csrf_serializer().dumps({"nonce": security._nonce_binding(CSRF_NONCE)})
        audit_before = db.query_one("SELECT COALESCE(MAX(id), 0) AS n FROM audit")["n"]
        before = _row(db, apartment_id)
        header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        response = client.post(f"/apartments/{apartment_id}", data=data, headers={"Cookie": header},
                               follow_redirects=False)
        after = _row(db, apartment_id)
        case = {"name": name, "user": user, "workspace": workspace, "lang": lang, "csrf": csrf, "id": apartment_id,
                "form": form, "status": response.status_code, "location": response.headers.get("location"),
                "after": after, "changed": after != before,
                "page": response.status_code in (200, 400) and not response.headers.get("location"),
                "audit": [dict(r) for r in db.query(
                    "SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit "
                    "WHERE id > ? ORDER BY id", (audit_before,))]}
        cases.append(case)
    golden = {"csrf_nonce": CSRF_NONCE, "seed": SEED, "columns": COLUMNS, "cases": cases}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/go_apartment_update_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "apartment_update_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_BOOTSTRAP_ADMIN", "0")
    # Door codes on, unbilled, with made-up app credentials (no TTLock call is made).
    os.environ.setdefault("UBYHOST_DOOR_CODES", "1")
    os.environ.setdefault("UBYHOST_TTLOCK_CLIENT_ID", "golden-client")
    os.environ.setdefault("UBYHOST_TTLOCK_CLIENT_SECRET", "golden-secret")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
