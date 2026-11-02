# 0815: Booking site checkout (Stripe Checkout on the host's account)

Status: in-progress
Depends on: 0814 | Base commit: tip of task/0814-booking-site-model | Branch: task/0815-booking-site-checkout
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A guest on `/p/<slug>` picks dates and guests, sees the price lines, enters name and e-mail, ticks the terms and taps "Pokračovat k platbě": we hold the dates for 15 minutes, store a pending `site_booking`, create a Stripe Checkout Session on the host's connected account and show one button to Stripe. This replaces the old request-to-book path (owner decision 1 Nov: instant book, full payment). The webhook that confirms the booking is 0816.

## 2. Context

Plan: `docs/plans/booking-site-v1.md`. Rules from 0814 live in `App/app/booking_site.py` (`quote`, `create_pending`, `attach_session`, `set_status`).

- CSP has `form-action 'self'`: a POST must never redirect off-site (lesson from 0763). The checkout POST therefore renders a page with a plain link to Stripe; it never answers 303 to stripe.com.
- Stripe calls go through `stripe_connect._api()` and pass the connected account in `options={"stripe_account": ...}`, never in `params` (0622). Tests fake `stripe_connect._client` exactly like `App/tests/test_payment_rails.py` does.
- Inside `with db.immediate() as cur:` use only `cur.execute(...)`; `db.lock_key(cur, name, id)` serialises writers on PostgreSQL.
- Stripe links carry `data-no-prefetch` (0500).

Excerpt `App/app/routes/property_page.py` (imports, verbatim):

```python
from .. import config, db, property_page, rate_limit
```

Excerpt `App/app/routes/property_page.py` (in `property_page_view`, verbatim):

```python
    page["bookable"] = property_page.widget_ready(apartment_id)
```

Excerpt `App/app/routes/property_page.py`: the whole block from the line `@router.post("/p/{slug}/book")` to the end of the file (functions `property_page_book`, `_book_error`, `property_page_request`), as on main after 0814.

Excerpt `App/app/templates/property_page.html` (verbatim):

```html
        <label class="ui-field"><span>{{ t('pp.book.to') }}</span>
          <input class="ui-input" type="date" name="date_to" required></label>
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.check') }}</button>
```

Excerpt `App/app/host_i18n.py`, English block (verbatim, one place):

```python
        "pp.book.email": "Your e-mail",
        "pp.book.send_request": "Send a booking request",
        "pp.book.request_note": "The host confirms your request; you pay only after the host accepts.",
        "pp.book.done": "Request sent",
        "pp.book.done_note": "The host has your request and will get back to you.",
```

Excerpt `App/app/host_i18n.py`, Czech block (verbatim, one place; the file stores Czech as `\u` escapes):

```python
        "pp.book.email": "Váš e-mail",
        "pp.book.send_request": "Odeslat poptávku",
        "pp.book.request_note": "Hostitel vaši poptávku potvrdí; platíte až po jejím přijetí.",
        "pp.book.done": "Poptávka odeslána",
        "pp.book.done_note": "Hostitel má vaši poptávku a ozve se.",
```

Excerpt `App/tests/test_booking_widget.py`: the whole function `test_request_creates_draft_for_host` (starts `def test_request_creates_draft_for_host(owner, monkeypatch):`, ends with `assert rows[0]["amount_czk"] == 3600`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_checkout.py` | create | hold + pending booking + Checkout Session |
| `App/app/routes/property_page.py` | edit | `/book` uses the quote; new `/checkout`, `/thanks`; remove `/request`; page shows `?book=` errors |
| `App/app/templates/property_page.html` | edit | guests field + error line |
| `App/app/templates/property_page_book.html` | replace | price lines + guest form |
| `App/app/templates/property_page_pay.html` | create | one button to Stripe |
| `App/app/templates/property_page_booked.html` | replace | thank-you page |
| `App/app/host_i18n.py` | edit | EN + CS keys |
| `App/tests/test_booking_widget.py` | edit | replace the request test |
| `App/tests/test_booking_checkout.py` | create | tests |
| `docs/tasks/0815-report.md` | create | report |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0815 step k"`.

**Step 1.** Create `App/app/booking_checkout.py`:

```python
"""Booking site checkout (brief 0815, plan booking-site-v1).

Hold the dates under a lock, store the pending booking, then open a Stripe
Checkout Session on the host's connected account (direct charge, 0 % fee).
The webhook (0816) turns a paid session into a reservation.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import booking_site, config, db, stripe_connect

log = logging.getLogger(__name__)

HOLD_MINUTES = 15
# Stripe's minimum session lifetime is 30 minutes; one more absorbs clock skew.
SESSION_MINUTES = 31


def hold_dates(apartment_id: int, date_from: str, date_to: str,
               *, minutes: int = HOLD_MINUTES) -> Optional[int]:
    """Re-check and hold under a lock; None if the nights were taken meanwhile."""
    now = db.utcnow()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", apartment_id)
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (apartment_id, date_to, date_from),
        )
        if cur.fetchone() is not None:
            return None
        cur.execute(
            "SELECT id FROM booking_hold WHERE apartment_id = ? AND expires_at > ?"
            " AND date_from < ? AND date_to > ?",
            (apartment_id, now, date_to, date_from),
        )
        if cur.fetchone() is not None:
            return None
        cur.execute(
            "INSERT INTO booking_hold (apartment_id, date_from, date_to, expires_at, created_at)"
            " VALUES (?, ?, ?, ?, ?) RETURNING id",
            (apartment_id, date_from, date_to, expires, now),
        )
        return int(cur.fetchone()["id"])


def _cz_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def product_name(name: str, q: Dict[str, Any], lang: str) -> str:
    """What the guest sees on Stripe Checkout and the receipt."""
    if lang == "cs":
        return f"Ubytování {name}, {_cz_date(q['date_from'])} – {_cz_date(q['date_to'])}"
    return f"Stay at {name}, {q['date_from']} – {q['date_to']}"


def start(apartment_id: int, slug: str, q: Dict[str, Any], *,
          guest_name: str, guest_email: str, lang: str) -> Dict[str, Any]:
    """{"url": <Stripe URL>, "booking_id": n} or {"error": "taken"|"unavailable"}."""
    apartment = db.query_one(
        "SELECT owner_user_id, internal_name FROM apartment WHERE id = ?", (apartment_id,)
    )
    if apartment is None:
        return {"error": "unavailable"}
    owner = int(apartment["owner_user_id"])
    account = stripe_connect.account_for_owner(owner)
    if account is None or account["onboarding_state"] != "complete":
        return {"error": "unavailable"}
    hold_id = hold_dates(apartment_id, q["date_from"], q["date_to"])
    if hold_id is None:
        return {"error": "taken"}
    booking = booking_site.create_pending(
        apartment_id, owner, q, guest_name=guest_name, guest_email=guest_email,
        lang=lang, hold_id=hold_id,
    )
    base = config.PUBLIC_BASE_URL.rstrip("/")
    try:
        api = stripe_connect._api()
        session = api.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "line_items": [{
                    "quantity": 1,
                    "price_data": {
                        "currency": "czk",
                        "unit_amount": int(q["total_czk"]) * 100,
                        "product_data": {
                            "name": product_name(apartment["internal_name"], q, lang),
                        },
                    },
                }],
                "customer_email": booking["guest_email"],
                "locale": "cs" if lang == "cs" else "en",
                "expires_at": int(time.time()) + SESSION_MINUTES * 60,
                "success_url": f"{base}/p/{slug}/thanks",
                "cancel_url": f"{base}/p/{slug}?book=cancelled",
                "metadata": {"site_booking_id": str(booking["id"])},
                "payment_intent_data": {
                    "metadata": {"site_booking_id": str(booking["id"])},
                },
            },
            options={"stripe_account": account["stripe_account_id"]},
        )
    except Exception:  # Stripe down, cap reached, bad key: free the dates
        log.exception("site booking %s: checkout session failed", booking["id"])
        db.execute("DELETE FROM booking_hold WHERE id = ?", (hold_id,))
        booking_site.set_status(int(booking["id"]), "expired")
        return {"error": "unavailable"}
    booking_site.attach_session(int(booking["id"]), str(session["id"]))
    db.audit(
        "site_booking_checkout",
        f"id={booking['id']} session={session['id']}",
        owner_user_id=owner,
    )
    return {"url": str(session["url"]), "booking_id": int(booking["id"])}
```

Run: `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_checkout.py 2>&1 | tail -3` → `All checks passed!`

**Step 2.** In `App/app/routes/property_page.py`:

(a) Replace the imports excerpt with:

```python
from .. import booking_checkout, booking_site, config, db, property_page, rate_limit
```

(b) Replace the `page["bookable"]` excerpt with:

```python
    page["bookable"] = property_page.widget_ready(apartment_id)
    page["book_error"] = request.query_params.get("book", "")
    if page["book_error"] not in BOOK_ERRORS:
        page["book_error"] = ""
```

(c) Replace the whole block from `@router.post("/p/{slug}/book")` to the end of the file with:

```python
BOOK_ERRORS = ("bad_dates", "min_nights", "too_soon", "guests", "no_price", "taken",
               "bad_email", "bad_name", "terms", "unavailable", "cancelled")
_EMAIL = __import__("re").compile(r"[^@\s]{1,64}@[^@\s]{1,200}\.[^@\s]{2,30}")
_CHECKOUT_MAX = 20
_CHECKOUT_WINDOW = 3600


def _bookable_apartment(slug: str):
    resolved = property_page.resolve(slug)
    if resolved is None or "redirect" in resolved or resolved.get("missing"):
        return None
    apartment_id = int(resolved["apartment_id"])
    if not property_page.widget_ready(apartment_id):
        return None
    return apartment_id


def _guests(value) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


@router.post("/p/{slug}/book")
async def property_page_book(request: Request, slug: str):
    """No-JS form POST: dates + guests -> the quote and the guest form.
    Nothing is held here; the hold starts at /checkout."""
    apartment_id = _bookable_apartment(slug)
    if apartment_id is None:
        return Response(status_code=404)
    form = await request.form()
    q = booking_site.quote(
        apartment_id,
        str(form.get("date_from") or "").strip(),
        str(form.get("date_to") or "").strip(),
        _guests(form.get("guests") or 1),
    )
    if q["error"]:
        return _book_error(slug, q["error"])
    return render(
        request,
        "property_page_book.html",
        {"page": _page_context(apartment_id) or {}, "show_nav": False, "lang": "en",
         "slug": slug, "q": q},
    )


def _book_error(slug: str, kind: str) -> Response:
    return RedirectResponse(f"/p/{slug}?book={kind}#book", status_code=303)


@router.post("/p/{slug}/checkout")
async def property_page_checkout(request: Request, slug: str):
    """Hold + pending booking + Stripe session, then a page with one link to
    Stripe (a POST never redirects off-site: CSP form-action 'self')."""
    scope = "property_page_checkout"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _CHECKOUT_MAX, _CHECKOUT_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    apartment_id = _bookable_apartment(slug)
    if apartment_id is None:
        return Response(status_code=404)
    form = await request.form()
    q = booking_site.quote(
        apartment_id,
        str(form.get("date_from") or "").strip(),
        str(form.get("date_to") or "").strip(),
        _guests(form.get("guests")),
    )
    if q["error"]:
        return _book_error(slug, q["error"])
    name = " ".join(str(form.get("guest_name") or "").split())
    email = str(form.get("guest_email") or "").strip()
    if len(name) < 3:
        return _book_error(slug, "bad_name")
    if not _EMAIL.fullmatch(email):
        return _book_error(slug, "bad_email")
    if str(form.get("terms") or "") != "1":
        return _book_error(slug, "terms")
    lang = "cs" if str(form.get("lang") or "") == "cs" else "en"
    result = booking_checkout.start(apartment_id, slug, q, guest_name=name,
                                    guest_email=email, lang=lang)
    if result.get("error"):
        return _book_error(slug, result["error"])
    response = render(
        request,
        "property_page_pay.html",
        {"page": _page_context(apartment_id) or {}, "show_nav": False, "lang": "en",
         "pay_url": result["url"], "total": q["total_czk"]},
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@router.get("/p/{slug}/thanks")
def property_page_thanks(request: Request, slug: str):
    """Stripe's success_url. Shows no booking data: the confirmation e-mail
    (0816) is the record."""
    response = render(request, "property_page_booked.html",
                      {"show_nav": False, "slug": slug, "lang": "en"})
    response.headers["X-Robots-Tag"] = "noindex"
    return response
```

Run: `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/routes/property_page.py 2>&1 | tail -3` → `All checks passed!`

**Step 3.** In `App/app/templates/property_page.html`, replace the excerpt with:

```html
        <label class="ui-field"><span>{{ t('pp.book.to') }}</span>
          <input class="ui-input" type="date" name="date_to" required></label>
        <label class="ui-field"><span>{{ t('pp.book.guests') }}</span>
          <input class="ui-input" type="number" name="guests" min="1" max="60" value="2" inputmode="numeric" required></label>
        {% if page.book_error %}<p class="ui-sub" role="alert" id="book">{{ t('pp.book.err.' ~ page.book_error) }}</p>{% endif %}
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.check') }}</button>
```

**Step 4.** Replace the whole content of `App/app/templates/property_page_book.html` with:

```html
{% extends "base.html" %}
{% block title %}{{ t('pp.book.title') }} · {{ page.name }}{% endblock %}
{% block content %}
<main class="pp" style="max-width:520px;margin:2rem auto;padding:0 1rem;">
  <h1>{{ t('pp.book.title') }} — {{ page.name }}</h1>
  <p class="pp-location">{{ page.district }}</p>
  <table class="ui-table">
    <tbody>
      <tr><td>{{ t('pp.book.dates') }}</td><td>{{ q.date_from }} → {{ q.date_to }} ({{ q.nights }} {{ t('pp.book.nights') }})</td></tr>
      <tr><td>{{ t('pp.book.guests') }}</td><td>{{ q.guests }}</td></tr>
      <tr><td>{{ t('pp.book.nightly') }} × {{ q.nights }}</td><td>{{ q.accommodation_czk }} {{ t('payments.czk') }}</td></tr>
      {% if q.cleaning_fee_czk %}<tr><td>{{ t('pp.book.cleaning') }}</td><td>{{ q.cleaning_fee_czk }} {{ t('payments.czk') }}</td></tr>{% endif %}
      <tr><td>{{ t('pp.book.total') }}</td><td><strong>{{ q.total_czk }} {{ t('payments.czk') }}</strong></td></tr>
      {% if q.city_tax_on_site_czk %}<tr><td>{{ t('pp.book.city_tax') }}</td><td>{{ q.city_tax_on_site_czk }} {{ t('payments.czk') }}</td></tr>{% endif %}
    </tbody>
  </table>
  <p class="ui-sub">{{ t('pp.book.policy.' ~ q.cancellation_policy) }}</p>
  <form method="post" action="/p/{{ slug }}/checkout" class="ui-form">
    <label class="ui-field">
      <span>{{ t('pp.book.name') }}</span>
      <input class="ui-input" type="text" name="guest_name" autocomplete="name" minlength="3" maxlength="120" required>
    </label>
    <label class="ui-field">
      <span>{{ t('pp.book.email') }}</span>
      <input class="ui-input" type="email" name="guest_email" autocomplete="email" required>
    </label>
    <label class="ui-check">
      <input type="checkbox" name="terms" value="1" required>
      <span>{{ t('pp.book.terms') }}</span>
    </label>
    <input type="hidden" name="date_from" value="{{ q.date_from }}">
    <input type="hidden" name="date_to" value="{{ q.date_to }}">
    <input type="hidden" name="guests" value="{{ q.guests }}">
    <input type="hidden" name="lang" value="{{ lang }}">
    <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.send_request') }}</button>
  </form>
  <p class="ui-sub">{{ t('pp.book.request_note') }}</p>
</main>
{% endblock %}
```

**Step 5.** Create `App/app/templates/property_page_pay.html`:

```html
{% extends "base.html" %}
{% block title %}{{ t('pp.book.pay_title') }}{% endblock %}
{% block content %}
<main style="max-width:480px;margin:2rem auto;padding:0 1rem;">
  <h1>{{ t('pp.book.pay_title') }}</h1>
  <p>{{ t('pp.book.pay_note') }}</p>
  <p><a class="ui-btn ui-btn-primary" href="{{ pay_url }}" rel="noopener" data-no-prefetch>{{ t('pp.book.pay_button') }} · {{ total }} {{ t('payments.czk') }}</a></p>
</main>
{% endblock %}
```

**Step 6.** Replace the whole content of `App/app/templates/property_page_booked.html` with:

```html
{% extends "base.html" %}
{% block title %}{{ t('pp.book.done') }}{% endblock %}
{% block content %}
<main style="max-width:480px;margin:2rem auto;padding:0 1rem;">
  <h1>{{ t('pp.book.done') }}</h1>
  <p>{{ t('pp.book.done_note') }}</p>
  <p><a href="/p/{{ slug }}">{{ t('pp.book.back') }}</a></p>
</main>
{% endblock %}
```

**Step 7.** In `App/app/host_i18n.py`, replace the English excerpt with:

```python
        "pp.book.email": "Your e-mail",
        "pp.book.send_request": "Continue to payment",
        "pp.book.request_note": "You pay the full price now by card. We confirm the booking by e-mail as soon as the payment goes through.",
        "pp.book.done": "Thank you",
        "pp.book.done_note": "We are confirming your payment. The confirmation arrives by e-mail within a few minutes.",
        "pp.book.back": "Back to the listing",
        "pp.book.guests": "Guests",
        "pp.book.name": "Full name",
        "pp.book.cleaning": "Cleaning fee",
        "pp.book.city_tax": "City tax, paid on site",
        "pp.book.terms": "I agree to the booking and cancellation terms and I am at least 18.",
        "pp.book.policy.non_refundable": "Non-refundable: no refund if you cancel.",
        "pp.book.policy.flexible": "Flexible: full refund until 24 hours before check-in.",
        "pp.book.policy.moderate": "Moderate: full refund until 5 days before check-in, then half of the nights.",
        "pp.book.pay_title": "Continue to secure payment",
        "pp.book.pay_note": "Stripe processes the payment for the host. Your dates are held for 15 minutes.",
        "pp.book.pay_button": "Pay",
        "pp.book.err.bad_dates": "Check the arrival and departure dates (30 nights at most).",
        "pp.book.err.min_nights": "This place needs a longer stay.",
        "pp.book.err.too_soon": "This day can no longer be booked. Pick a later arrival.",
        "pp.book.err.guests": "The place does not take that many guests.",
        "pp.book.err.no_price": "This place has no price yet.",
        "pp.book.err.taken": "These dates are already taken.",
        "pp.book.err.bad_email": "Enter a valid e-mail.",
        "pp.book.err.bad_name": "Enter your full name.",
        "pp.book.err.terms": "Tick the box to agree to the terms.",
        "pp.book.err.unavailable": "We could not prepare the payment right now. Please try again in a moment.",
        "pp.book.err.cancelled": "The payment was not completed. The dates are released within 15 minutes.",
```

**Step 8.** In `App/app/host_i18n.py`, replace the Czech excerpt with (keep the `\u` escapes exactly):

```python
        "pp.book.email": "Váš e-mail",
        "pp.book.send_request": "Pokračovat k platbě",
        "pp.book.request_note": "Celou cenu zaplatíte nyní kartou. Rezervaci potvrdíme e-mailem, jakmile platba projde.",
        "pp.book.done": "Děkujeme",
        "pp.book.done_note": "Ověřujeme vaši platbu. Potvrzení přijde e-mailem během několika minut.",
        "pp.book.back": "Zpět na ubytování",
        "pp.book.guests": "Počet hostů",
        "pp.book.name": "Jméno a příjmení",
        "pp.book.cleaning": "Úklid",
        "pp.book.city_tax": "Místní poplatek, platí se na místě",
        "pp.book.terms": "Souhlasím s podmínkami rezervace a storna a je mi alespoň 18 let.",
        "pp.book.policy.non_refundable": "Nevratná: při zrušení se platba nevrací.",
        "pp.book.policy.flexible": "Flexibilní: plná náhrada do 24 hodin před příjezdem.",
        "pp.book.policy.moderate": "Střední: plná náhrada do 5 dnů před příjezdem, potom polovina ceny nocí.",
        "pp.book.pay_title": "Pokračujte k bezpečné platbě",
        "pp.book.pay_note": "Platbu pro hostitele zpracuje Stripe. Termín vám držíme 15 minut.",
        "pp.book.pay_button": "Zaplatit",
        "pp.book.err.bad_dates": "Zkontrolujte datum příjezdu a odjezdu (nejvýše 30 nocí).",
        "pp.book.err.min_nights": "Toto ubytování vyžaduje delší pobyt.",
        "pp.book.err.too_soon": "Na tento den už rezervovat nelze. Zvolte pozdější příjezd.",
        "pp.book.err.guests": "Tolik hostů ubytování nepojme.",
        "pp.book.err.no_price": "Ubytování zatím nemá cenu.",
        "pp.book.err.taken": "Tento termín je už obsazený.",
        "pp.book.err.bad_email": "Zadejte platný e-mail.",
        "pp.book.err.bad_name": "Zadejte jméno a příjmení.",
        "pp.book.err.terms": "Pro pokračování potvrďte souhlas s podmínkami.",
        "pp.book.err.unavailable": "Platbu se teď nepodařilo připravit. Zkuste to prosím za chvíli.",
        "pp.book.err.cancelled": "Platba nebyla dokončena. Termín se uvolní do 15 minut.",
```

Run: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -5` → passes (English and Czech carry the same keys).

**Step 9.** In `App/tests/test_booking_widget.py`, replace the whole `test_request_creates_draft_for_host` function with:

```python
def test_request_route_is_gone(owner, monkeypatch):
    """0815: instant book replaced request-to-book (owner decision 1 Nov)."""
    _complete_account(owner, monkeypatch)
    client = _client()
    response = client.post(f"/p/{_slug(owner)}/request",
                           data={"date_from": "2026-12-01", "date_to": "2026-12-04",
                                 "guest_email": "guest@example.test"})
    assert response.status_code in (404, 405)
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_widget.py -q --tb=short 2>&1 | tail -15`. If another test in this file fails because `/book` now needs `guests` or renders different text, fix only that test's form data or expected text (add `"guests": "2"`; the quote page still shows `Total`), and list it under Deviations.

**Step 10.** Create `App/tests/test_booking_checkout.py`:

```python
"""Brief 0815: booking site checkout (hold, pending booking, Stripe session)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_checkout, booking_site, config, db, host_i18n, property_page, stripe_connect
from app.main import app

OWNER = "checkouthost"
FROM, TO = "2027-03-10", "2027-03-13"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeSessions:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.options: List[Dict[str, Any]] = []
        self.fail = False

    def create(self, params=None, options=None):
        assert params is not None
        assert "stripe_account" not in params, "stripe_account belongs in options="
        assert options and options.get("stripe_account") == "acct_site"
        if self.fail:
            raise RuntimeError("stripe down")
        self.created.append(params)
        self.options.append(options)
        return {"id": f"cs_test_{len(self.created)}", "url": "https://checkout.stripe.com/c/pay/cs_test"}


@pytest.fixture
def fake_sessions(monkeypatch):
    sessions = _FakeSessions()

    class _Checkout:
        pass

    _Checkout.sessions = sessions

    class _V1:
        checkout = _Checkout

    class _Client:
        v1 = _V1()

    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    monkeypatch.setattr(stripe_connect, "_client", lambda: _Client())
    return sessions


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Checkout Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Site Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500})
    property_page.publish_page(aid, published=True)
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_site", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    try:
        yield aid
    finally:
        _cleanup()


def _client() -> TestClient:
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client


def _slug(aid: int) -> str:
    return property_page.account_row(aid)["slug"]


def _form(**extra) -> Dict[str, str]:
    data = {"date_from": FROM, "date_to": TO, "guests": "2", "guest_name": "Jana Nová",
            "guest_email": "jana@example.test", "terms": "1", "lang": "cs"}
    data.update(extra)
    return data


def test_book_shows_price_lines(apartment, fake_sessions):
    response = _client().post(f"/p/{_slug(apartment)}/book",
                              data={"date_from": FROM, "date_to": TO, "guests": "2"})
    assert response.status_code == 200
    assert "6500" in response.text and "Cleaning fee" in response.text
    assert f'action="/p/{_slug(apartment)}/checkout"' in response.text


def test_checkout_creates_hold_booking_and_session(apartment, fake_sessions):
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form())
    assert response.status_code == 200
    assert "https://checkout.stripe.com/c/pay/cs_test" in response.text
    assert response.headers["Cache-Control"] == "no-store"
    params = fake_sessions.created[0]
    assert params["mode"] == "payment" and params["locale"] == "cs"
    assert params["line_items"][0]["price_data"]["unit_amount"] == 650000
    assert params["line_items"][0]["price_data"]["product_data"]["name"].startswith("Ubytování Site Flat")
    booking = booking_site.by_session("cs_test_1")
    assert booking["status"] == "pending" and booking["total_czk"] == 6500
    assert params["metadata"] == {"site_booking_id": str(booking["id"])}
    assert not property_page.dates_available(apartment, FROM, TO)


def test_second_guest_cannot_take_held_dates(apartment, fake_sessions):
    client = _client()
    client.post(f"/p/{_slug(apartment)}/checkout", data=_form())
    response = client.post(f"/p/{_slug(apartment)}/checkout", data=_form(), follow_redirects=False)
    assert response.status_code == 303
    assert "book=taken" in response.headers["location"]
    assert len(fake_sessions.created) == 1


@pytest.mark.parametrize("extra,code", [
    ({"terms": ""}, "terms"),
    ({"guest_email": "nope"}, "bad_email"),
    ({"guest_name": "J"}, "bad_name"),
    ({"guests": "0"}, "guests"),
])
def test_checkout_validation(apartment, fake_sessions, extra, code):
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form(**extra),
                              follow_redirects=False)
    assert response.status_code == 303
    assert f"book={code}" in response.headers["location"]
    assert fake_sessions.created == []


def test_stripe_failure_frees_the_dates(apartment, fake_sessions):
    fake_sessions.fail = True
    response = _client().post(f"/p/{_slug(apartment)}/checkout", data=_form(),
                              follow_redirects=False)
    assert "book=unavailable" in response.headers["location"]
    assert property_page.dates_available(apartment, FROM, TO)
    row = db.query_one("SELECT status FROM site_booking WHERE apartment_id = ?", (apartment,))
    assert row["status"] == "expired"


def test_error_is_shown_on_the_page(apartment, fake_sessions):
    response = _client().get(f"/p/{_slug(apartment)}?book=taken")
    assert "These dates are already taken." in response.text
    response = _client().get(f"/p/{_slug(apartment)}?book=<script>")
    assert "<script>" not in response.text


def test_thanks_page(apartment):
    response = _client().get(f"/p/{_slug(apartment)}/thanks")
    assert response.status_code == 200 and "Thank you" in response.text


def test_hold_dates_rejects_overlap(apartment):
    assert booking_checkout.hold_dates(apartment, FROM, TO) is not None
    assert booking_checkout.hold_dates(apartment, "2027-03-12", "2027-03-14") is None
    assert booking_checkout.hold_dates(apartment, TO, "2027-03-15") is not None
```

Run: `cd App && .venv/bin/python -m pytest tests/test_booking_checkout.py -q --tb=short -x 2>&1 | tail -15` → all pass.

## 5. Do not touch

`App/app/booking_site.py`, `stripe_connect.py`, `payment_links.py`, `App/app/main.py` (CSP), `db.py`, migrations, CSS files, `routes/payments.py`. Hard rules 2 (no third-party script; Stripe is a plain link), 3, 4, 5, 8.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_checkout.py app/routes/property_page.py tests/test_booking_checkout.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_checkout.py tests/test_booking_widget.py tests/test_booking_site.py tests/test_property_page.py tests/test_property_page_meta.py tests/test_host_i18n.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30
```

## 7. Acceptance

- [ ] The §6 test run passes.
- [ ] `grep -n '"/p/{slug}/request"' App/app/routes/property_page.py` prints nothing.
- [ ] `grep -n 'RedirectResponse' App/app/routes/property_page.py` shows only local `/p/` targets.
- [ ] `git diff --stat origin/main` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0815-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

`App/app/booking_checkout.py` (lock, Stripe params, failure path), `App/app/routes/property_page.py` (no off-site redirect, validation), `App/app/host_i18n.py`.

## Owner steps

1. Merge when CI is green.
2. Nothing to click yet: bookings stay "pending" until 0816 (the webhook) is merged and deployed, so do not share a booking page with real guests before then.
