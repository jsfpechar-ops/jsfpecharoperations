"""Write go/internal/payments/testdata/booking_webhook/golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/booking_webhook_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED, sends every
event in EVENTS through stripe_connect.process_event (the dedupe, then
booking_webhook.handle) and records whether each call returned or raised, the
Stripe refund requests, and the rows afterwards. Stripe is faked at
stripe_connect._client, so the call guard and the monthly call count still run.
booking_invoice.ensure is replaced by a no-op: the Go port does not issue the
invoice (brief 1350, known gap). go/internal/payments/booking_webhook_test.go
seeds PostgreSQL from the same file, runs the Go handler and compares.
App/tests/test_go_booking_webhook_golden.py fails when this file or
go/internal/payments/booking_i18n.json is stale.

Timestamps the run writes are not comparable: a timestamp column records
"seed" when it still holds the seeded value, "run" when the run wrote it, and
null when it is empty.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
GO_PAYMENTS = APP.parent / "go" / "internal" / "payments"
OUT = GO_PAYMENTS / "testdata" / "booking_webhook" / "golden.json"
I18N_OUT = GO_PAYMENTS / "booking_i18n.json"

STAMP = "2026-09-01T00:00:00+00:00"
SECRET = "golden-secret-key-not-for-real-use"
BASE_URL = "https://golden.example.test"

# The host_i18n keys the Go handler reads, in cs and en only.
I18N_KEYS = [
    "pp.book.policy.flexible",
    "pp.book.policy.moderate",
    "pp.book.policy.non_refundable",
    "site_booking.mail.clash_subject",
    "site_booking.mail.clash_text",
    "site_booking.mail.guest_manage",
    "site_booking.mail.guest_manage_direct",
    "site_booking.mail.guest_register",
    "site_booking.mail.guest_subject",
    "site_booking.mail.guest_text",
    "site_booking.mail.guest_text_direct",
    "site_booking.mail.host_clash_subject",
    "site_booking.mail.host_clash_text",
    "site_booking.mail.host_subject",
    "site_booking.mail.host_text",
    "site_booking.mail.host_text_direct",
]
I18N_LANGS = ["cs", "en"]


def _booking(bid, apt, owner, status, dfrom, dto, *, lang="cs", email="guest@example.test",
             name="Test Guest", hold=None, pay="stripe", policy="flexible", total=4000):
    return [bid, apt, owner, hold, status, dfrom, dto, 2, name, email, lang, 2, 1800, total,
            policy, "v1", f"cs_{bid}", pay, STAMP, STAMP]


# Apartment 10 (owner 1): slug, booking page, host mail, Stripe account.
# Apartment 11 (owner 1): no permalink token (no registration link), no page
# slug (manage link uses "x"), an active stay 2027-03-10..15 for clashes.
# Apartment 12 (owner 2): host entity without mail, no Stripe account, an
# active stay 2027-03-10..15.
SEED = [
    {"table": "user_account",
     "columns": ["id", "username", "password_hash", "role", "created_at"],
     "rows": [[1, "host1@example.test", "x", "host", STAMP],
              [2, "host2@example.test", "x", "host", STAMP]]},
    {"table": "legal_entity",
     "columns": ["id", "owner_user_id", "name", "contact_email", "created_at"],
     "rows": [[100, 1, "Host One", "Host.One@Example.test", STAMP],
              [101, 2, "Host Two", None, STAMP]]},
    {"table": "apartment",
     "columns": ["id", "owner_user_id", "legal_entity_id", "internal_name", "permalink_token", "created_at"],
     "rows": [[10, 1, 100, "Chata u lesa", "tok-ten-aaaaaaaaaaaa", STAMP],
              [11, 1, 100, "Byt Praha", None, STAMP],
              [12, 2, 101, "Apartmán Brno", "tok-twelve-bbbbbbbbbb", STAMP]]},
    {"table": "apartment_slug",
     "columns": ["slug", "apartment_id", "is_current", "created_at"],
     "rows": [["chata-u-lesa-k7m2", 10, 1, STAMP],
              ["apartman-brno-q9z4", 12, 1, STAMP]]},
    {"table": "property_slug",
     "columns": ["id", "apartment_id", "slug", "published", "created_at", "updated_at"],
     "rows": [[1, 10, "chata-u-lesa", 1, STAMP, STAMP],
              [2, 12, "apartman-brno", 1, STAMP, STAMP]]},
    {"table": "stripe_account",
     "columns": ["id", "owner_user_id", "stripe_account_id", "mode", "onboarding_state",
                 "charges_enabled", "payouts_enabled", "created_at", "updated_at"],
     "rows": [[1, 1, "acct_golden1", "test", "complete", 1, 1, STAMP, STAMP]]},
    {"table": "reservation",
     "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to", "status",
                 "created_at", "updated_at"],
     "rows": [[50, 11, "ical", "airbnb-1", "2027-03-10", "2027-03-15", "active", STAMP, STAMP],
              [51, 12, "ical", "airbnb-2", "2027-03-10", "2027-03-15", "active", STAMP, STAMP]]},
    {"table": "booking_hold",
     "columns": ["id", "apartment_id", "date_from", "date_to", "expires_at", "created_at"],
     "rows": [[201, 10, "2027-01-01", "2027-01-05", STAMP, STAMP],
              [204, 11, "2027-03-12", "2027-03-14", STAMP, STAMP],
              [205, 12, "2027-03-12", "2027-03-14", STAMP, STAMP],
              [208, 10, "2027-07-01", "2027-07-03", STAMP, STAMP],
              [210, 10, "2027-09-01", "2027-09-03", STAMP, STAMP]]},
    {"table": "site_booking",
     "columns": ["id", "apartment_id", "owner_user_id", "hold_id", "status", "date_from", "date_to",
                 "guests", "guest_name", "guest_email", "lang", "nights", "nightly_czk", "total_czk",
                 "cancellation_policy", "terms_version", "stripe_session_id", "pay_method",
                 "created_at", "updated_at"],
     "rows": [
         # 1 cs card, paid; then replayed, then a second paid event, then expired: no-ops.
         _booking(1, 10, 1, "pending", "2027-01-01", "2027-01-05", hold=201),
         # 2 en, unpaid completed (pending bank method), then async succeeded.
         _booking(2, 10, 1, "pending", "2027-02-01", "2027-02-03", lang="en", policy="moderate"),
         # 3 direct pay method, no guest mail address: host mail only.
         _booking(3, 10, 1, "pending", "2027-04-01", "2027-04-04", email=None, pay="direct"),
         # 4 en clash: refunded on acct_golden1, mails.
         _booking(4, 11, 1, "pending", "2027-03-12", "2027-03-14", lang="en", hold=204),
         # 5 clash, owner 2 has no Stripe account: raises, stays pending.
         _booking(5, 12, 2, "pending", "2027-03-12", "2027-03-14", hold=205),
         # 6 clash, Stripe answers an error: raises, stays pending; the redelivery
         # after Stripe recovered refunds it.
         _booking(6, 11, 1, "pending", "2027-03-11", "2027-03-13"),
         # 7 clash, the session has no payment intent: raises.
         _booking(7, 11, 1, "pending", "2027-03-13", "2027-03-16"),
         # 8 expired session; 9 async payment failed.
         _booking(8, 10, 1, "pending", "2027-07-01", "2027-07-03", hold=208),
         _booking(9, 10, 1, "pending", "2027-08-01", "2027-08-03"),
         # 10 already expired, then paid late: confirmed. Unknown language -> cs.
         _booking(10, 10, 1, "expired", "2027-09-01", "2027-09-03", hold=210, lang="de",
                  policy="non_refundable"),
         # 11 owner 2: host has no mail address, guest mail with empty reply_to.
         _booking(11, 12, 2, "pending", "2027-06-01", "2027-06-02", lang="en"),
         # 12 already cancelled: an expired event changes nothing.
         _booking(12, 10, 1, "cancelled", "2027-10-01", "2027-10-03"),
     ]},
]


def _event(eid, etype, booking_id, *, payment_status="paid", intent="auto", session=None):
    obj = {
        "id": session or f"cs_{booking_id}",
        "object": "checkout.session",
        "payment_status": payment_status,
        "metadata": {"site_booking_id": str(booking_id)},
    }
    if intent == "auto":
        obj["payment_intent"] = f"pi_{booking_id}"
    elif intent is not None:
        obj["payment_intent"] = intent
    return {"id": eid, "object": "event", "type": etype, "data": {"object": obj}}


DONE = "checkout.session.completed"
ASYNC_OK = "checkout.session.async_payment_succeeded"
EXPIRED = "checkout.session.expired"
ASYNC_FAIL = "checkout.session.async_payment_failed"

EVENTS = [
    _event("evt_g01", DONE, 1),
    _event("evt_g01", DONE, 1),
    _event("evt_g02", ASYNC_OK, 1),
    _event("evt_g03", DONE, 2, payment_status="unpaid", intent=None),
    _event("evt_g04", ASYNC_OK, 2),
    _event("evt_g05", DONE, 3),
    _event("evt_g06", DONE, 4),
    _event("evt_g07", DONE, 5),
    _event("evt_g08", DONE, 6, intent="pi_fail"),
    _event("evt_g09", DONE, 7, intent=None),
    _event("evt_g10", EXPIRED, 8, payment_status="unpaid", intent=None),
    _event("evt_g11", ASYNC_FAIL, 9, payment_status="unpaid", intent=None),
    _event("evt_g12", DONE, 10),
    _event("evt_g13", DONE, 11),
    _event("evt_g14", EXPIRED, 12, payment_status="unpaid", intent=None),
    _event("evt_g15", EXPIRED, 1, payment_status="unpaid", intent=None),
    _event("evt_g16", DONE, 999, session="cs_unknown"),
    _event("evt_g17", DONE, 4),
    # evt_g08 redelivered after Stripe recovered: one refund, one set of clash mails.
    _event("evt_g08", DONE, 6, intent="pi_fail"),
]


class _FakeRefunds:
    """pi_fail raises on its first call only: Stripe then recovers."""

    def __init__(self, calls):
        self.calls = calls
        self.failed = 0

    def create(self, params=None, options=None):
        params = params or {}
        options = options or {}
        self.calls.append({
            "payment_intent": params.get("payment_intent"),
            "metadata_site_booking_id": (params.get("metadata") or {}).get("site_booking_id"),
            "stripe_account": options.get("stripe_account"),
            "idempotency_key": options.get("idempotency_key"),
        })
        if params.get("payment_intent") == "pi_fail" and self.failed == 0:
            self.failed += 1
            raise RuntimeError("fake Stripe error")
        return {"id": f"re_{len(self.calls)}", "status": "succeeded"}


class _FakeClient:
    def __init__(self, calls):
        self.v1 = type("V1", (), {})()
        self.v1.refunds = _FakeRefunds(calls)


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _ts(value):
    if value is None:
        return None
    return "seed" if value == STAMP else "run"


def _rows(db, sql, ts_cols=()):
    out = []
    for row in db.query(sql):
        item = dict(row)
        for col in ts_cols:
            item[col] = _ts(item[col])
        out.append(item)
    return out


def _snapshot(db) -> dict:
    return {
        "site_booking": _rows(
            db,
            "SELECT id, status, reservation_id, hold_id, stripe_payment_intent_id, refunded_czk,"
            " paid_at, updated_at FROM site_booking ORDER BY id",
            ("paid_at", "updated_at")),
        "reservation": _rows(
            db,
            "SELECT id, apartment_id, source, uid, date_from, date_to, summary,"
            " expected_guests_override, guest_email, status, created_at, updated_at"
            " FROM reservation ORDER BY id",
            ("created_at", "updated_at")),
        "booking_hold": _rows(db, "SELECT id FROM booking_hold ORDER BY id"),
        "email_outbox": _rows(
            db,
            "SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email,"
            " cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at"
            " FROM email_outbox ORDER BY id",
            ("next_attempt_at", "created_at", "updated_at")),
        "audit": _rows(
            db,
            "SELECT at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id"
            " FROM audit ORDER BY id",
            ("at",)),
        "stripe_webhook_event": _rows(
            db,
            "SELECT event_id, event_type, mode, created_at FROM stripe_webhook_event ORDER BY id",
            ("created_at",)),
        "stripe_calls": sum(int(r["calls"]) for r in db.query(
            "SELECT calls FROM lock_api_usage WHERE provider = 'stripe'")),
    }


def render_i18n() -> str:
    from app import host_i18n

    catalog = {lang: {k: host_i18n.STRINGS[lang][k] for k in I18N_KEYS if k in host_i18n.STRINGS[lang]}
               for lang in I18N_LANGS}
    return json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def render() -> str:
    """Seed a fresh database, send the events, and return the golden JSON text."""
    from app import booking_invoice, config, db, stripe_connect

    saved = {name: getattr(config, name) for name in (
        "STRIPE_MODE", "STRIPE_SECRET_KEY", "STRIPE_MONTHLY_API_CALLS", "MAIL_BACKEND",
        "PUBLIC_BASE_URL", "_SECRET_KEY")}
    saved_client = stripe_connect._client
    saved_ensure = booking_invoice.ensure
    calls: list = []
    try:
        config.STRIPE_MODE = "test"
        config.STRIPE_SECRET_KEY = "sk_test_golden"
        config.STRIPE_MONTHLY_API_CALLS = 50000
        config.MAIL_BACKEND = "console"
        config.PUBLIC_BASE_URL = BASE_URL
        config._SECRET_KEY = SECRET
        fake = _FakeClient(calls)
        stripe_connect._client = lambda: fake
        booking_invoice.ensure = lambda booking_id: None

        db.init_db()
        _seed(db)
        results = []
        for event in EVENTS:
            try:
                stripe_connect.process_event(json.loads(json.dumps(event)))
                results.append("ok")
            except Exception:  # noqa: BLE001 - the route answers 500, Stripe retries
                results.append("error")
        golden = {
            "stamp": STAMP,
            "secret": SECRET,
            "base_url": BASE_URL,
            "seed": SEED,
            "events": EVENTS,
            "results": results,
            "refunds": calls,
            "after": _snapshot(db),
        }
    finally:
        for name, value in saved.items():
            setattr(config, name, value)
        stripe_connect._client = saved_client
        booking_invoice.ensure = saved_ensure
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    I18N_OUT.write_text(render_i18n(), encoding="utf-8")
    print(f"wrote {OUT} and {I18N_OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "booking_webhook_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", SECRET)
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
