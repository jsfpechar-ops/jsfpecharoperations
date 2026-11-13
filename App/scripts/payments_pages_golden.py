"""Write go/internal/payments/pages/testdata/golden.json from the Python routes (brief 1353).

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/payments_pages_golden.py          write the file
    .venv/bin/python scripts/payments_pages_golden.py --check  exit 1 when it is stale

It seeds FIXTURE into a throwaway SQLite database, calls each CASE on the real
FastAPI app with the TestClient (a signed session cookie per host, a valid CSRF
token on POSTs, the language cookie of the case) and records the status, the
Location header and, for a page, summary(): the visible text, the form fields
and the links of the page body (the host_page "ui-page" block; the shell is
brief 1380's golden). WRITES run in order on the same database and also record
the rows they change (the payment_services setting, the consent audit rows).
go/internal/payments/pages/pages_test.go seeds the same FIXTURE into Postgres,
runs the same cases through the Go handlers and compares after the same
summary(); keep the two summary functions in step.

Stripe: payment_links.send is replaced by LINK_RESULTS (no network), the Go
test gives the same answers through a fake LinkSender.
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
OUT = APP.parent / "go" / "internal" / "payments" / "pages" / "testdata" / "golden.json"
_TMP = Path(tempfile.mkdtemp(prefix="ubyhost-paypages-"))

SECRET = "payments-pages-golden-secret-0123456789abcdef"
PINNED_ENV = {
    "UBYHOST_DATA_DIR": str(_TMP),
    "UBYHOST_DB": str(_TMP / "golden.db"),
    "UBYHOST_SECRET_KEY": SECRET,
    "UBYHOST_ENABLE_SCHEDULER": "0",
    "UBYHOST_ICAL_OPEN_SYNC_MINUTES": "0",
    "UBYHOST_BOOTSTRAP_ADMIN": "0",
    "UBYHOST_UBYPORT_ENV": "mock",
    "UBYHOST_DEPLOYMENT": "local",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_PUBLIC_BASE_URL": "http://testserver",
    "UBYHOST_TERMS_VERSION": "t1",
    "UBYHOST_PRIVACY_VERSION": "p1",
    "UBYHOST_DPA_VERSION": "d1",
    "UBYHOST_STRIPE_MODE": "test",
}

TS = "2026-11-01T08:00:00+00:00"


def _services(n: int) -> str:
    return json.dumps(
        [{"id": f"svc-{i:02d}", "name": f"Extra {i}", "amount_czk": 100 + i} for i in range(n)],
        ensure_ascii=False,
    )


# Rows as (table, {column: value}). Postgres-portable values only.
FIXTURE = [
    ("user_account", {"id": uid, "username": name, "password_hash": "x", "created_at": TS,
                      "role": "host", "active": 1, "session_version": 0})
    for uid, name in [(1, "pay-new"), (2, "pay-pending"), (3, "pay-complete"), (4, "pay-rejected"), (5, "pay-details")]
] + [
    ("legal_acceptance", {"id": 100 + uid * 3 + i, "user_account_id": uid, "document": doc, "version": ver,
                          "accepted_at": TS, "method": "clickwrap"})
    for uid in range(1, 6) for i, (doc, ver) in enumerate([("terms", "t1"), ("privacy", "p1"), ("dpa", "d1")])
] + [
    ("audit", {"id": 900 + uid, "at": TS, "actor": "seed", "action": "payments_terms_accepted",
               "detail": "version=2026-11-01", "owner_user_id": uid})
    for uid in (2, 3, 5)
] + [
    ("legal_entity", {"id": 21, "owner_user_id": 2, "name": "Penzion Růže s.r.o.", "business_type": "company",
                      "created_at": TS, "contact_email": "host2@example.test", "vat_status": "none",
                      "invoice_due_days": 14, "iban": "CZ6508000000192000145399", "bank_account": None}),
    ("legal_entity", {"id": 31, "owner_user_id": 3, "name": "Jana <Nová> & spol.", "business_type": "company",
                      "created_at": TS, "contact_email": None, "vat_status": "none",
                      "invoice_due_days": 14, "iban": None, "bank_account": None}),
    ("legal_entity", {"id": 51, "owner_user_id": 5, "name": "  ", "business_type": "company",
                      "created_at": TS, "contact_email": "five@example.test", "vat_status": "none",
                      "invoice_due_days": 14, "iban": None, "bank_account": "19-2000145399/0800"}),
    ("audit", {"id": 910, "at": TS, "actor": "seed", "action": "payments_terms_accepted",
               "detail": "version=2025-01-01", "owner_user_id": 1}),
    ("stripe_account", {"owner_user_id": 2, "stripe_account_id": "acct_pending", "mode": "test",
                        "onboarding_state": "pending", "charges_enabled": 0, "payouts_enabled": 0,
                        "created_at": TS, "updated_at": TS}),
    ("stripe_account", {"owner_user_id": 3, "stripe_account_id": "acct_complete", "mode": "test",
                        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
                        "created_at": TS, "updated_at": TS}),
    ("stripe_account", {"owner_user_id": 4, "stripe_account_id": "acct_rejected", "mode": "test",
                        "onboarding_state": "rejected", "charges_enabled": 0, "payouts_enabled": 0,
                        "created_at": TS, "updated_at": TS}),
    ("stripe_account", {"owner_user_id": 5, "stripe_account_id": "acct_live_only", "mode": "live",
                        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
                        "created_at": TS, "updated_at": TS}),
    ("apartment", {"id": 41, "legal_entity_id": 21, "owner_user_id": 2, "internal_name": "Byt Růže", "created_at": TS}),
    ("apartment", {"id": 42, "legal_entity_id": None, "owner_user_id": 1, "internal_name": "Other flat", "created_at": TS}),
    ("reservation", {"id": 61, "apartment_id": 41, "source": "ical", "uid": "r61", "date_from": "2026-12-01",
                     "date_to": "2026-12-04", "summary": "Novák", "status": "active", "guest_email": " guest61@example.test ",
                     "created_at": TS, "updated_at": TS}),
    ("reservation", {"id": 62, "apartment_id": 41, "source": "ical", "uid": "r62", "date_from": "2026-12-10",
                     "date_to": "2026-12-12", "summary": "  ", "status": "active", "guest_email": None,
                     "created_at": TS, "updated_at": TS}),
    ("reservation", {"id": 63, "apartment_id": 41, "source": "ical", "uid": "r63", "date_from": "2026-12-20",
                     "date_to": "2026-12-22", "summary": "Cancelled one", "status": "cancelled", "guest_email": None,
                     "created_at": TS, "updated_at": TS}),
    ("reservation", {"id": 64, "apartment_id": 42, "source": "ical", "uid": "r64", "date_from": "2026-12-01",
                     "date_to": "2026-12-02", "summary": "Not yours", "status": "active", "guest_email": "x@example.test",
                     "created_at": TS, "updated_at": TS}),
    ("settings", {"key": "payment_services:2", "value": json.dumps(
        [{"id": "svc-a", "name": "Úklid navíc", "amount_czk": 500},
         {"id": "svc-b", "name": 'Late <checkout> & "more"', "amount_czk": 300, "note": "kept"},
         {"id": "", "name": "no id, dropped"}, "not a dict"], ensure_ascii=False)}),
    ("settings", {"key": "payment_services:3", "value": _services(20)}),
    ("settings", {"key": "payment_services:5", "value": "{not json"}),
]


def _req(rid, owner, reason, amount, rail, status, created, *, email=None, note=None, stay=None, vs=None, link=None):
    return ("payment_request", {
        "id": rid, "owner_user_id": owner, "reservation_id": stay, "reason": reason, "amount_czk": amount,
        "currency": "CZK", "rail": rail, "status": status, "guest_email": email, "guest_note": note,
        "variable_symbol": vs, "stripe_payment_link_id": link, "expires_at": "2026-12-31",
        "created_at": created, "updated_at": created,
    })


FIXTURE += [
    _req(71, 2, "repair", 250, "card", "draft", "2026-11-05T10:00:00+00:00", email="g@example.test"),
    _req(72, 2, "cleaning", 90, "card", "sent", "2026-11-04T10:00:00+00:00", link="plink_72"),
    _req(73, 2, "damage", 300, "qr", "paid", "2026-11-03T10:00:00+00:00", vs="2600073"),
    _req(74, 2, "late_checkout", 70, "qr", "draft", "2026-11-03T10:00:00+00:00", email="  "),
    _req(75, 2, "custom", 80, "qr", "draft", "2026-11-02T10:00:00+00:00", note="Kolo <půjčení>", stay=61, email="g@example.test"),
    _req(76, 2, "custom", 85, "card", "expired", "2026-11-01T10:00:00+00:00", note=""),
    _req(77, 2, "extra_guest", 60, "card", "awaiting_payment", "2026-10-30T10:00:00+00:00", email="  g2@example.test ", link="plink_77"),
    _req(78, 2, "repair", 55, "card", "draft", "2026-10-29T10:00:00+00:00"),
    _req(81, 3, "extra_guest", 400, "card", "awaiting_payment", "2026-11-06T10:00:00+00:00", email="guest&co@example.test", link="plink_81"),
    _req(82, 3, "repair", 120, "card", "paid", "2026-11-05T10:00:00+00:00", link="plink_82"),
    _req(83, 3, "cleaning", 99, "qr", "sent", "2026-11-05T10:00:00+00:00"),
]

# payment_links.send answers by request id; anything else returns "".
LINK_RESULTS = {
    72: "https://buy.stripe.com/test_72?x=1&y=2",
    77: "https://buy.stripe.com/test_77",
    81: "STRIPE_OFF",
    82: "https://buy.stripe.com/test_82",
}

# (name, method, path, host id, lang, stripe mode, form)
CASES = [
    ("overview_off_en", "GET", "/payments", 2, "en", "off", None),
    ("overview_new_en", "GET", "/payments", 1, "en", "test", None),
    ("overview_pending_cs", "GET", "/payments", 2, "cs", "test", None),
    ("overview_pending_en", "GET", "/payments", 2, "en", "test", None),
    ("overview_complete_en", "GET", "/payments", 3, "en", "test", None),
    ("overview_complete_cs", "GET", "/payments?lang=cs", 3, "en", "test", None),
    ("overview_rejected_cs", "GET", "/payments", 4, "cs", "test", None),
    ("overview_details_en", "GET", "/payments", 5, "en", "test", None),
    ("overview_redirect_service", "GET", "/payments?service=svc-a&x=%C3%BA", 2, "cs", "test", None),
    ("overview_redirect_stay", "GET", "/payments?reservation_id=", 2, "cs", "test", None),
    ("signed_out", "GET", "/payments", 0, "en", "test", None),
    ("new_plain_cs", "GET", "/payments/new", 2, "cs", "test", None),
    ("new_prefill_en", "GET", "/payments/new?reservation_id=61&service=svc-b", 2, "en", "test", None),
    ("new_prefill_cs", "GET", "/payments/new?reservation_id=62&service=svc-a", 2, "cs", "test", None),
    ("new_other_stay_en", "GET", "/payments/new?reservation_id=64&service=nope", 2, "en", "test", None),
    ("new_no_bank_en", "GET", "/payments/new", 1, "en", "test", None),
    ("new_bank_account_cs", "GET", "/payments/new?reservation_id=x1", 5, "cs", "off", None),
    ("share_ok_cs", "GET", "/payments/requests/72/share", 2, "cs", "test", None),
    ("share_ok_en", "GET", "/payments/requests/77/share", 2, "en", "test", None),
    ("share_no_link_id", "GET", "/payments/requests/71/share", 2, "cs", "test", None),
    ("share_paid", "GET", "/payments/requests/82/share", 3, "en", "test", None),
    ("share_stripe_off", "GET", "/payments/requests/81/share", 3, "en", "test", None),
    ("share_other_owner", "GET", "/payments/requests/72/share", 3, "en", "test", None),
    ("share_qr", "GET", "/payments/requests/83/share", 3, "cs", "test", None),
    ("share_missing", "GET", "/payments/requests/9999/share", 3, "cs", "test", None),
    ("consent_cs", "GET", "/payments/consent", 1, "cs", "test", None),
    ("consent_en", "GET", "/payments/consent", 1, "en", "live", None),
    ("consent_off", "GET", "/payments/consent", 1, "en", "off", None),
]

# Run in order on one database after CASES; each records the rows after it.
# New services go to host 4, whose page hides them: their ids are random.
WRITES = [
    ("svc_add_bad_amount", "POST", "/payments/services", 4, "en", "test", {"name": "Bike", "amount_czk": "12a"}),
    ("svc_add_zero", "POST", "/payments/services", 4, "cs", "test", {"name": "Bike", "amount_czk": "0"}),
    ("svc_add_too_much", "POST", "/payments/services", 4, "en", "test", {"name": "Bike", "amount_czk": "1000001"}),
    ("svc_add_blank_name", "POST", "/payments/services", 4, "en", "test", {"name": "  \t ", "amount_czk": "5"}),
    ("svc_add_ok", "POST", "/payments/services", 4, "cs", "test",
     {"name": "  Kolo   <na> \t den & \"noc\" " + "x" * 70, "amount_czk": " 150 "}),
    ("svc_add_second", "POST", "/payments/services", 4, "en", "off", {"name": "Parkování", "amount_czk": "1000000"}),
    ("svc_add_full", "POST", "/payments/services", 3, "en", "test", {"name": "One more", "amount_czk": "10"}),
    ("svc_add_keeps_extra_keys", "POST", "/payments/services", 2, "en", "test", {"name": "Snídaně", "amount_czk": "250"}),
    ("svc_add_bad_json", "POST", "/payments/services", 5, "en", "test", {"name": "Fresh", "amount_czk": "1"}),
    ("svc_delete_unknown", "POST", "/payments/services/nope/delete", 2, "cs", "test", {}),
    ("svc_delete_ok", "POST", "/payments/services/svc-b/delete", 2, "en", "test", {}),
    ("svc_delete_other_owner", "POST", "/payments/services/svc-a/delete", 3, "en", "test", {}),
    ("consent_post_off", "POST", "/payments/consent", 1, "en", "off", {"agree": "1"}),
    ("consent_post_no_tick", "POST", "/payments/consent", 1, "cs", "test", {"agree": "yes"}),
    ("consent_post_ok", "POST", "/payments/consent", 1, "en", "test", {"agree": "1"}),
    ("consent_post_again", "POST", "/payments/consent", 1, "en", "test", {"agree": "1"}),
    ("consent_after_overview_en", "GET", "/payments", 1, "en", "test", None),
]

# ---- summary: keep in step with summarise() in pages_test.go ---------------

_DROP = [re.compile(rf"<{tag}\b.*?</{tag}>", re.S | re.I) for tag in ("script", "style", "svg")]
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
_ATTR = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+)))?")
_FIELD_ATTRS = ("name", "type", "value", "method", "action", "id", "for", "role")
_FLAGS = ("checked", "selected", "disabled", "required", "readonly", "open", "hidden")


def body_region(page: str) -> str:
    start = page.find('<div class="ui-page"')
    end = page.find('<div class="page-skeleton"', start)
    if start < 0 or end < 0:
        return ""
    return page[start:end]


def summary(page: str) -> dict:
    region = body_region(page)
    for drop in _DROP:
        region = drop.sub(" ", region)
    region = _COMMENT.sub(" ", region)
    fields, links = [], []
    for m in _TAG.finditer(region):
        if m.group(1):
            continue
        tag = m.group(2).lower()
        attrs = {}
        for a in _ATTR.finditer(m.group(3)):
            value = a.group(2) if a.group(2) is not None else a.group(3) if a.group(3) is not None else a.group(4)
            attrs[a.group(1).lower()] = html.unescape(value) if value is not None else None
        if attrs.get("name") == "_csrf":
            attrs["value"] = "CSRF"
        if tag == "a" and "href" in attrs:
            links.append(attrs["href"] or "")
        if tag in ("form", "input", "select", "option", "textarea", "button", "details", "label"):
            parts = [tag]
            parts += [f"{k}={attrs[k]}" for k in _FIELD_ATTRS if attrs.get(k) is not None]
            parts += [k for k in _FLAGS if k in attrs]
            fields.append(" ".join(parts))
    text = html.unescape(_TAG.sub(" ", region))
    return {"text": " ".join(text.split()), "fields": fields, "links": links}


# ---- run ---------------------------------------------------------------------


def main() -> int:
    for key in ("UBYHOST_DATABASE_URL", "UBYHOST_TEST_DATABASE_URL"):
        os.environ.pop(key, None)
    os.environ.update(PINNED_ENV)
    sys.path.insert(0, str(APP))
    from fastapi.testclient import TestClient

    from app import auth, config, db, payment_links, security, stripe_connect
    from app.main import app

    db.init_db()
    for table, row in FIXTURE:
        db.insert(table, row)

    def fake_send(request_id):
        result = LINK_RESULTS.get(int(request_id), "")
        if result == "STRIPE_OFF":
            raise stripe_connect.StripeOff("golden")
        return result

    payment_links.send = fake_send

    def call(case):
        name, method, path, uid, lang, mode, form = case
        config.STRIPE_MODE = mode
        client = TestClient(app, base_url="http://testserver")
        client.cookies.set("ubyhost_lang", lang)
        if uid:
            client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(uid, 0))
        if method == "GET":
            response = client.get(path, follow_redirects=False)
        else:
            nonce = "golden-csrf-nonce"
            client.cookies.set(security.CSRF_COOKIE, nonce)
            token = security._csrf_serializer().dumps({"nonce": security._nonce_binding(nonce)})
            response = client.request(method, path, data={**form, "_csrf": token}, follow_redirects=False)
        out = {"name": name, "method": method, "path": path, "uid": uid, "lang": lang, "mode": mode,
               "form": form, "status": response.status_code, "location": response.headers.get("location", "")}
        if response.status_code == 200:
            out["page"] = summary(response.text)
            out["title"] = re.search(r"<title>(.*?)</title>", response.text, re.S).group(1).strip()
        elif response.status_code != 303:
            out["body"] = response.text
        return out

    def rows():
        svc = {r["key"]: re.sub(r'"id": "[0-9a-f]{8}"', '"id": "<new>"', r["value"] or "")
               for r in db.query("SELECT key, value FROM settings WHERE key LIKE 'payment_services:%' ORDER BY key")}
        audit = [dict(r) for r in db.query(
            "SELECT actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit"
            " WHERE action = 'payments_terms_accepted' ORDER BY owner_user_id, id")]
        return {"settings": svc, "audit": audit}

    cases = [call(c) for c in CASES]
    writes = []
    for c in WRITES:
        out = call(c)
        out["rows"] = rows()
        writes.append(out)
    env = {k: v for k, v in PINNED_ENV.items() if k not in ("UBYHOST_DATA_DIR", "UBYHOST_DB")}
    data = {"secret": SECRET, "env": env, "fixture": [{"table": t, "row": r} for t, r in FIXTURE],
            "link_results": {str(k): v for k, v in LINK_RESULTS.items()}, "cases": cases, "writes": writes}
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"stale: {OUT.relative_to(APP.parent)}")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(APP.parent)}: {len(cases)} cases, {len(writes)} writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
