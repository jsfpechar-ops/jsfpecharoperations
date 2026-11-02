# 0816: Booking site payment webhook (confirm, or refund a double booking)

Status: todo
Depends on: 0815 | Base commit: tip of task/0815-booking-site-checkout | Branch: task/0816-booking-site-webhook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When Stripe reports a paid booking session, re-check the dates under a lock and either create the stay (`reservation.source = 'site'`) and mail the guest and the host, or, if the nights were sold meanwhile, refund the guest in full automatically and tell both (owner decision 1 Nov: host absorbs the Stripe fee). An expired or failed session releases the hold. Plan: `docs/plans/booking-site-v1.md`.

## 2. Context

- `stripe_connect.process_event` records the event id only after the handler returns, so a handler that raises is retried by Stripe. Handlers must be idempotent.
- Booking sessions carry `metadata.site_booking_id` (0815). Payment-link sessions carry `payment_link`; both arrive as `checkout.session.completed`.
- Stripe calls: `stripe_connect._api()`, connected account in `options`. Refund: `api.v1.refunds.create(params=..., options={"stripe_account": ..., "idempotency_key": ...})`.
- Inside `with db.immediate() as cur:` use only `cur.execute`; `db.lock_key(cur, "booking_site_dates", apartment_id)` is the same key 0815's hold uses. `reservation` has no encrypted columns, so a raw INSERT is fine.
- Mail: `mail.enqueue(kind=, idempotency_key=, to_email=, subject=, payload={"text", "lang", "reply_to"}, reservation_id=, apartment_id=, owner_user_id=)`. Every kind is in `KINDS` and in exactly one of `GUEST_KINDS` / `HOST_KINDS` (`test_claim_mail.py` checks). The host's address and the guest reply-to are `mail_notify._entity_contact_email(apartment["legal_entity_id"])`.
- Guest registration link: `f"{config.PUBLIC_BASE_URL.rstrip('/')}/l/{guest_slug.link_key(apartment)}/{reservation_id}"` (same as `claim._stay_link`).
- Copy lives in `host_i18n.py` (EN and CS must carry the same keys; `%(name)s` placeholders; `host_i18n.translate(lang, key, **kw)`).

Excerpt `App/app/stripe_connect.py` (end of `process_event`, verbatim):

```python
    etype = event.get("type")
    if etype == "account.updated":
        mirror_by_account_id(dict(event["data"]["object"]), config.STRIPE_MODE)
    elif etype in payment_links.PAID_EVENTS:
        payment_links.on_paid(event)
    _record_event(event)
```

Excerpt `App/app/mail.py` (start of `KINDS`, verbatim):

```python
KINDS = (
    "claim",
    "claim_resend",
    "payment_request",
    "reminder_guest",
    "reminder_host",
```

Excerpt `App/app/mail.py` (end of `GUEST_KINDS`, verbatim):

```python
    "invoice_issued",
    "door_code",
)
```

Excerpt `App/app/mail.py` (start of `HOST_KINDS`, verbatim):

```python
HOST_KINDS = (
    "reminder_host",
```

Excerpt `App/app/host_i18n.py` English (verbatim, one place): `        "payments.reason.custom": "Custom",`
Excerpt `App/app/host_i18n.py` Czech (verbatim, one place): `        "payments.reason.custom": "Vlastní",` — the file may store it as `"Vlastní"`; match whichever form `grep -n 'payments.reason.custom' App/app/host_i18n.py` shows.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_webhook.py` | create | handlers |
| `App/app/stripe_connect.py` | edit | dispatch booking sessions |
| `App/app/mail.py` | edit | 3 kinds |
| `App/app/host_i18n.py` | edit | EN + CS mail copy |
| `App/tests/test_booking_webhook.py` | create | tests |
| `docs/tasks/0816-report.md` | create | report |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0816 step k"`.

**Step 1.** Create `App/app/booking_webhook.py`:

```python
"""Booking site webhook (brief 0816, plan booking-site-v1).

paid session  -> lock, re-check, reservation (source 'site') + mails;
                 nights sold meanwhile -> full automatic refund + mails.
expired/failed session -> booking expired, hold released.
Every path is idempotent: Stripe retries until the handler returns.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from . import booking_site, config, db, host_i18n, mail, stripe_connect

log = logging.getLogger(__name__)

PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
END_EVENTS = ("checkout.session.expired", "checkout.session.async_payment_failed")
EVENTS = PAID_EVENTS + END_EVENTS


def is_booking_event(event: Dict[str, Any]) -> bool:
    obj = (event.get("data") or {}).get("object") or {}
    return event.get("type") in EVENTS and bool((obj.get("metadata") or {}).get("site_booking_id"))


def handle(event: Dict[str, Any]) -> None:
    obj = (event.get("data") or {}).get("object") or {}
    booking = booking_site.by_session(str(obj.get("id") or ""))
    if booking is None:
        log.warning("booking webhook: no booking for session %s", obj.get("id"))
        return
    if event.get("type") in END_EVENTS:
        _expire(booking)
        return
    if obj.get("payment_status") != "paid":
        return  # async method still pending; async_payment_succeeded follows
    if booking["status"] not in ("pending", "expired"):
        return  # already handled
    _confirm(booking, str(obj.get("payment_intent") or ""))


def _expire(booking: Dict[str, Any]) -> None:
    if booking["status"] != "pending":
        return
    booking_site.set_status(int(booking["id"]), "expired")
    if booking.get("hold_id"):
        db.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))


def _confirm(booking: Dict[str, Any], payment_intent: str) -> None:
    now = db.utcnow()
    reservation_id: Optional[int] = None
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (booking["apartment_id"], booking["date_to"], booking["date_from"]),
        )
        clash = cur.fetchone() is not None
        if not clash:
            cur.execute(
                "INSERT INTO reservation (apartment_id, source, uid, date_from, date_to,"
                " summary, expected_guests_override, guest_email, status, created_at, updated_at)"
                " VALUES (?, 'site', ?, ?, ?, ?, ?, ?, 'active', ?, ?) RETURNING id",
                (booking["apartment_id"], f"site-{booking['id']}", booking["date_from"],
                 booking["date_to"], booking["guest_name"], booking["guests"],
                 booking["guest_email"], now, now),
            )
            reservation_id = int(cur.fetchone()["id"])
            cur.execute(
                "UPDATE site_booking SET status = 'paid', reservation_id = ?,"
                " stripe_payment_intent_id = ?, paid_at = ?, updated_at = ?"
                " WHERE id = ? AND status IN ('pending', 'expired')",
                (reservation_id, payment_intent or None, now, now, booking["id"]),
            )
        if booking.get("hold_id"):
            cur.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    if clash:
        _refund_clash(booking, payment_intent)
        return
    db.audit("site_booking_paid", f"id={booking['id']} reservation={reservation_id}",
             owner_user_id=int(booking["owner_user_id"]))
    _mail_confirmed(booking_site.get(int(booking["id"])) or booking, int(reservation_id))


def _refund_clash(booking: Dict[str, Any], payment_intent: str) -> None:
    """Double booking: full refund on the host's account (raises -> Stripe retries)."""
    account = stripe_connect.account_for_owner(int(booking["owner_user_id"]))
    if account is None or not payment_intent:
        raise RuntimeError(f"site booking {booking['id']}: cannot refund (no account or intent)")
    api = stripe_connect._api()
    api.v1.refunds.create(
        params={"payment_intent": payment_intent,
                "metadata": {"site_booking_id": str(booking["id"])}},
        options={"stripe_account": account["stripe_account_id"],
                 "idempotency_key": f"site_booking_clash_refund_{booking['id']}"},
    )
    booking_site.set_status(int(booking["id"]), "clash_refunded",
                            refunded_czk=int(booking["total_czk"]),
                            stripe_payment_intent_id=payment_intent)
    db.audit("site_booking_clash_refunded", f"id={booking['id']} amount={booking['total_czk']}",
             owner_user_id=int(booking["owner_user_id"]))
    _mail_clash(booking)


# --- mails ---------------------------------------------------------------------


def _apartment(booking: Dict[str, Any]):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (booking["apartment_id"],))


def _host_email(apartment) -> str:
    from . import mail_notify

    return mail_notify._entity_contact_email(apartment["legal_entity_id"]) if apartment else ""


def _dates(booking: Dict[str, Any], lang: str) -> str:
    def one(iso: str) -> str:
        d = date.fromisoformat(iso)
        return f"{d.day}. {d.month}. {d.year}" if lang == "cs" else iso
    return f"{one(booking['date_from'])} – {one(booking['date_to'])}"


def _facts(booking: Dict[str, Any], apartment, lang: str) -> Dict[str, Any]:
    return {
        "property": apartment["internal_name"] if apartment else "",
        "dates": _dates(booking, lang),
        "guests": booking["guests"],
        "total": booking["total_czk"],
        "name": booking["guest_name"] or "",
        "email": booking["guest_email"] or "",
        "policy": host_i18n.translate(lang, f"pp.book.policy.{booking['cancellation_policy']}"),
    }


def _mail_confirmed(booking: Dict[str, Any], reservation_id: int) -> None:
    from . import guest_slug

    apartment = _apartment(booking)
    host_email = _host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = _facts(booking, apartment, lang)
    key = guest_slug.link_key(apartment) if apartment else ""
    link = f"{config.PUBLIC_BASE_URL.rstrip('/')}/l/{key}/{reservation_id}" if key else ""
    text = host_i18n.translate(lang, "site_booking.mail.guest_text", **facts)
    if link:
        text += "\n\n" + host_i18n.translate(lang, "site_booking.mail.guest_register", link=link)
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_confirmed",
            idempotency_key=f"site_booking:{booking['id']}:confirmed",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.guest_subject", **facts),
            payload={"text": text, "lang": lang, "reply_to": host_email},
            reservation_id=reservation_id,
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = _facts(booking, apartment, "cs")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_new",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", "site_booking.mail.host_text", **host_facts),
                     "lang": "cs"},
            reservation_id=reservation_id,
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )


def _mail_clash(booking: Dict[str, Any]) -> None:
    apartment = _apartment(booking)
    host_email = _host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = _facts(booking, apartment, lang)
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:clash_refund",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.clash_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.clash_text", **facts),
                     "lang": lang, "reply_to": host_email},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = _facts(booking, apartment, "cs")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_clash",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_clash_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", "site_booking.mail.host_clash_text", **host_facts),
                     "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
```

Run: `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_webhook.py 2>&1 | tail -3` → `All checks passed!`

**Step 2.** In `App/app/stripe_connect.py`, replace the `process_event` excerpt with:

```python
    etype = event.get("type")
    from . import booking_webhook

    if etype == "account.updated":
        mirror_by_account_id(dict(event["data"]["object"]), config.STRIPE_MODE)
    elif booking_webhook.is_booking_event(event):
        booking_webhook.handle(event)
    elif etype in payment_links.PAID_EVENTS:
        payment_links.on_paid(event)
    _record_event(event)
```

**Step 3.** In `App/app/mail.py`:
(a) replace the `KINDS` excerpt with the same lines plus three kinds right after `"reminder_host",`:

```python
KINDS = (
    "claim",
    "claim_resend",
    "payment_request",
    "reminder_guest",
    "reminder_host",
    # 0816: booking site — guest confirmation, guest double-booking refund, host notice.
    "site_booking_confirmed",
    "site_booking_refunded",
    "site_booking_host",
```

(b) replace the `GUEST_KINDS` excerpt with:

```python
    "invoice_issued",
    "door_code",
    "site_booking_confirmed",
    "site_booking_refunded",
)
```

(c) replace the `HOST_KINDS` excerpt with:

```python
HOST_KINDS = (
    "reminder_host",
    "site_booking_host",
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py tests/test_claim_mail.py -q --tb=short -x -k "kinds or KINDS or booking" 2>&1 | tail -3` → passes.

**Step 4.** In `App/app/host_i18n.py`, insert directly below the English `"payments.reason.custom"` line:

```python
        "site_booking.mail.guest_subject": "Booking confirmed: %(property)s, %(dates)s",
        "site_booking.mail.guest_text": "Hello %(name)s,\n\nyour booking is confirmed and paid.\n\nPlace: %(property)s\nDates: %(dates)s\nGuests: %(guests)s\nPaid: %(total)s CZK\n%(policy)s\nThe local accommodation tax is paid on site.\n\nAnswer this e-mail to reach your host.",
        "site_booking.mail.guest_register": "Before you arrive, fill in the guest details the law requires here: %(link)s",
        "site_booking.mail.clash_subject": "Your booking could not be confirmed: full refund",
        "site_booking.mail.clash_text": "Hello %(name)s,\n\nwe are sorry: %(property)s was booked for %(dates)s by someone else a moment before your payment arrived. You get the full %(total)s CZK back to your card automatically; banks usually show it within 5 to 10 days.\n\nAnswer this e-mail to reach the host.",
        "site_booking.mail.host_subject": "New booking from your website: %(property)s, %(dates)s",
        "site_booking.mail.host_text": "New paid booking from your website.\n\nPlace: %(property)s\nDates: %(dates)s\nGuests: %(guests)s\nPaid: %(total)s CZK\nGuest: %(name)s, %(email)s\n\nThe stay is in UbyHost now; the guest got the link to the guest register.",
        "site_booking.mail.host_clash_subject": "Double booking prevented: %(property)s, %(dates)s",
        "site_booking.mail.host_clash_text": "A guest paid for %(property)s, %(dates)s, but those nights were already taken. We refunded the full %(total)s CZK automatically; the card fee stays with Stripe. Guest: %(name)s, %(email)s.\n\nNo action is needed.",
```

and directly below the Czech `"payments.reason.custom"` line (keep this Czech text; plain UTF-8 is fine):

```python
        "site_booking.mail.guest_subject": "Rezervace potvrzena: %(property)s, %(dates)s",
        "site_booking.mail.guest_text": "Dobrý den, %(name)s,\n\nvaše rezervace je potvrzená a zaplacená.\n\nUbytování: %(property)s\nTermín: %(dates)s\nPočet hostů: %(guests)s\nZaplaceno: %(total)s Kč\n%(policy)s\nMístní poplatek z pobytu se platí na místě.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel.",
        "site_booking.mail.guest_register": "Před příjezdem prosím vyplňte údaje, které vyžaduje zákon: %(link)s",
        "site_booking.mail.clash_subject": "Rezervaci nešlo potvrdit: vracíme celou částku",
        "site_booking.mail.clash_text": "Dobrý den, %(name)s,\n\nomlouváme se: %(property)s si na termín %(dates)s těsně před vaší platbou zarezervoval někdo jiný. Celých %(total)s Kč se vám automaticky vrátí na kartu; banka je obvykle připíše do 5 až 10 dnů.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel.",
        "site_booking.mail.host_subject": "Nová rezervace z vašeho webu: %(property)s, %(dates)s",
        "site_booking.mail.host_text": "Máte novou zaplacenou rezervaci z vašeho webu.\n\nUbytování: %(property)s\nTermín: %(dates)s\nPočet hostů: %(guests)s\nZaplaceno: %(total)s Kč\nHost: %(name)s, %(email)s\n\nPobyt už je v UbyHostu a host dostal odkaz do knihy hostů.",
        "site_booking.mail.host_clash_subject": "Dvojí rezervaci jsme zastavili: %(property)s, %(dates)s",
        "site_booking.mail.host_clash_text": "Host zaplatil %(property)s na %(dates)s, ale tyto noci už byly obsazené. Celých %(total)s Kč jsme mu automaticky vrátili; poplatek za kartu si ponechává Stripe. Host: %(name)s, %(email)s.\n\nNemusíte nic dělat.",
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -3` → passes (test_booking_site.py must stay first: test_host_i18n.py alone has no database).

**Step 5.** Create `App/tests/test_booking_webhook.py`:

```python
"""Brief 0816: booking site webhook (confirm, double-booking refund, expiry)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app import auth, booking_checkout, booking_site, booking_webhook, config, db, mail, stripe_connect

OWNER = "webhookhost"
FROM, TO = "2027-04-10", "2027-04-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeRefunds:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []

    def create(self, params=None, options=None):
        assert options and options.get("stripe_account") == "acct_hook"
        assert options.get("idempotency_key")
        self.created.append(params)
        self.options.append(options)
        return {"id": "re_test_1"}


@pytest.fixture
def refunds(monkeypatch):
    fake = _FakeRefunds()

    class _V1:
        pass

    _V1.refunds = fake

    class _Client:
        v1 = _V1()

    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return fake


@pytest.fixture
def booking(monkeypatch):
    db.init_db()
    _cleanup()
    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(mail, "enqueue", lambda **kw: sent.append(kw) or 1)
    auth.create_account(f"{OWNER}@example.test", "Hook Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = db.insert("legal_entity", {"owner_user_id": oid, "name": "Hook Host",
                                        "contact_email": "host@example.test",
                                        "created_at": db.utcnow()})
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Hook Flat",
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_hook", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    q = booking_site.quote(aid, FROM, TO, 2)
    hold = booking_checkout.hold_dates(aid, FROM, TO)
    row = booking_site.create_pending(aid, oid, q, guest_name="Jana Nová",
                                      guest_email="jana@example.test", lang="cs", hold_id=hold)
    booking_site.attach_session(row["id"], "cs_hook_1")
    row = booking_site.get(row["id"])
    row["sent"] = sent
    try:
        yield row
    finally:
        _cleanup()


def _event(etype: str, status: str = "paid", eid: str = "evt_1") -> Dict[str, Any]:
    return {"id": eid, "type": etype, "data": {"object": {
        "id": "cs_hook_1", "payment_status": status, "payment_intent": "pi_hook_1",
        "metadata": {"site_booking_id": "1"},
    }}}


def test_paid_creates_reservation_and_mails(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed"))
    row = booking_site.get(booking["id"])
    assert row["status"] == "paid" and row["stripe_payment_intent_id"] == "pi_hook_1"
    res = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    assert res["source"] == "site" and res["date_from"] == FROM and res["guest_email"] == "jana@example.test"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None
    kinds = sorted(m["kind"] for m in booking["sent"])
    assert kinds == ["site_booking_confirmed", "site_booking_host"]
    guest = next(m for m in booking["sent"] if m["kind"] == "site_booking_confirmed")
    assert "Rezervace potvrzena" in guest["subject"] and guest["payload"]["reply_to"] == "host@example.test"
    assert refunds.created == []


def test_paid_twice_is_idempotent(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed"))
    booking_webhook.handle(_event("checkout.session.async_payment_succeeded"))
    n = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?",
                     (booking["apartment_id"],))["n"]
    assert n == 1


def test_unpaid_async_waits(booking, refunds):
    booking_webhook.handle(_event("checkout.session.completed", status="unpaid"))
    assert booking_site.get(booking["id"])["status"] == "pending"


def test_clash_refunds_in_full(booking, refunds):
    db.insert("reservation", {
        "apartment_id": booking["apartment_id"], "source": "ical", "uid": "airbnb-1",
        "date_from": "2027-04-12", "date_to": "2027-04-15", "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    booking_webhook.handle(_event("checkout.session.completed"))
    row = booking_site.get(booking["id"])
    assert row["status"] == "clash_refunded" and row["refunded_czk"] == 6500
    assert refunds.created[0]["payment_intent"] == "pi_hook_1"
    kinds = sorted(m["kind"] for m in booking["sent"])
    assert kinds == ["site_booking_host", "site_booking_refunded"]
    n = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE source = 'site' AND apartment_id = ?",
                     (booking["apartment_id"],))["n"]
    assert n == 0


def test_expired_releases_hold(booking, refunds):
    booking_webhook.handle(_event("checkout.session.expired", status="unpaid"))
    assert booking_site.get(booking["id"])["status"] == "expired"
    assert db.query_one("SELECT id FROM booking_hold WHERE id = ?", (booking["hold_id"],)) is None


def test_process_event_routes_booking_sessions(booking, refunds, monkeypatch):
    called = []
    from app import payment_links

    monkeypatch.setattr(payment_links, "on_paid", lambda e: called.append(e))
    stripe_connect.process_event(_event("checkout.session.completed", eid="evt_route_1"))
    assert called == []
    assert booking_site.get(booking["id"])["status"] == "paid"
    db.execute("DELETE FROM stripe_webhook_event WHERE event_id = ?", ("evt_route_1",))
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_webhook.py -q --tb=short -x 2>&1 | tail -15` → all pass. If `legal_entity` insert fails on a NOT NULL column, add only that column with a plain test value in the fixture and list it under Deviations.

## 5. Do not touch

`booking_site.py`, `booking_checkout.py`, `payment_links.py`, `routes/*`, templates, `db.py`, migrations. Hard rules 3, 4, 5, 8.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -3
.venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_webhook.py tests/test_booking_checkout.py tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_claim_mail.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
```

## 7. Acceptance

- [ ] The §6 run passes.
- [ ] `git diff --stat task/0815-booking-site-checkout` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0816-report.md` (600 tokens at most) and set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/booking_webhook.py` (`_confirm` lock and SQL, `_refund_clash`), `App/app/stripe_connect.py` dispatch order.

## Owner steps

1. Merge after 0815 when CI is green; deploy.
2. Stripe Dashboard → Developers → Webhooks → the UbyHost endpoint (Connected accounts): make sure these events are ticked: `account.updated`, `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`. Save.
