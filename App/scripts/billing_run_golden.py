"""Write go/internal/billingjob/testdata/run.golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/billing_run_golden.py

It seeds a throwaway SQLite database with SEED (one scenario per host:
trials, rolls, invoices, apartment counts, dunning stages), then calls
app/billing_jobs.run(day) for each entry of RUNS in order, so each run sees what
the one before wrote. Each run records the counts Python returns. At the end it
dumps the rows the runs wrote: billing_account (without updated_at),
platform_invoice (without created_at, pdf_blob and pdf_sha256; ``has_pdf`` says
the stored sha256 matches the stored bytes), platform_invoice_sequence, the
audit rows and the email_outbox rows. go/internal/billingjob/run_golden_test.go
replays the same runs in Go on Postgres and compares everything. The PDF bytes
differ (reportlab against go/internal/pdf), so they are not compared. A run's
"env" changes the environment before it.
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
OUT = APP.parent / "go" / "internal" / "billingjob" / "testdata" / "run.golden.json"

ENV = {
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_BILLING_ENABLED": "1",
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
    "UBYHOST_BILLING_ENABLED": "BILLING_ENABLED",
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

USER_COLS = ["id", "username", "password_hash", "role", "created_at", "email", "active", "email_verified_at"]
ACCOUNT_COLS = [
    "owner_user_id", "status", "plan", "billing_interval", "addon_ttlock", "addon_whitelabel",
    "apartments_billed", "trial_started_at", "trial_ends_at", "period_start", "period_end",
    "pending_change_json", "carry_czk", "buyer_name", "buyer_street", "buyer_city", "buyer_zip",
    "buyer_ico", "buyer_dic", "buyer_email", "updated_at", "discount_percent", "discount_reason",
]
INVOICE_COLS = [
    "id", "owner_user_id", "kind", "corrects_id", "seq_year", "seq_no", "number", "vs",
    "issue_date", "due_date", "period_from", "period_to", "total_haler", "voided", "paid_on",
    "paid_via", "snapshot_json", "created_at",
]
APARTMENT_COLS = ["id", "owner_user_id", "internal_name", "active", "created_at"]


def _snapshot(number: str) -> str:
    rows = [{"description": "Předplatné UbyHost Standard, 1 apartmán", "quantity": 1, "gross_haler": 14900}]
    return json.dumps({"invoice": {"number": number}, "items": rows}, ensure_ascii=False, sort_keys=True)


def _account(owner, status, plan=None, interval=None, *, ttlock=0, whitelabel=0, billed=1, started=None,
             ends=None, start=None, end=None, pending=None, carry=0, buyer="Host %d s.r.o.", email=None,
             discount=0):
    name = buyer % owner if buyer and "%d" in buyer else buyer
    return [owner, status, plan, interval, ttlock, whitelabel, billed, started, ends, start, end, pending,
            carry, name, "Hlavní 12", "Praha", "11000", "", "", email, NOW, discount, None]


_invoices: list = []


def _invoice(owner, period_from, period_to, due, *, kind="invoice", paid_on=None, voided=0, seq=None):
    number_id = len(_invoices) + 1
    seq = seq or number_id
    number = f"UBY-2026-{seq:04d}"
    _invoices.append([
        number_id, owner, kind, None, 2026, seq, number, f"2026{seq:04d}", "2026-09-01", due,
        period_from, period_to, 14900, voided, paid_on, "bank_manual" if paid_on else None,
        _snapshot(number), NOW])


users, accounts, apartments = [], [], []


def _host(owner, email="default", verified=None, active=1):
    users.append([owner, f"u{owner}", "x", "host", NOW,
                  f"owner{owner}@example.test" if email == "default" else email, active, verified])


def _flats(owner, n, active=1):
    for _ in range(n):
        apartments.append([len(apartments) + 1, owner, f"Byt {len(apartments) + 1}", active, NOW])


# --- trials ------------------------------------------------------------------
_host(1, verified="2026-10-20T10:00:00+00:00")          # pending, verified: starts, ends 2026-11-19
accounts.append(_account(1, "trial_pending"))
_host(2)                                                # pending, never verified: stays
accounts.append(_account(2, "trial_pending"))
_host(3, verified="2026-11-20T10:00:00+00:00")          # pending, verified in the future: stays
accounts.append(_account(3, "trial_pending"))
_host(4, verified="2026-10-14T23:30:00+00:00")          # Prague date 15 Oct, ends 14 Nov (UTC+30 days)
accounts.append(_account(4, "trial_pending"))
_host(5)                                                # seven days left, no plan: mail to the login address
accounts.append(_account(5, "trialing", started="2026-10-21", ends="2026-11-20"))
_host(6)                                                # three days left: mail to the billing address
accounts.append(_account(6, "trialing", started="2026-10-17", ends="2026-11-16", email="  billing6@example.test "))
_host(7)                                                # last day: mail
accounts.append(_account(7, "trialing", started="2026-10-14", ends="2026-11-13"))
_host(8)                                                # seven days left but a plan is ordered: no mail
accounts.append(_account(8, "trialing", "standard", "month", started="2026-10-21", ends="2026-11-20"))
_host(9)                                                # ended yesterday, plan ordered: active, then invoiced
accounts.append(_account(9, "trialing", "standard", "month", billed=2, started="2026-10-13", ends="2026-11-12"))
_flats(9, 2)
_host(10)                                               # ended, no plan: paused
accounts.append(_account(10, "trialing", started="2026-10-01", ends="2026-11-01"))
_host(11, email=None)                                   # reminder due but nobody to mail
accounts.append(_account(11, "trialing", started="2026-10-21", ends="2026-11-20"))

# --- periods, invoices, apartments ------------------------------------------------
_host(12)                                               # period ends today: not rolled; invoice issued
accounts.append(_account(12, "active", "standard", "month", billed=3, start="2026-10-14", end="2026-11-13"))
_flats(12, 3)
_host(13)                                               # period over, pending change: rolled to Max + TTLock
accounts.append(_account(13, "active", "standard", "month", billed=1, start="2026-10-01", end="2026-10-31",
                         pending='{"plan": "max", "addon_ttlock": 1}'))
_flats(13, 2)
_flats(13, 1, active=0)
_host(14)                                               # canceling and over: paused
accounts.append(_account(14, "canceling", "standard", "month", start="2026-10-01", end="2026-10-31"))
_host(15)                                               # canceling, not over, already invoiced
accounts.append(_account(15, "canceling", "standard", "month", start="2026-11-01", end="2026-11-30"))
_invoice(15, "2026-11-01", "2026-11-30", "2026-11-15", seq=1)
_host(16)                                               # overdue and over, annual: rolled, invoiced for a year
accounts.append(_account(16, "overdue", "max", "year", billed=5, start="2025-11-01", end="2026-10-31", ttlock=1))
_flats(16, 5)
_host(17)                                               # annual rise 2 to 4: supplementary invoice (595 Kc)
accounts.append(_account(17, "active", "standard", "year", billed=2, start="2026-03-01", end="2027-02-28"))
_invoice(17, "2026-03-01", "2027-02-28", "2026-03-15", paid_on="2026-03-10", seq=2)
_flats(17, 4)
_host(18)                                               # fewer apartments: pending change next period
accounts.append(_account(18, "active", "standard", "month", billed=2, start="2026-11-01", end="2026-11-30",
                         pending='{"plan": "max"}'))
_invoice(18, "2026-11-01", "2026-11-30", "2026-11-15", paid_on="2026-11-02", seq=3)
_flats(18, 1)
_host(19)                                               # fewer apartments, change already pending: skipped
accounts.append(_account(19, "active", "standard", "month", billed=3, start="2026-11-01", end="2026-11-30",
                         pending='{"apartments": 1}'))
_invoice(19, "2026-11-01", "2026-11-30", "2026-11-15", paid_on="2026-11-02", seq=4)
_flats(19, 1)
_host(20)                                               # annual rise, tiny difference: carried (10 Kc)
accounts.append(_account(20, "active", "standard", "year", billed=1, start="2026-01-01", end="2026-12-31",
                         discount=90))
_invoice(20, "2026-01-01", "2026-12-31", "2026-01-15", paid_on="2026-01-10", seq=5)
_flats(20, 2)
_host(21)                                               # annual rise 2 to 3 for 9 months: 892.5 rounds to 892
accounts.append(_account(21, "active", "standard", "year", billed=2, start="2026-09-01", end="2027-08-31"))
_invoice(21, "2026-09-01", "2027-08-31", "2026-09-15", paid_on="2026-09-10", seq=6)
_flats(21, 3)
_host(22)                                               # nothing to do
accounts.append(_account(22, "active", "standard", "month", billed=1, start="2026-11-01", end="2026-11-30"))
_invoice(22, "2026-11-01", "2026-11-30", "2026-11-15", paid_on="2026-11-02", seq=7)
_flats(22, 1)
_host(23)                                               # no buyer name: the invoice fails, the others go on
accounts.append(_account(23, "active", "standard", "month", billed=1, start="2026-11-01", end="2026-11-30",
                         buyer="   "))
_host(24)                                               # annual rise with no buyer name: change saved, invoice fails
accounts.append(_account(24, "active", "standard", "year", billed=2, start="2026-03-01", end="2027-02-28",
                         buyer=None))
_invoice(24, "2026-03-01", "2027-02-28", "2026-03-15", paid_on="2026-03-10", seq=8)
_flats(24, 4)
_host(25)                                               # rise on a monthly plan, a day later than the period start
accounts.append(_account(25, "active", "standard", "month", billed=1, start="2026-11-05", end="2026-12-04"))
_invoice(25, "2026-11-05", "2026-12-04", "2026-11-19", paid_on="2026-11-06", seq=9)
_flats(25, 6)
_host(26)                                               # a period that starts later: not invoiced yet
accounts.append(_account(26, "active", "standard", "month", billed=1, start="2026-11-20", end="2026-12-19"))
_flats(26, 1)

# --- dunning (period dates left empty: only the dunning touches these hosts) ----------
_host(30)                                               # 7 days late, active: overdue + reminder
accounts.append(_account(30, "active", "standard", "month"))
_invoice(30, "2026-10-01", "2026-10-31", "2026-11-06", seq=20)
_host(31)                                               # 14 days late: read-only
accounts.append(_account(31, "active", "standard", "month"))
_invoice(31, "2026-10-01", "2026-10-31", "2026-10-30", seq=21)
_host(32)                                               # overdue already, 12 days late: reminder
accounts.append(_account(32, "overdue", "standard", "month"))
_invoice(32, "2026-10-01", "2026-10-31", "2026-11-01", seq=22)
_host(33)                                               # 45 days late: monthly bucket 1
accounts.append(_account(33, "active", "standard", "month"))
_invoice(33, "2026-09-01", "2026-09-30", "2026-09-29", seq=23)
_host(34)                                               # paused, 1 day late: nothing
accounts.append(_account(34, "paused", "standard", "month"))
_invoice(34, "2026-10-01", "2026-10-31", "2026-11-12", seq=24)
_host(35)                                               # a supplementary invoice, 8 days late
accounts.append(_account(35, "active", "standard", "year"))
_invoice(35, "2026-10-01", "2026-10-31", "2026-11-05", kind="supplementary", seq=25)
_host(36)                                               # voided: ignored
accounts.append(_account(36, "active", "standard", "month"))
_invoice(36, "2026-10-01", "2026-10-31", "2026-10-01", voided=1, seq=26)
_host(37)                                               # paid: ignored
accounts.append(_account(37, "active", "standard", "month"))
_invoice(37, "2026-10-01", "2026-10-31", "2026-10-01", paid_on="2026-10-05", seq=27)
_host(38)                                               # two unpaid invoices, 8 and 20 days late
accounts.append(_account(38, "active", "standard", "month"))
_invoice(38, "2026-10-01", "2026-10-31", "2026-11-05", seq=28)
_invoice(38, "2026-09-01", "2026-09-30", "2026-10-24", seq=29)
_host(39, email=None)                                   # 8 days late and nobody to mail
accounts.append(_account(39, "active", "standard", "month"))
_invoice(39, "2026-10-01", "2026-10-31", "2026-11-05", seq=30)
_host(40)                                               # a storno is never dunned
accounts.append(_account(40, "active", "standard", "month"))
_invoice(40, "2026-10-01", "2026-10-31", "2026-10-01", kind="storno", seq=31)
_host(43)                                               # exactly 44 days late: the first monthly mail
accounts.append(_account(43, "active", "standard", "month"))
_invoice(43, "2026-09-01", "2026-09-30", "2026-09-30", seq=32)
_host(44)                                               # 43 days late: still the read-only mail
accounts.append(_account(44, "active", "standard", "month"))
_invoice(44, "2026-09-01", "2026-09-30", "2026-10-01", seq=33)
_host(41)                                               # a host with no billing account at all
_host(42)                                               # not billed: trial_pending host with unverified mail, inactive login
accounts.append(_account(42, "trial_pending"))
users[-1][6] = 0
users[-1][7] = "2026-10-01T10:00:00+00:00"

SEED = [
    {"table": "user_account", "columns": USER_COLS, "rows": users},
    {"table": "billing_account", "columns": ACCOUNT_COLS, "rows": accounts},
    {"table": "apartment", "columns": APARTMENT_COLS, "rows": apartments},
    {"table": "platform_invoice", "columns": INVOICE_COLS, "rows": _invoices},
    {"table": "platform_invoice_sequence", "columns": ["year", "last_no"], "rows": [[2026, 33]]},
]

RUNS = [
    {"name": "r1", "day": "2026-11-13"},
    {"name": "r2_same_day", "day": "2026-11-13"},
    {"name": "r3_billing_off", "day": "2026-11-14", "env": {"UBYHOST_BILLING_ENABLED": "no"}},
    {"name": "r4_mail_off", "day": "2026-11-15", "env": {"UBYHOST_BILLING_ENABLED": "yes", "UBYHOST_MAIL_BACKEND": "disabled"}},
    {"name": "r5_late", "day": "2026-12-30", "env": {"UBYHOST_MAIL_BACKEND": "ses"}},
]

ACCOUNT_DUMP = [c for c in ACCOUNT_COLS if c != "updated_at"]
INVOICE_DUMP = [c for c in INVOICE_COLS if c != "created_at"]
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
        if name == "UBYHOST_MAIL_BACKEND":
            value = value.strip().lower()
        if name == "UBYHOST_BILLING_ENABLED":
            value = value.lower() in ("1", "true", "yes")
        setattr(config, CONFIG_ATTR[name], value)


def render() -> str:
    """Seed a fresh database, run RUNS, return the golden JSON text."""
    from app import billing_jobs, config, db

    saved = {attr: getattr(config, attr) for attr in CONFIG_ATTR.values()}
    try:
        _apply_env(config, ENV)
        db.init_db()
        _seed(db)
        results = []
        for run in RUNS:
            _apply_env(config, run.get("env", {}))
            counts = billing_jobs.run(date.fromisoformat(run["day"]))
            results.append({"name": run["name"], "counts": counts})
        invoices = []
        for row in db.query("SELECT * FROM platform_invoice ORDER BY id"):
            blob = row["pdf_blob"]
            has_pdf = bool(blob) and hashlib.sha256(bytes(blob)).hexdigest() == row["pdf_sha256"]
            record = {c: row[c] for c in INVOICE_DUMP}
            record["has_pdf"] = has_pdf
            invoices.append(record)
        emails = []
        for row in db.query(f"SELECT {', '.join(EMAIL_COLUMNS)} FROM email_outbox ORDER BY idempotency_key"):
            emails.append({c: row[c] for c in EMAIL_COLUMNS})
        golden = {
            "env": ENV,
            "seed": SEED,
            "runs": RUNS,
            "results": results,
            "accounts": [{c: row[c] for c in ACCOUNT_DUMP}
                         for row in db.query("SELECT * FROM billing_account ORDER BY owner_user_id")],
            "invoices": invoices,
            "sequence": [dict(r) for r in db.query("SELECT year, last_no FROM platform_invoice_sequence ORDER BY year")],
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
    os.environ["UBYHOST_DATA_DIR"] = str(tmp)
    os.environ["UBYHOST_DB"] = str(tmp / "billing_run_golden.sqlite3")
    os.environ.pop("UBYHOST_DATABASE_URL", None)
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
