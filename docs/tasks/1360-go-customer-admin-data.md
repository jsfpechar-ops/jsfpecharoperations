# 1360: Go customer admin: data layer, funnel redirect, account toggle (part 1 of 3: Python golden fixture)

<<<<<<< HEAD
Status: todo
=======
Status: review
>>>>>>> go-customer-admin-pages
Depends on: none | Base commit: a83df5412638cc7ae1c64810e5b0b59fc68997cc | Branch: go-customer-admin (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Add the Python golden script that runs the real customer-admin code (`App/app/admin_customers.py`, the route-level queries of `App/app/routes/admin_customers.py`, the toggle and funnel routes) on a fixed SQLite seed and writes `go/internal/web/customers/testdata/admin_customers_golden.json`, plus a pytest that fails when that file is stale. Briefs 1362 and 1363 port the code to Go and must reproduce this file on PostgreSQL, so it is the parity contract for the whole task.

## 2. Context

- Split: this task is three briefs run in order on one branch, one executor session each: 1360 (Python golden fixture), 1362 (Go queries), 1363 (Go guard, funnel, toggle, routes). Brief 1361 (HTML pages) comes later. The orchestrator opens one draft PR after 1363.
- Plan: `docs/plans/go-full-move.md` §2 (parity first: a Python golden script writes fixtures, the Go code reproduces them) and §7 row "Port customer admin pages" (Tier B, own package `go/internal/web/customers/`). You do not need to open it.
- Every file in this brief is NEW and given in full. Create it byte for byte from its block in §4 (everything between the `~~~~` fence lines, ending with one newline) and check its sha256. If the sha256 differs: compare with the block once, fix, check again; still different: STOP (§8). Never edit an existing file.
- The port stays switched off: no Caddy, env, `UBYHOST_GO_PATHS` or `docs/ENVIRONMENT.md` change. No new dependency (rule 4). SQL Postgres-portable (rule 5). Never push to `main` (rule 8).
- The script mirrors `App/scripts/dsr_due_golden.py`: it seeds a throwaway database (its own temp dir and env), so it never touches a real database. Its output is deterministic (same sha256 on every run).
- Coverage of the fixture: `q` with `%`, `_`, `!`, case and non-ASCII; every state, `ending`, both plans, bad values; `after`/`before` seek pagination over more than 25 rows; `summary`; `detail` (10 newest of 12 invoices, `buyer_prefill` with and without legal entity, ZIP normalisation, archived and inactive apartments ignored), `activity` ordering and its LIMIT 20, `operator_log` LIMIT 20; missing e-mail count; consent counts; `billing.account`; `_cursor`; `_kc`; the toggle (enable, disable in Czech, own-account refusal, unknown user 404, non-admin 403 with audit rows and session_version before/after) and the funnel redirect.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/admin_customers_golden.py` | create | writes the golden JSON from the real Python |
| `App/tests/test_admin_customers_golden.py` | create | fails when the golden JSON is stale |
| `go/internal/web/customers/testdata/admin_customers_golden.json` | create (generated) | output of the script, about 2050 lines |
| `docs/tasks/1360-go-customer-admin-data.md` | edit | `Status:` line only |
| `docs/tasks/1360-report.md` | create | your report |

No other file may change.

## 4. Steps

Commit after each step with the message `1360 step k`.

### Step 1: the script and its pytest

Create `App/scripts/admin_customers_golden.py`:

~~~~python
"""Write go/internal/web/customers/testdata/admin_customers_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/admin_customers_golden.py          write the file
    .venv/bin/python scripts/admin_customers_golden.py --check  exit 1 when it is stale

It seeds a throwaway SQLite database with the fixed rows in SEED, runs
admin_customers.customers / summary / detail, the two route-level queries of
routes/admin_customers.py (missing e-mail count, consent counts), billing.account,
_cursor and _kc, and then drives the real toggle and funnel routes through
TestClient. go/internal/web/customers/*_test.go seeds PostgreSQL from the same
file and compares. App/tests/test_admin_customers_golden.py fails when this
file is stale.

The toggle phase runs last, so it cannot change the data cases above it.
The "i18n" section is the host strings go/internal/web/customers/i18n.json must hold.
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
OUT = APP.parent / "go" / "internal" / "web" / "customers" / "testdata" / "admin_customers_golden.json"

TODAY = "2026-11-13"
STAMP = "2026-09-01T00:00:00+00:00"
MAX_ID = 99999


def _user(uid, username, **kw):
    row = {"id": uid, "username": username, "password_hash": "x", "role": "host",
           "active": 1, "created_at": STAMP, "email": username + "@example.test"}
    row.update(kw)
    return row


def _billing(uid, status, plan="standard", **kw):
    row = {"owner_user_id": uid, "status": status, "plan": plan, "billing_interval": "month",
           "apartments_billed": 2, "updated_at": STAMP}
    row.update(kw)
    return row


def _table(name, rows):
    """One seed table. Each row lists only its own columns, so column defaults apply."""
    return {"table": name, "rows": rows}


def _seed() -> list:
    users = [
        _user(1, "admin", role="admin", display_name="Admin"),
        # 2: active, plan standard; every special character of the q filter.
        _user(2, "anna_100%", display_name="Anna_Test!", last_login_at=STAMP,
              email_verified_at=STAMP),
        _user(3, "bob", email=None),  # legacy: no billing row, no e-mail
        _user(4, "carol", active=0, signup_at=STAMP),  # unverified
        _user(5, "dan", active=0, display_name="Dan Disabled"),  # disabled
        _user(6, "eve", display_name="Eve Ending"),  # trialing, ends in 3 days
        _user(7, "frank", display_name="Frank Trial"),  # trialing, ends in 30 days
        _user(8, "gina", display_name="Gina Overdue"),
        _user(9, "hugo", display_name="Hugo Canceling"),
        _user(10, "ivo", display_name="Ivo Paused"),
        _user(11, "jana", display_name="Jana Pending"),
        _user(12, "cenek", display_name="Čeněk Novák"),  # non-ASCII name
        _user(13, "karel", email="  "),  # blank e-mail
        _user(14, "lena", active=0, signup_at=STAMP, email_verified_at=STAMP),  # disabled, verified
        _user(15, "milan", display_name="Milan Ending Edge"),  # trial ends exactly in 7 days
        _user(16, "nora", display_name="Nora Past Trial"),  # trial ended yesterday
    ]
    for i in range(101, 131):
        users.append(_user(i, f"bulk{i}", display_name=f"Bulk Host {i}"))
    billing = [
        _billing(2, "active"),
        _billing(4, "trialing", trial_ends_at="2026-11-20"),
        _billing(5, "active"),
        _billing(6, "trialing", plan="max", trial_started_at="2026-11-01",
                 trial_ends_at="2026-11-16"),
        _billing(7, "trialing", trial_started_at="2026-11-01", trial_ends_at="2026-12-13"),
        _billing(8, "overdue", plan="max", addon_ttlock=1, addon_whitelabel=1,
                 apartments_billed=7, billing_interval="year", discount_percent=15,
                 period_start="2026-10-01", period_end="2027-09-30"),
        _billing(9, "canceling", cancel_at_period_end=1, period_end="2026-12-01"),
        _billing(10, "paused"),
        _billing(11, "trial_pending", plan=None, billing_interval=None, apartments_billed=0),
        _billing(12, "active", plan="max"),
        _billing(14, "trialing", trial_ends_at="2026-11-14"),
        _billing(15, "trialing", trial_ends_at="2026-11-20"),
        _billing(16, "trialing", trial_ends_at="2026-11-12"),
    ]
    for i in range(101, 131):
        billing.append(_billing(i, "active", plan="max" if i % 2 else "standard"))
    entities = [
        {"owner_user_id": 2, "name": " Anna s.r.o. ", "ico": "12345678", "dic": "CZ12345678",
         "contact_email": " anna@firma.example.test "},
        # id 6: entity only, every other field empty
        {"owner_user_id": 6, "name": "Eve OSVC", "ico": None, "dic": "", "contact_email": None},
        # 2 more entities for host 2: ORDER BY id LIMIT 1 must take the first
        {"owner_user_id": 2, "name": "Second entity", "ico": "999", "dic": None,
         "contact_email": None},
        {"owner_user_id": 8, "name": "Gina ltd", "ico": "87654321", "dic": None,
         "contact_email": "gina@firma.example.test"},
    ]
    for entity in entities:
        entity["created_at"] = STAMP
    apartments = [
        # host 2: first active apartment has a spaced ZIP; later rows must not win
        {"owner_user_id": 2, "internal_name": "A1", "active": 1, "created_at": STAMP,
         "addr_street": "Hlavní", "addr_house_no": "12", "addr_obec": " Brno ",
         "addr_zip": "602 00"},
        {"owner_user_id": 2, "internal_name": "A2", "active": 1, "created_at": STAMP,
         "addr_street": "Druhá", "addr_house_no": "2", "addr_obec": "Praha", "addr_zip": "11000"},
        # host 2: archived and inactive apartments never count nor prefill
        {"owner_user_id": 2, "internal_name": "A3", "active": 1, "created_at": STAMP,
         "archived_at": STAMP, "addr_obec": "Ostrava"},
        {"owner_user_id": 2, "internal_name": "A4", "active": 0, "created_at": STAMP},
        # host 7: apartment only; street empty, house number only, blank city, letters-only ZIP
        {"owner_user_id": 7, "internal_name": "B1", "active": 1, "created_at": STAMP,
         "addr_street": None, "addr_house_no": "12", "addr_obec": "  ", "addr_zip": "abc"},
        # host 8: apartment with only a street and a mixed ZIP
        {"owner_user_id": 8, "internal_name": "C1", "active": 1, "created_at": STAMP,
         "addr_street": "Nová", "addr_house_no": None, "addr_obec": "Plzeň",
         "addr_zip": "30 1-00"},
        # an inactive-only host
        {"owner_user_id": 9, "internal_name": "D1", "active": 0, "created_at": STAMP},
    ]
    for i in range(101, 104):
        apartments.append({"owner_user_id": i, "internal_name": f"E{i}", "active": 1,
                           "created_at": STAMP})
    invoices = []
    for n in range(1, 13):  # 12 invoices for host 2: only the newest 10 are listed
        invoices.append({
            "owner_user_id": 2, "kind": "invoice" if n % 5 else "storno", "seq_year": 2026,
            "seq_no": n, "number": f"2026{n:04d}", "vs": f"2026{n:04d}",
            "issue_date": f"2026-{(n % 9) + 1:02d}-01", "due_date": f"2026-{(n % 9) + 1:02d}-15",
            "period_from": f"2025-{n:02d}-01", "period_to": f"2025-{n:02d}-28",
            "total_haler": 129000 + n * 100, "voided": 1 if n % 4 == 0 else 0,
            "paid_on": "2026-02-01" if n % 3 == 0 else None, "snapshot_json": "{}",
            "created_at": STAMP,
        })
    invoices.append({
        "owner_user_id": 8, "kind": "invoice", "seq_year": 2026, "seq_no": 50, "number": "20260050",
        "vs": "20260050", "issue_date": "2026-10-01", "due_date": "2026-10-15",
        "period_from": "2026-10-01", "period_to": "2026-10-31", "total_haler": 999,
        "voided": 0, "paid_on": None, "snapshot_json": "{}", "created_at": STAMP})
    audit = []
    # Host 2: 12 logins at distinct times, 5 mails and 5 billing rows; one mail
    # and one billing row share an instant (the tie breaks on detail).
    for n in range(12):
        audit.append({"at": f"2026-10-{n + 1:02d}T08:00:00+00:00", "actor": f"login-actor{n}",
                      "action": "login", "detail": f"ip{n}", "owner_user_id": 2})
    for n, (action, at) in enumerate([
        ("billing_invoice_issued", "2026-10-20T10:00:00+00:00"),
        ("billing_status_changed", "2026-10-21T10:00:00+00:00"),
        ("billing", "2026-10-21T10:00:00+00:00"),
        ("billing_plan", "2026-10-22T10:00:00+00:00"),
        ("billingx", "2026-10-23T10:00:00+00:00"),
    ]):
        audit.append({"at": at, "actor": "operator:admin" if n % 2 else "system",
                      "action": action, "detail": None if n == 2 else f"d{n}",
                      "owner_user_id": 2})
    # Not in the activity feed: other actions, other owners.
    audit.append({"at": "2026-10-25T10:00:00+00:00", "actor": "operator:admin",
                  "action": "user_disabled", "detail": "", "owner_user_id": 2})
    audit.append({"at": "2026-10-25T10:00:00+00:00", "actor": "host", "action": "mail_sent",
                  "detail": "", "owner_user_id": 2})
    audit.append({"at": "2026-10-26T10:00:00+00:00", "actor": "operator:admin",
                  "action": "login", "detail": "x", "owner_user_id": 8})
    # operator_log of host 2: 22 rows, only the newest 20 (by id) come back.
    for n in range(22):
        audit.append({"at": f"2026-10-{(n % 9) + 1:02d}T12:00:00+00:00",
                      "actor": f"operator:op{n % 3}", "action": f"op_action{n}",
                      "detail": f"detail {n}", "owner_user_id": 2,
                      "actor_user_id": 1, "impersonator_user_id": 1 if n % 7 == 0 else None})
    # Host 9: 30 logins, so the activity LIMIT 20 cuts the oldest 10.
    for n in range(30):
        audit.append({"at": f"2026-09-{n + 1:02d}T07:00:00+00:00", "actor": "h",
                      "action": "login", "detail": f"n{n}", "owner_user_id": 9})
    mails = []
    for n, (kind, at, subject) in enumerate([
        ("welcome", "2026-10-02T09:00:00+00:00", "Welcome"),
        ("invoice", "2026-10-21T10:00:00+00:00", None),
        ("reminder", "2026-10-21T10:00:00+00:00", "Please pay"),
        ("invoice", "2026-10-24T09:00:00+00:00", "Invoice 2026"),
        ("reset", "2026-10-24T10:00:00+00:00", ""),
    ]):
        mails.append({"idempotency_key": f"golden-{n}", "kind": kind, "owner_user_id": 2,
                      "subject": subject, "created_at": at, "updated_at": at})
    mails.append({"idempotency_key": "golden-other", "kind": "welcome", "owner_user_id": 8,
                  "subject": "Other owner", "created_at": STAMP, "updated_at": STAMP})
    clicks = [
        {"user_account_id": 2, "platform": "google", "gclid": "g", "clicked_at": STAMP,
         "consent_text_id": 1, "consented_at": STAMP, "created_at": STAMP},
        {"user_account_id": 2, "platform": "meta", "fbc": "f", "clicked_at": STAMP,
         "consent_text_id": 1, "consented_at": STAMP, "withdrawn_at": STAMP, "created_at": STAMP},
        {"user_account_id": 6, "platform": "meta", "fbc": "f", "clicked_at": STAMP,
         "consent_text_id": 1, "consented_at": STAMP, "created_at": STAMP},
        {"user_account_id": 7, "platform": "google", "gclid": "g", "clicked_at": STAMP,
         "consent_text_id": 1, "consented_at": STAMP, "withdrawn_at": STAMP, "created_at": STAMP},
    ]
    acceptances = []
    for uid in (1, 7):
        for doc in ("terms", "privacy", "dpa"):
            acceptances.append({"user_account_id": uid, "document": doc, "version": "{ver}",
                                "accepted_at": STAMP, "method": "clickwrap"})
    consent_texts = [{"id": 1, "version": "1", "purpose": "ads", "lang": "en", "text": "t",
                      "text_sha256": "x", "created_at": STAMP}]
    return [
        _table("user_account", users),
        _table("consent_texts", consent_texts),
        _table("billing_account", billing),
        _table("legal_entity", entities),
        _table("apartment", apartments),
        _table("platform_invoice", invoices),
        _table("audit", audit),
        _table("email_outbox", mails),
        _table("ad_click", clicks),
        _table("legal_acceptance", acceptances),
    ]


# Filter cases for customers(): q, state, plan. Cursors are added for the
# pagination cases below.
FILTERS = [
    ("all", "", "", ""),
    ("q plain", "anna", "", ""),
    ("q upper and padded", "  ANNA  ", "", ""),
    ("q percent", "100%", "", ""),
    ("q percent alone", "%", "", ""),
    ("q underscore", "_", "", ""),
    ("q underscore word", "anna_", "", ""),
    ("q bang", "!", "", ""),
    ("q bang word", "test!", "", ""),
    ("q by e-mail", "bulk110@", "", ""),
    ("q by display name", "overdue", "", ""),
    ("q non-ASCII lower-case part", "ěk nov", "", ""),
    ("q non-ASCII upper-case term", "ĚK NOV", "", ""),
    ("q non-ASCII capital letter", "čen", "", ""),
    ("q no match", "zzz-none", "", ""),
    ("q too long", "a" * 200, "", ""),
    ("state legacy", "", "legacy", ""),
    ("state unverified", "", "unverified", ""),
    ("state disabled", "", "disabled", ""),
    ("state trial_pending", "", "trial_pending", ""),
    ("state trialing", "", "trialing", ""),
    ("state active", "", "active", ""),
    ("state overdue", "", "overdue", ""),
    ("state canceling", "", "canceling", ""),
    ("state paused", "", "paused", ""),
    ("state ending", "", "ending", ""),
    ("state bogus", "", "bogus", ""),
    ("plan standard", "", "", "standard"),
    ("plan max", "", "", "max"),
    ("plan bogus", "", "", "gold"),
    ("state active plan max", "", "active", "max"),
    ("state ending plan max", "", "ending", "max"),
    ("q and state", "bulk", "active", ""),
    ("q and state and plan", "bulk1", "active", "standard"),
]

I18N_KEYS = ("auth.error.admins_only", "auth.error.own_disable",
             "customers.ops.enabled", "customers.ops.disabled")
CURSORS = ["12", "", "abc", "-5", "١٢", "1" * 19, "1" * 18, "0012", "12 ", "1_2", "0"]
HALER = [0, 1, 99, 100, 150, 999, 100000, 123456, 99999999, 123456789012, -1, -100, -150, -123456]
DETAIL_IDS = [1, 2, 3, 4, 6, 7, 8, 9, 12, 13, MAX_ID]
CONSENT_IDS = [2, 6, 7, 8, MAX_ID]


def _list_cases(admin_customers, today):
    cases = []

    def run(name, q, state, plan, after=0, before=0):
        values = admin_customers.filters(q, state, plan)
        cases.append({"name": name, "q": q, "state": state, "plan": plan,
                      "after": after, "before": before, "values": values,
                      "result": admin_customers.customers(values, after=after, before=before,
                                                          today=today)})
        return cases[-1]["result"]

    for name, q, state, plan in FILTERS:
        run(name, q, state, plan)
    page1 = run("page 1", "", "", "")
    page2 = run("page 2 after", "", "", "", after=page1["customers"][-1]["id"])
    run("page 2 back before", "", "", "", before=page2["customers"][0]["id"])
    run("before the first row", "", "", "", before=page1["customers"][0]["id"])
    run("after the last row", "", "", "", after=page2["customers"][-1]["id"])
    run("after beats nothing", "", "", "", after=0, before=0)
    run("after and before together", "", "", "", after=120, before=105)
    bulk = run("bulk active 1", "bulk", "active", "")
    run("bulk active 2", "bulk", "active", "", after=bulk["customers"][-1]["id"])
    run("bulk active before", "bulk", "active", "", before=105)
    return cases


def _toggle_phase(db, today) -> dict:
    from fastapi.testclient import TestClient

    from app import login_link
    from app.main import app

    def account_id(username):
        return db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]

    def csrf(client) -> str:
        page = client.get("/l/does-not-exist").text
        return re.search(r'<meta name="csrf-token" content="([^"]*)"', page).group(1)

    def client_for(username, lang):
        client = TestClient(app)
        client.cookies.set("ubyhost_lang", lang)
        account = db.query_one("SELECT * FROM user_account WHERE username = ?", (username,))
        token = login_link.issue(account)
        response = client.post("/login/link", data={"t": token, "_csrf": csrf(client)},
                               follow_redirects=False)
        assert response.status_code == 303 and "/login" not in response.headers["location"], \
            response.headers["location"]
        return client

    def user_state(uid):
        row = db.query_one(
            "SELECT id, username, active, session_version FROM user_account WHERE id = ?", (uid,))
        return dict(row) if row else None

    admin = client_for("admin", "en")
    admin_cs = client_for("admin", "cs")
    host = client_for("frank", "en")
    steps = []

    def step(name, client, method, path, lang, target=0):
        before = user_state(target) if target else None
        top = db.query_one("SELECT COALESCE(MAX(id), 0) AS n FROM audit")["n"]
        headers = {"X-CSRF-Token": csrf(client)}
        response = client.request(method, path, headers=headers, follow_redirects=False)
        added = [dict(r) for r in db.query(
            "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id "
            "FROM audit WHERE id > ? AND action <> 'login' ORDER BY id", (top,))]
        steps.append({
            "name": name, "method": method, "path": path, "lang": lang, "target": target,
            "role": "host" if client is host else "admin",
            "status": response.status_code,
            "location": response.headers.get("location"),
            "body": response.text if response.status_code in (403, 404) else None,
            "content_type": response.headers.get("content-type"),
            "user_before": before, "user_after": user_state(target) if target else None,
            "audit_added": added,
        })

    dan, anna, adm = account_id("dan"), account_id("anna_100%"), account_id("admin")
    step("enable a disabled host", admin, "POST", f"/admin/customers/{dan}/aktivovat", "en", dan)
    step("disable an active host in Czech", admin_cs, "POST",
         f"/admin/customers/{anna}/aktivovat", "cs", anna)
    step("enable it again in Czech", admin_cs, "POST",
         f"/admin/customers/{anna}/aktivovat", "cs", anna)
    step("own account refused", admin, "POST", f"/admin/customers/{adm}/aktivovat", "en", adm)
    step("unknown user", admin, "POST", f"/admin/customers/{MAX_ID}/aktivovat", "en")
    step("host is not an admin", host, "POST", f"/admin/customers/{dan}/aktivovat", "en", dan)
    step("funnel as admin", admin, "GET", "/admin/funnel", "en")
    step("funnel as host", host, "GET", "/admin/funnel", "en")
    return {"steps": steps}


def render() -> str:
    """Seed a fresh database, run every case, and return the golden JSON text."""
    from app import acceptance, admin_customers, billing, db, host_i18n
    from app.routes import admin_customers as routes

    db.init_db()
    versions = acceptance.current_versions()
    seed = _seed()
    for table in seed:
        for row in table["rows"]:
            if table["table"] == "legal_acceptance":
                row["version"] = versions[row["document"]]
            cols = ", ".join(row)
            marks = ", ".join("?" for _ in row)
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", list(row.values()))
    today = date.fromisoformat(TODAY)
    golden = {
        "today": TODAY,
        "versions": versions,
        "seed": seed,
        "filters_check": [
            [q, s, p, admin_customers.filters(q, s, p)]
            for q, s, p in [("  x  ", "active", "max"), ("y" * 130, "ending", "standard"),
                            ("", "nope", "nope"), ("", "legacy", "")]
        ],
        "list": _list_cases(admin_customers, today),
        "summary": admin_customers.summary(today),
        "missing_email_count": db.query_one(
            "SELECT COUNT(*) AS n FROM user_account WHERE active = 1 "
            "AND (email IS NULL OR TRIM(email) = '')")["n"],
        "detail": {str(uid): admin_customers.detail(uid) for uid in DETAIL_IDS},
        "account": {str(uid): billing.account(uid) for uid in DETAIL_IDS},
        "consent": {str(uid): dict(db.query_one(
            "SELECT (SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = ? "
            "AND c.platform = 'google' AND c.withdrawn_at IS NULL) AS google_consent, "
            "(SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = ? "
            "AND c.platform = 'meta' AND c.withdrawn_at IS NULL) AS meta_consent",
            (uid, uid))) for uid in CONSENT_IDS},
        "i18n": {lang: {k: strings[k] for k in I18N_KEYS if k in strings}
                 for lang, strings in host_i18n.STRINGS.items()},
        "cursor": [[c, routes._cursor(c)] for c in CURSORS],
        "kc": [[h, routes._kc(h)] for h in HALER],
    }
    golden["toggle"] = _toggle_phase(db, today)
    return _compact(json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True)) + "\n"


# An object or array that holds no other object or array, as json.dumps(indent=1)
# writes it. Strings never hold a raw newline, so only whitespace between tokens
# is joined.
_LEAF = re.compile(r"([\[{])\n *([^\[\]{}\n][^\[\]{}]*?)\n *([\]}])")


def _compact(text: str) -> str:
    """Write each innermost object or array on one line (a seed row, a result row)."""
    return _LEAF.sub(lambda m: m.group(1) + re.sub(r"\n *", " ", m.group(2)) + m.group(3), text)


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if OUT.read_text(encoding="utf-8") == text:
            return 0
        print(f"stale: {OUT}; run scripts/admin_customers_golden.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "admin_customers_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
~~~~

Check: `sha256sum App/scripts/admin_customers_golden.py 2>&1 | tail -30` must print `00818e5713c356389e209933da03c8317928b183f27268b19ff571d4dfcbf880`.

Create `App/tests/test_admin_customers_golden.py`:

~~~~python
"""go/internal/web/customers/*_test.go read go/internal/web/customers/testdata/admin_customers_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database and never the test session's database.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "customers" / "testdata" / "admin_customers_golden.json"


def test_admin_customers_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "admin_customers_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    committed = GOLDEN.read_bytes()
    assert committed.count(b'"audit_added"') >= 8
    assert committed.count(b'"older"') >= 40
~~~~

Check: `sha256sum App/tests/test_admin_customers_golden.py 2>&1 | tail -30` must print `ff4f93cef04063c06afe8b856fbd19c9ae142d3bb9f9eb9fff51ed5f0e8c7ee9`.

Commit `1360 step 1`.

### Step 2: generate the golden JSON

From `App/`:

```bash
.venv/bin/python scripts/admin_customers_golden.py 2>&1 | tail -1
sha256sum ../go/internal/web/customers/testdata/admin_customers_golden.json 2>&1 | tail -30
```

The first line ends `wrote .../go/internal/web/customers/testdata/admin_customers_golden.json`. The sha256 must be `d41b62be79cd0a1bf2e0fe09c4612c4a19cb5dd6bccc36e8c46d20475900371b`. Different: STOP (§8); never edit the JSON by hand. Commit `1360 step 2`.

### Step 3: checks and report

Run §6, write the report (§9), set `Status: review`, commit `1360 step 3`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `App/tests/conftest.py`, every existing file under `App/app/` and `App/scripts/`.
- `docs/context/*`, `docs/ENVIRONMENT.md`, Caddy, compose and `.env` files: no change.
- `go/internal/web/customers/testdata/admin_customers_golden.json` is written only by the golden script, never by hand.
- Never print the session secret or cookies. No push, merge or deploy.

## 6. Commands

1. From `App/`:

```bash
.venv/bin/python scripts/admin_customers_golden.py 2>&1 | tail -1 && sha256sum ../go/internal/web/customers/testdata/admin_customers_golden.json && git status --short 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_admin_customers_golden.py -q --tb=short 2>&1 | tail -30
```

Expected: sha256 still `d41b62be79cd0a1bf2e0fe09c4612c4a19cb5dd6bccc36e8c46d20475900371b` (a re-run changes nothing), `git status` shows no modified file, pytest `1 passed`.

2. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` ends `context lint: OK`.

## 7. Acceptance

- [ ] The 3 files exist with the sha256 values in §4.
- [ ] Golden re-run leaves the JSON unchanged; `test_admin_customers_golden.py` passes.
- [ ] Context lint OK.
- [ ] `git diff --stat <start commit>` lists only the §3 paths.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 differs twice for the same file;
- a test fails twice;
- Postgres does not start, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1360-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat <start commit>`; `<start commit>` is the commit you started from: `git rev-parse HEAD` before step 1, write it down).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/scripts/admin_customers_golden.py`: the seed and the cases (it is the contract the Go code must meet); the toggle phase runs last so it cannot change the data cases.

## Owner steps

None. Next: brief 1362 on the same branch.
