"""Write go/internal/billingjob/testdata/invoicer.golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/billing_invoice_golden.py

It seeds a throwaway SQLite database with SEED, then runs STEPS in order against
app/billing_invoices.py (issue_for_period, issue_supplementary, storno, send), so
each step sees what the one before wrote. Each step records its result (the new
id, or the ValueError text). At the end it dumps the rows the steps wrote:
platform_invoice (without created_at, pdf_blob and pdf_sha256; ``has_pdf`` says
the stored sha256 matches the stored bytes), platform_invoice_sequence, the
carry_czk of every billing_account, the audit rows and the email_outbox rows.
go/internal/billingjob/invoicer_test.go replays the same steps in Go and compares
everything. The PDF bytes differ (reportlab against go/internal/pdf), so they are
not compared. A step's "env" changes the environment before it (mail backend).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "billingjob" / "testdata" / "invoicer.golden.json"

ENV = {
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_OPERATOR_NAME": "UbyHost s.r.o. <Test> & Co",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_DIC": "CZ12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Dlouhá 1, 602 00 Brno",
    "UBYHOST_OPERATOR_EMAIL": "ops@example.test",
    "UBYHOST_BILLING_IBAN": "CZ6508000000192000145399",
    "UBYHOST_BILLING_BANK_ACCOUNT": "19-2000145399/0800",
    "UBYHOST_BILLING_VAT_STATUS": "non_payer",
}
# Environment variable -> app.config attribute (read by config at import time).
CONFIG_ATTR = {
    "UBYHOST_APP_BASE_URL": "APP_BASE_URL",
    "UBYHOST_PUBLIC_BASE_URL": "PUBLIC_BASE_URL",
    "UBYHOST_MAIL_BACKEND": "MAIL_BACKEND",
    "UBYHOST_OPERATOR_NAME": "OPERATOR_NAME",
    "UBYHOST_OPERATOR_ICO": "OPERATOR_ICO",
    "UBYHOST_OPERATOR_DIC": "OPERATOR_DIC",
    "UBYHOST_OPERATOR_ADDRESS": "OPERATOR_ADDRESS",
    "UBYHOST_OPERATOR_EMAIL": "OPERATOR_EMAIL",
    "UBYHOST_BILLING_IBAN": "BILLING_IBAN",
    "UBYHOST_BILLING_BANK_ACCOUNT": "BILLING_BANK_ACCOUNT",
    "UBYHOST_BILLING_VAT_STATUS": "BILLING_VAT_STATUS",
}

NOW = "2026-01-01T00:00:00+00:00"


def _snapshot(number: str, items: list) -> str:
    rows = [{"description": d, "quantity": 1, "gross_haler": h} for d, h in items]
    return json.dumps({"invoice": {"number": number}, "items": rows}, ensure_ascii=False, sort_keys=True)


USER_COLS = ["id", "username", "password_hash", "role", "created_at", "email"]
ACCOUNT_COLS = [
    "owner_user_id", "status", "plan", "billing_interval", "addon_ttlock", "addon_whitelabel",
    "apartments_billed", "carry_czk", "buyer_name", "buyer_street", "buyer_city", "buyer_zip",
    "buyer_ico", "buyer_dic", "buyer_email", "updated_at", "discount_percent", "discount_reason",
]
INVOICE_COLS = [
    "id", "owner_user_id", "kind", "corrects_id", "seq_year", "seq_no", "number", "vs",
    "issue_date", "due_date", "period_from", "period_to", "total_haler", "voided", "paid_on",
    "paid_via", "snapshot_json", "created_at",
]

SEED = [
    {"table": "user_account", "columns": USER_COLS, "rows": [
        [1, "u1", "x", "host", NOW, "owner1@example.test"],
        [2, "u2", "x", "host", NOW, "  owner2@example.test  "],
        [3, "u3", "x", "host", NOW, "owner3@example.test"],
        [4, "u4", "x", "host", NOW, "owner4@example.test"],
        [5, "u5", "x", "host", NOW, "owner5@example.test"],
        [6, "u6", "x", "host", NOW, None],
    ]},
    {"table": "billing_account", "columns": ACCOUNT_COLS, "rows": [
        # 3 apartments, standard, month, TTLock, 10 % discount with a reason, carry 120.
        [1, "active", "standard", "month", 1, 0, 3, 120, 'Novák & syn, s.r.o. "Test"',
         "Hlavní 12", "Praha", "11000", "12345678", "CZ12345678", "  billing@example.test  ",
         NOW, 10, "Věrnostní sleva"],
        # 7 apartments, max, year, white label; the buyer has no billing e-mail.
        [2, "active", "max", "year", 0, 1, 7, 0, "Hotel Říčany a.s.", "Nádražní 5", "Říčany",
         "25101", "", "", None, NOW, 0, None],
        # A blank buyer name: buyer_missing.
        [3, "active", "standard", "month", 0, 0, 2, 0, "   ", None, None, None, None, None,
         None, NOW, 0, None],
        # No plan yet: no_plan.
        [4, "trialing", None, None, 0, 0, 1, 0, "Pavel Černý", "Ulice 1", "Brno", "60200",
         "", "", None, NOW, 0, None],
        # 1 apartment, standard, month; no e-mail anywhere (user_account.email is NULL).
        [6, "active", "standard", "month", 0, 0, 1, 0, "Eva Malá", "Polní 3", "Ostrava", "70200",
         "", "", None, NOW, 0, None],
    ]},
    {"table": "platform_invoice", "columns": INVOICE_COLS, "rows": [
        # 1: paid.
        [1, 1, "invoice", None, 2026, 38, "UBY-2026-0038", "20260038", "2026-09-01", "2026-09-15",
         "2026-08-01", "2026-08-31", 14900, 0, "2026-09-05", "bank_manual",
         _snapshot("UBY-2026-0038", [("Předplatné UbyHost Standard, 1 apartmán", 14900)]), NOW],
        # 2: workspace deleted (no owner).
        [2, None, "invoice", None, 2026, 39, "UBY-2026-0039", "20260039", "2026-09-01", "2026-09-15",
         "2026-08-01", "2026-08-31", 14900, 0, None, None,
         _snapshot("UBY-2026-0039", [("Předplatné UbyHost Standard, 1 apartmán", 14900)]), NOW],
        # 3: owner 5 has no billing account (buyer_missing on storno).
        [3, 5, "invoice", None, 2026, 40, "UBY-2026-0040", "20260040", "2026-09-01", "2026-09-15",
         "2026-09-01", "2026-09-30", 14900, 0, None, None,
         _snapshot("UBY-2026-0040", [("Předplatné UbyHost Standard, 1 apartmán", 14900)]), NOW],
        # 4: odd haler amounts: the storno floors them (-1499 // 100 is -15, so +15 Kč).
        [4, 1, "invoice", None, 2026, 41, "UBY-2026-0041", "20260041", "2026-09-01", "2026-09-15",
         "2026-09-01", "2026-09-30", 13401, 0, None, None,
         _snapshot("UBY-2026-0041", [("Předplatné UbyHost Standard, 3 apartmány", 14900),
                                      ("Sleva 10 %", -1499)]), NOW],
    ]},
    {"table": "platform_invoice_sequence", "columns": ["year", "last_no"], "rows": [[2026, 41]]},
]

# Each step: name, op, args, optional "env" (applied before the step). A "target"
# is an invoice id: an int, or the name of an earlier step whose result is the id.
NOV = ("2026-11-01", "2026-11-30")
STEPS = [
    {"name": "a1", "op": "issue_for_period", "owner": 1, "from": NOV[0], "to": NOV[1], "today": "2026-11-01"},
    {"name": "a2", "op": "issue_for_period", "owner": 1, "from": NOV[0], "to": NOV[1], "today": "2026-11-03"},
    {"name": "b1", "op": "issue_for_period", "owner": 2, "from": "2026-11-01", "to": "2027-10-31", "today": "2026-11-02"},
    {"name": "c1", "op": "issue_for_period", "owner": 3, "from": NOV[0], "to": NOV[1], "today": "2026-11-02"},
    {"name": "d1", "op": "issue_for_period", "owner": 4, "from": NOV[0], "to": NOV[1], "today": "2026-11-02"},
    {"name": "e1", "op": "issue_for_period", "owner": 5, "from": NOV[0], "to": NOV[1], "today": "2026-11-02"},
    {"name": "f1", "op": "issue_for_period", "owner": 6, "from": "2026-11-10", "to": "2026-12-09", "today": "2026-11-10"},
    {"name": "s1", "op": "issue_supplementary", "owner": 1, "amount": 49,
     "description": "Doplatek: změna na 4 apartmány", "from": NOV[0], "to": NOV[1], "today": "2026-11-15"},
    {"name": "s2", "op": "issue_supplementary", "owner": 1, "amount": 500,
     "description": 'Doplatek: změna na 4 apartmány, "<&>" a \\ lomítko', "from": NOV[0], "to": NOV[1],
     "today": "2026-11-15"},
    {"name": "s3", "op": "issue_supplementary", "owner": 5, "amount": 100,
     "description": "Doplatek", "from": NOV[0], "to": NOV[1], "today": "2026-11-15"},
    {"name": "s4", "op": "issue_supplementary", "owner": 3, "amount": 50,
     "description": "Doplatek", "from": NOV[0], "to": NOV[1], "today": "2026-11-15"},
    {"name": "s5", "op": "issue_supplementary", "owner": 2, "amount": 50,
     "description": "Doplatek za 1 apartmán", "from": "2026-11-01", "to": "2027-10-31", "today": "2026-12-25"},
    {"name": "send_a1", "op": "send", "target": "a1"},
    {"name": "send_a1_again", "op": "send", "target": "a1"},
    {"name": "send_b1", "op": "send", "target": "b1"},
    {"name": "send_f1", "op": "send", "target": "f1"},
    {"name": "send_s2", "op": "send", "target": "s2"},
    {"name": "send_missing", "op": "send", "target": 999},
    {"name": "send_no_owner", "op": "send", "target": 2},
    {"name": "send_mail_off", "op": "send", "target": "s5", "env": {"UBYHOST_MAIL_BACKEND": "disabled"}},
    {"name": "send_s5", "op": "send", "target": "s5", "env": {"UBYHOST_MAIL_BACKEND": "ses"}},
    {"name": "t1", "op": "storno", "target": "a1", "reason": "Chybná adresa", "today": "2026-11-16",
     "env": {"UBYHOST_MAIL_BACKEND": "console"}},
    {"name": "t2", "op": "storno", "target": "a1", "reason": "Znovu", "today": "2026-11-16"},
    {"name": "t3", "op": "storno", "target": "t1", "reason": "Storno stornu", "today": "2026-11-16"},
    {"name": "t4", "op": "storno", "target": 999, "reason": "Neexistuje", "today": "2026-11-16"},
    {"name": "t5", "op": "storno", "target": 1, "reason": "Zaplaceno", "today": "2026-11-16"},
    {"name": "t6", "op": "storno", "target": 2, "reason": "Bez vlastníka", "today": "2026-11-16"},
    {"name": "t7", "op": "storno", "target": 3, "reason": "Bez účtu", "today": "2026-11-16"},
    {"name": "t8", "op": "storno", "target": 4, "reason": "Haléře", "today": "2026-11-17"},
    {"name": "t9", "op": "storno", "target": "s2", "reason": "", "today": "2026-12-31"},
    {"name": "send_t1", "op": "send", "target": "t1"},
    {"name": "a3", "op": "issue_for_period", "owner": 1, "from": NOV[0], "to": NOV[1], "today": "2026-11-20"},
    {"name": "f2", "op": "issue_for_period", "owner": 6, "from": "2026-12-25", "to": "2027-01-24", "today": "2026-12-25"},
    {"name": "f3", "op": "issue_for_period", "owner": 6, "from": "2027-01-25", "to": "2027-02-24", "today": "2027-01-02"},
    {"name": "send_f3", "op": "send", "target": "f3"},
]

INVOICE_DUMP = [c for c in INVOICE_COLS if c != "created_at"] + ["has_pdf"]
EMAIL_COLUMNS = ["idempotency_key", "kind", "reservation_id", "apartment_id", "owner_user_id",
                 "to_email", "cc_email", "subject", "payload", "state", "attempts"]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _apply_env(config, env: dict) -> None:
    for name, value in env.items():
        setattr(config, CONFIG_ATTR[name], value.strip().lower() if name == "UBYHOST_MAIL_BACKEND" else value)


def _run(billing_invoices, step: dict, ids: dict):
    target = step.get("target")
    if isinstance(target, str):
        target = ids[target]
    when = date.fromisoformat(step["today"]) if "today" in step else None
    op = step["op"]
    if op == "issue_for_period":
        return billing_invoices.issue_for_period(step["owner"], step["from"], step["to"], today=when)
    if op == "issue_supplementary":
        return billing_invoices.issue_supplementary(
            step["owner"], amount_czk=step["amount"], description=step["description"],
            period_from=step["from"], period_to=step["to"], today=when)
    if op == "storno":
        return billing_invoices.storno(target, reason=step["reason"], today=when)
    return billing_invoices.send(target)


def render() -> str:
    """Seed a fresh database, run STEPS, return the golden JSON text."""
    from app import billing_invoices, config, db

    saved = {attr: getattr(config, attr) for attr in CONFIG_ATTR.values()}
    try:
        _apply_env(config, ENV)
        db.init_db()
        _seed(db)
        ids, results = {}, []
        for step in STEPS:
            _apply_env(config, step.get("env", {}))
            try:
                value = _run(billing_invoices, step, ids)
                record = {"id": value} if step["op"] != "send" else {"mail_id": value is not None}
                if step["op"] != "send":
                    ids[step["name"]] = value
            except ValueError as exc:
                record = {"error": str(exc)}
            results.append({"name": step["name"], **record})
        invoices = []
        for row in db.query("SELECT * FROM platform_invoice ORDER BY id"):
            blob = row["pdf_blob"]
            has_pdf = bool(blob) and hashlib.sha256(bytes(blob)).hexdigest() == row["pdf_sha256"]
            record = {c: row[c] for c in INVOICE_COLS if c != "created_at"}
            record["has_pdf"] = has_pdf
            invoices.append(record)
        emails = []
        for row in db.query(f"SELECT {', '.join(EMAIL_COLUMNS)} FROM email_outbox ORDER BY idempotency_key"):
            emails.append({c: row[c] for c in EMAIL_COLUMNS})
        golden = {
            "env": ENV,
            "seed": SEED,
            "steps": STEPS,
            "results": results,
            "invoices": invoices,
            "sequence": [dict(r) for r in db.query("SELECT year, last_no FROM platform_invoice_sequence ORDER BY year")],
            "carry": [dict(r) for r in db.query("SELECT owner_user_id, carry_czk FROM billing_account ORDER BY owner_user_id")],
            "audit": [dict(r) for r in db.query(
                "SELECT actor, action, detail, owner_user_id FROM audit ORDER BY id")],
            "emails": emails,
        }
    finally:
        for attr, value in saved.items():
            setattr(config, attr, value)
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def prepare_env() -> None:
    """The process environment, before ``app`` is imported."""
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "billing_invoice_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.update(ENV)
    sys.path.insert(0, str(APP))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    prepare_env()
    main()
