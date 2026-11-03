# 0821: Booking site cancellation, guest side (booking page, self-cancel, automatic refund)

Status: todo
Depends on: 0818 and 0820 merged (0820 brings the signed booking link and the invoice; 0818 the page CSS and keys); the host side is 0822 | Base commit: tip of origin/main | Branch: task/0821-booking-site-cancellation
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

1. The guest opens the private booking page from the confirmation e-mail (`/p/<slug>/b/<id>/<token>`, the signed link from 0820), sees the booking, the cancellation terms, what they would get back today, downloads the invoice and adds the stay to a calendar (`Guest.dc.html`, 390 px). They can cancel without an account: the refund per the host's policy goes back to the card automatically (Stripe refund on the host's account, idempotency key), the reservation is cancelled so the nights are free again, and the guest and the host get an e-mail.
2. A full refund also issues the storno of the invoice (0820), best effort.
3. `booking_cancel.cancel(..., by_host=True)` (full refund) is built here and used by the host list in 0822.

Deviations from the mockup, on purpose (list them in the report): (1) the guest's e-mail address is shown masked (`j***@example.cz`) because the page is reachable by anyone who holds the link; (2) the refund box and the cancel button sit behind a `<details>` "Zrušit rezervaci" so a stray tap cannot cancel and no JavaScript is needed; (3) the invoice button shows only when an invoice exists; "Host.dc.html" (host cancel and list) is brief 0822.

## 2. Context

Plan: `docs/plans/booking-site-v1.md` (section 2 has the refund rules, implemented in `booking_site.refund_czk`). Status moves allowed by `booking_site.set_status` (verbatim):

```python
_TRANSITIONS = {
    "pending": {"paid", "expired", "clash_refunded"},
    "paid": {"cancelled", "refunded", "clash_refunded"},
    "cancelled": {"refunded"},
    "expired": {"paid", "clash_refunded"},
    "refunded": set(),
    "clash_refunded": set(),
}
```

`set_status(booking_id, status, **fields)` returns False when the booking is already in that status (so a double click loses), and accepts the fields `refunded_czk, invoice_id, paid_at, cancelled_at, reservation_id, stripe_*`. `refund_czk(booking, *, checkin_hour, now=None, by_host=False)` returns the amount for now (host cancel: the whole remaining amount). `settings(aid)["checkin_hour"]` is the check-in hour, `check_in_moment(date, hour)` the Prague datetime, `_now(now)` Prague now.

The refund pattern to copy is `booking_webhook._refund_clash` (verbatim):

```python
    api = stripe_connect._api()
    api.v1.refunds.create(
        params={"payment_intent": payment_intent,
                "metadata": {"site_booking_id": str(booking["id"])}},
        options={"stripe_account": account["stripe_account_id"],
                 "idempotency_key": f"site_booking_clash_refund_{booking['id']}"},
    )
```

The stripe account goes in `options`, never in `params` (0622). Amounts are minor units: CZK x 100 (as `unit_amount` in 0815). A refund can fail (Stripe down): the booking must then stay `cancelled`, nothing is lost, and the host can retry; a retry must refund exactly once. The idempotency key is per booking, not per amount, and the intended amount is stored before anything irreversible (`db.set_setting`), so a retry later in time cannot refund a different sum.

Cancelling a stay: the iCal sync does it with `db.update("reservation", id, {"status": "cancelled", "updated_at": now})`, then `claim.expire_on_cancel(row)` and `icalsync._warn_if_guests_registered(row, apartment_id, "cancelled")` (verbatim from `icalsync._cancel_existing_stay`):

```python
    db.update("reservation", existing["id"], {"status": "cancelled", "updated_at": now})
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
```

The nights are free again because `property_page.dates_available`, the calendar, the iCal export and `_confirm` only read `reservation.status = 'active'`.

Mails: `mail.enqueue(kind=..., idempotency_key=..., to_email=..., subject=..., payload={"text":..., "lang":..., "reply_to":...}, apartment_id=..., owner_user_id=...)`; reuse the kinds `site_booking_refunded` (guest) and `site_booking_host` (host). Helpers in `booking_webhook.py` to import and reuse (verbatim signatures): `_apartment(booking)`, `_host_email(apartment)`, `_facts(booking, apartment, lang)` (keys `property, dates, guests, total, name, email, policy`).

Invoice: `booking_site.get(id)["invoice_id"]` (0820). `invoices.cancel(invoice_id, reason, correction_date, actor_user_id, *, today)` issues a storno (non-payer) or corrective document (payer) and raises `ValueError` if it cannot (reason shorter than 5 characters, already corrected).

Public pages: the booking page is a capability link (HMAC token, 404 for anything else, rate limited like the other `/p/` routes, `noindex`, `no-store`). Public POST forms in `/p/` carry no `_csrf` field (as `/p/<slug>/checkout`).

The page CSS lives inline in `property_page.html` after 0818 (page-owned `<style>`, tokens only). This brief moves that block into a partial both public pages include, then adds a few rules.

Excerpt `App/app/templates/property_page.html` after 0818 (verbatim; the block to move starts at the line `<style>` that directly follows the `noindex` meta line and ends at the first `</style>` after it; its first and last rules are):

```html
<style>
.pp-bk { display: flex; flex-direction: column; gap: var(--space-4); max-width: 520px; margin-top: var(--space-6); }
...
@media (max-width: 480px) { .pp-bk { max-width: none; } }
</style>
```

Excerpt `docs/context/known-issues.md` (last line, verbatim; add yours after it):

```
- K-PG-ORDER: goose tests fail after icalsync locally; CI OK.
```

Excerpt `docs/context/decisions.md`: add one line at the end (see step 9).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_cancel.py` | create | cancel, refund, reservation, invoice storno, mails |
| `App/app/booking_manage.py` | create | page view data, masked e-mail, deadline text, one-stay iCal |
| `App/app/routes/property_page.py` | edit | `GET /p/{slug}/b/{id}/{token}`, `POST .../cancel`, `GET .../calendar.ics` |
| `App/app/templates/_pp_booking_css.html` | create | the moved page CSS plus new rules |
| `App/app/templates/property_page.html` | edit | include the partial instead of the inline block |
| `App/app/templates/booking_manage.html` | create | guest booking page |
| `App/app/host_i18n.py` | edit | EN + CS keys `bk.*`, mails |
| `App/tests/test_booking_cancel.py` | create | logic and routes |
| `App/tests/test_booking_manage_browser.py` | create | 390/360/1280 geometry, screenshot |
| `docs/context/decisions.md`, `docs/context/known-issues.md` | edit | one line each |
| `docs/tasks/0821-report.md`, `docs/tasks/screenshots-0821/guest-390.png` | create | report, screenshot |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0821 step k"`.

**Step 1.** Create `App/app/booking_cancel.py`:

```python
"""Booking site cancellation and refunds (brief 0821, plan booking-site-v1).

paid -> cancelled (dates freed, intended refund stored) -> Stripe refund ->
refunded. A failed refund leaves the booking `cancelled`; a retry refunds
exactly once (one idempotency key per booking, intended amount stored first).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from . import booking_site, booking_webhook, claim, db, host_i18n, mail, stripe_connect

log = logging.getLogger(__name__)


def _intent_key(booking_id: int) -> str:
    return f"site_booking_refund_intent:{int(booking_id)}"


def refund_now(booking: Dict[str, Any], *, by_host: bool, now: Optional[datetime] = None) -> int:
    s = booking_site.settings(int(booking["apartment_id"]))
    return booking_site.refund_czk(booking, checkin_hour=s["checkin_hour"],
                                   by_host=by_host, now=now)


def started(booking: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    s = booking_site.settings(int(booking["apartment_id"]))
    return booking_site.check_in_moment(booking["date_from"], s["checkin_hour"]) <= booking_site._now(now)


def cancel(booking_id: int, *, by_host: bool, now: Optional[datetime] = None) -> Dict[str, Any]:
    """{"error": None, "refund_czk": n} or {"error": not_found | not_cancellable
    | started | busy | refund_failed}. Safe to call twice."""
    booking = booking_site.get(booking_id)
    if booking is None:
        return {"error": "not_found"}
    owner = int(booking["owner_user_id"])
    if booking["status"] == "paid":
        if not by_host and started(booking, now):
            return {"error": "started"}
        amount = refund_now(booking, by_host=by_host, now=now)
        db.set_setting(_intent_key(booking_id), f"{amount}:{'h' if by_host else 'g'}")
        if not booking_site.set_status(booking_id, "cancelled", cancelled_at=db.utcnow()):
            return {"error": "busy"}
        _free_reservation(booking)
        db.audit("site_booking_cancelled",
                 f"id={booking_id} by={'host' if by_host else 'guest'} refund={amount}",
                 owner_user_id=owner)
    elif booking["status"] == "cancelled" and not int(booking["refunded_czk"] or 0):
        raw = db.get_setting(_intent_key(booking_id)) or ""
        number, _, who = raw.partition(":")
        if not number.isdigit() or who not in ("h", "g"):
            return {"error": "not_cancellable"}
        amount, by_host = int(number), who == "h"  # retry after a failed refund
    else:
        return {"error": "not_cancellable"}
    if amount > 0:
        try:
            _stripe_refund(booking, amount)
        except Exception:
            log.exception("site booking %s: refund failed", booking_id)
            _mail_refund_failed(booking)
            return {"error": "refund_failed", "refund_czk": amount}
        booking_site.set_status(booking_id, "refunded", refunded_czk=amount)
        db.audit("site_booking_refunded", f"id={booking_id} amount={amount}", owner_user_id=owner)
        if amount >= int(booking["total_czk"]):
            _storno_invoice(booking_site.get(booking_id) or booking)
        elif booking.get("invoice_id"):
            db.audit("site_invoice_needs_correction", f"id={booking_id} amount={amount}",
                     owner_user_id=owner)
    _mail_cancelled(booking_site.get(booking_id) or booking, amount, by_host)
    return {"error": None, "refund_czk": amount}


def _free_reservation(booking: Dict[str, Any]) -> None:
    if not booking.get("reservation_id"):
        return
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (booking["reservation_id"],))
    if row is None or row["status"] != "active":
        return
    db.update("reservation", row["id"], {"status": "cancelled", "updated_at": db.utcnow()})
    from . import icalsync

    claim.expire_on_cancel(row)
    icalsync._warn_if_guests_registered(row, int(booking["apartment_id"]), "cancelled")


def _stripe_refund(booking: Dict[str, Any], amount_czk: int) -> None:
    account = stripe_connect.account_for_owner(int(booking["owner_user_id"]))
    intent = booking.get("stripe_payment_intent_id")
    if account is None or not intent:
        raise RuntimeError(f"site booking {booking['id']}: cannot refund (no account or intent)")
    api = stripe_connect._api()
    api.v1.refunds.create(
        params={"payment_intent": intent, "amount": int(amount_czk) * 100,
                "metadata": {"site_booking_id": str(booking["id"])}},
        options={"stripe_account": account["stripe_account_id"],
                 "idempotency_key": f"site_booking_cancel_refund_{booking['id']}"},
    )


def _storno_invoice(booking: Dict[str, Any]) -> None:
    if not booking.get("invoice_id"):
        return
    from . import invoices

    try:
        invoices.cancel(int(booking["invoice_id"]),
                        host_i18n.translate("cs", "site_booking.invoice.cancel_reason"),
                        None, None, today=claim.prague_today())
    except ValueError as exc:
        log.warning("site booking %s: no storno (%s)", booking["id"], exc)
        db.audit("site_invoice_needs_correction", f"id={booking['id']} reason={exc}",
                 owner_user_id=int(booking["owner_user_id"]))


# --- mails ---------------------------------------------------------------------


def _mail_cancelled(booking: Dict[str, Any], amount: int, by_host: bool) -> None:
    apartment = booking_webhook._apartment(booking)
    host_email = booking_webhook._host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = booking_webhook._facts(booking, apartment, lang)
    facts["refund"] = amount
    if by_host:
        guest_key = "site_booking.mail.cancel_guest_by_host"
    elif amount > 0:
        guest_key = "site_booking.mail.cancel_guest_refund"
    else:
        guest_key = "site_booking.mail.cancel_guest_none"
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:cancelled",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.cancel_subject", **facts),
            payload={"text": host_i18n.translate(lang, guest_key, **facts),
                     "lang": lang, "reply_to": host_email},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = booking_webhook._facts(booking, apartment, "cs")
        host_facts["refund"] = amount
        host_key = ("site_booking.mail.cancel_host_by_host" if by_host
                    else "site_booking.mail.cancel_host_by_guest")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_cancelled",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_cancel_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", host_key, **host_facts), "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )


def _mail_refund_failed(booking: Dict[str, Any]) -> None:
    apartment = booking_webhook._apartment(booking)
    host_email = booking_webhook._host_email(apartment)
    if not host_email:
        return
    facts = booking_webhook._facts(booking, apartment, "cs")
    mail.enqueue(
        kind="site_booking_host",
        idempotency_key=f"site_booking:{booking['id']}:refund_failed",
        to_email=host_email,
        subject=host_i18n.translate("cs", "site_booking.mail.refund_failed_subject", **facts),
        payload={"text": host_i18n.translate("cs", "site_booking.mail.refund_failed_text", **facts),
                 "lang": "cs"},
        apartment_id=int(booking["apartment_id"]),
        owner_user_id=int(booking["owner_user_id"]),
    )
```

Run `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_cancel.py 2>&1 | tail -5`.

**Step 2.** Create `App/app/booking_manage.py`:

```python
"""Data for the guest booking page (brief 0821)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

from . import booking_cancel, booking_site, db, property_page

VISIBLE = ("paid", "cancelled", "refunded", "clash_refunded")


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if local and domain else ""


def day_label(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}" if lang == "cs" else iso


def deadline_label(booking: Dict[str, Any], checkin_hour: int, lang: str) -> str:
    """Until when the full refund holds; "" for a non-refundable booking."""
    moment = booking_site.check_in_moment(booking["date_from"], checkin_hour)
    policy = booking["cancellation_policy"]
    if policy == "flexible":
        moment -= timedelta(hours=24)
    elif policy == "moderate":
        moment -= timedelta(days=5)
    else:
        return ""
    if lang == "cs":
        return f"{moment.day}. {moment.month}. {moment.year} {moment:%H:%M}"
    return f"{moment:%Y-%m-%d %H:%M}"


def view(booking: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """Everything booking_manage.html prints."""
    s = booking_site.settings(int(booking["apartment_id"]))
    apartment = db.query_one("SELECT internal_name FROM apartment WHERE id = ?",
                             (booking["apartment_id"],))
    status = booking["status"]
    state = "refunded" if status == "refunded" else status
    nights = int(booking["nights"])
    can_cancel = status == "paid" and not booking_cancel.started(booking)
    return {
        "id": int(booking["id"]),
        "state": state,
        "tone": "done" if status == "paid" else "neutral",
        "name": (apartment["internal_name"] if apartment else "") or "",
        "arrive": day_label(booking["date_from"], lang),
        "depart": day_label(booking["date_to"], lang),
        "guests": int(booking["guests"]),
        "total": int(booking["total_czk"]),
        "refunded": int(booking["refunded_czk"] or 0),
        "email": mask_email(booking["guest_email"] or ""),
        "city_tax": int(s["city_tax_czk"]) * int(booking["guests"]) * nights,
        "policy": booking["cancellation_policy"],
        "deadline": deadline_label(booking, s["checkin_hour"], lang),
        "can_cancel": can_cancel,
        "refund_now": booking_cancel.refund_now(booking, by_host=False) if can_cancel else 0,
        "has_invoice": bool(booking.get("invoice_id")),
    }


def calendar_ics(booking: Dict[str, Any], name: str) -> str:
    """One all-day event for the guest's own calendar. No personal data."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    start = date.fromisoformat(booking["date_from"]).strftime("%Y%m%d")
    end = date.fromisoformat(booking["date_to"]).strftime("%Y%m%d")
    summary = (name or "").replace("\\", " ").replace(",", " ").replace(";", " ").replace("\n", " ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UbyHost//Booking//CS", "BEGIN:VEVENT",
             f"UID:ubyhost-booking-{int(booking['id'])}@ubyhost.cz", f"DTSTAMP:{stamp}",
             f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}",
             f"SUMMARY:{summary}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"

```

(`property_page` import is unused: remove it if ruff reports F401.) Run ruff as in step 1.

**Step 3.** Move the CSS. In `App/app/templates/property_page.html` cut the whole inline `<style> ... </style>` block (0818) and put it unchanged into the new file `App/app/templates/_pp_booking_css.html`, then append these rules before its closing `</style>`:

```css
.pp-bk-page { max-width: 520px; margin: var(--space-6) auto; padding: 0 var(--space-4); }
.pp-bk h1 { margin: 0; font-size: var(--size-22); line-height: 1.25; }
.pp-bk-head { display: flex; flex-direction: column; gap: var(--space-2); }
.pp-bk-badge { align-self: flex-start; border-radius: var(--radius-pill); padding: 3px 10px; font-size: var(--size-12); font-weight: 700; background: var(--st-done-bg); color: var(--st-done-ink); }
.pp-bk-badge[data-tone="neutral"] { background: var(--surface-2); color: var(--ink-2); }
.pp-bk-refund { background: var(--surface-2); border-radius: var(--radius-2); padding: var(--space-3); margin: 0; }
.pp-bk-card summary { display: flex; align-items: center; min-height: 44px; cursor: pointer; font-weight: 700; }
.pp-bk-actions { display: flex; flex-direction: column; gap: var(--space-2); }
```

In `property_page.html` put `{% include "_pp_booking_css.html" %}` where the block was (inside `head_extra`, after the `noindex` meta line). Check the tokens used here exist: `grep -c -- '--radius-pill:\|--st-done-bg:\|--st-done-ink:\|--surface-2:' app/static/tokens.css` must be at least 4 (one line may hold several; if a name is missing, STOP). Run `.venv/bin/python -m pytest tests/test_booking_site_page.py tests/test_property_page.py -q --tb=short -x 2>&1 | tail -15` (0818 tests) to prove the move changed nothing.

**Step 4.** `App/app/host_i18n.py`: keys. Anchor `grep -nF '"site_booking.invoice.note"' app/host_i18n.py` (0820; two hits: English, then Czech). Insert English after the first, Czech after the second. If `site_booking.invoice.note` is missing, 0820 is not merged: STOP.

English:

```python
        "site_booking.invoice.cancel_reason": "Booking cancelled, payment refunded",
        "site_booking.mail.cancel_subject": "Booking cancelled: %(property)s, %(dates)s",
        "site_booking.mail.cancel_guest_refund": "Hello %(name)s,\n\nyour booking of %(property)s for %(dates)s is cancelled. We refund %(refund)s CZK to your card; banks usually show it within 5 to 10 days.\n\nAnswer this e-mail to reach your host.",
        "site_booking.mail.cancel_guest_none": "Hello %(name)s,\n\nyour booking of %(property)s for %(dates)s is cancelled. Under the cancellation terms nothing is refunded.\n\nAnswer this e-mail to reach your host.",
        "site_booking.mail.cancel_guest_by_host": "Hello %(name)s,\n\nwe are sorry: the host had to cancel your booking of %(property)s for %(dates)s. You get the full %(refund)s CZK back to your card; banks usually show it within 5 to 10 days.\n\nAnswer this e-mail to reach your host.",
        "site_booking.mail.host_cancel_subject": "Booking cancelled: %(property)s, %(dates)s",
        "site_booking.mail.cancel_host_by_guest": "The guest cancelled a booking from your website.\n\nPlace: %(property)s\nDates: %(dates)s\nGuest: %(name)s, %(email)s\nRefunded to the guest: %(refund)s CZK\n\nThe nights are free again.",
        "site_booking.mail.cancel_host_by_host": "You cancelled a booking from your website.\n\nPlace: %(property)s\nDates: %(dates)s\nGuest: %(name)s, %(email)s\nRefunded to the guest: %(refund)s CZK\n\nThe nights are free again.",
        "site_booking.mail.refund_failed_subject": "Refund failed: %(property)s, %(dates)s",
        "site_booking.mail.refund_failed_text": "A booking was cancelled but the refund to the guest did not go through. Nothing was lost: open the booking site page and tap the refund button again.\n\nGuest: %(name)s, %(email)s",
        "bk.badge.paid": "Paid",
        "bk.badge.cancelled": "Cancelled",
        "bk.badge.refunded": "Cancelled",
        "bk.badge.clash_refunded": "Refunded",
        "bk.h1.paid": "Booking confirmed",
        "bk.h1.cancelled": "Booking cancelled",
        "bk.h1.refunded": "Booking cancelled",
        "bk.h1.clash_refunded": "Booking not confirmed",
        "bk.sub.paid": "We sent the confirmation to %(email)s.",
        "bk.sub.cancelled": "Under the cancellation terms nothing is refunded.",
        "bk.sub.refunded": "We refunded %(refund)s CZK to your card.",
        "bk.sub.clash_refunded": "The dates were taken a moment before your payment arrived. We refunded the full amount.",
        "bk.arrive": "Arrival",
        "bk.depart": "Departure",
        "bk.guests": "Guests",
        "bk.paid": "Paid",
        "bk.city_tax": "City tax %(amount)s CZK is paid on site.",
        "bk.policy.non_refundable": "No refund after payment.",
        "bk.policy.flexible": "Full refund until %(when)s.",
        "bk.policy.moderate": "Full refund until %(when)s. After that half of the accommodation without the cleaning fee.",
        "bk.refund_now": "If you cancel now, we refund %(amount)s CZK to your card.",
        "bk.refund_none": "If you cancel now, nothing is refunded.",
        "bk.cancel.open": "Cancel the booking",
        "bk.cancel.confirm": "Cancel for good? This cannot be undone.",
        "bk.cancel.button": "Yes, cancel the booking",
        "bk.invoice": "Invoice (PDF)",
        "bk.calendar": "Add to calendar",
        "bk.link_note": "The link to this page is also in your e-mail.",
        "bk.err.started": "The stay has started, so it can no longer be cancelled here. Write to your host.",
        "bk.err.busy": "The booking is being changed. Try again in a moment.",
        "bk.err.refund_failed": "The booking is cancelled, but the refund did not go through yet. The host was told and will repeat it.",
```

Czech:

```python
        "site_booking.invoice.cancel_reason": "Zrušení rezervace, vrácení platby",
        "site_booking.mail.cancel_subject": "Rezervace zrušena: %(property)s, %(dates)s",
        "site_booking.mail.cancel_guest_refund": "Dobrý den, %(name)s,\n\nvaše rezervace %(property)s na %(dates)s je zrušená. Vracíme vám %(refund)s Kč na kartu; banka je obvykle připíše do 5 až 10 dnů.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel.",
        "site_booking.mail.cancel_guest_none": "Dobrý den, %(name)s,\n\nvaše rezervace %(property)s na %(dates)s je zrušená. Podle storno podmínek se nic nevrací.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel.",
        "site_booking.mail.cancel_guest_by_host": "Dobrý den, %(name)s,\n\nomlouváme se: hostitel musel vaši rezervaci %(property)s na %(dates)s zrušit. Celých %(refund)s Kč se vám vrací na kartu; banka je obvykle připíše do 5 až 10 dnů.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel.",
        "site_booking.mail.host_cancel_subject": "Rezervace zrušena: %(property)s, %(dates)s",
        "site_booking.mail.cancel_host_by_guest": "Host zrušil rezervaci z vašeho webu.\n\nUbytování: %(property)s\nTermín: %(dates)s\nHost: %(name)s, %(email)s\nVráceno hostovi: %(refund)s Kč\n\nNoci jsou zase volné.",
        "site_booking.mail.cancel_host_by_host": "Zrušili jste rezervaci z vašeho webu.\n\nUbytování: %(property)s\nTermín: %(dates)s\nHost: %(name)s, %(email)s\nVráceno hostovi: %(refund)s Kč\n\nNoci jsou zase volné.",
        "site_booking.mail.refund_failed_subject": "Vrácení platby se nepovedlo: %(property)s, %(dates)s",
        "site_booking.mail.refund_failed_text": "Rezervace je zrušená, ale vrácení platby hostovi neproběhlo. Nic se neztratilo: otevřete stránku rezervačního webu a klepněte na vrácení platby znovu.\n\nHost: %(name)s, %(email)s",
        "bk.badge.paid": "Zaplaceno",
        "bk.badge.cancelled": "Zrušeno",
        "bk.badge.refunded": "Zrušeno",
        "bk.badge.clash_refunded": "Vráceno",
        "bk.h1.paid": "Rezervace potvrzena",
        "bk.h1.cancelled": "Rezervace zrušena",
        "bk.h1.refunded": "Rezervace zrušena",
        "bk.h1.clash_refunded": "Rezervace nepotvrzena",
        "bk.sub.paid": "Potvrzení jsme poslali na %(email)s.",
        "bk.sub.cancelled": "Podle storno podmínek se nic nevrací.",
        "bk.sub.refunded": "Vrátili jsme vám %(refund)s Kč na kartu.",
        "bk.sub.clash_refunded": "Termín byl těsně před vaší platbou obsazený. Vrátili jsme celou částku.",
        "bk.arrive": "Příjezd",
        "bk.depart": "Odjezd",
        "bk.guests": "Hosté",
        "bk.paid": "Zaplaceno",
        "bk.city_tax": "Městský poplatek %(amount)s Kč zaplatíte na místě.",
        "bk.policy.non_refundable": "Po zaplacení se nic nevrací.",
        "bk.policy.flexible": "Do %(when)s vracíme celou částku.",
        "bk.policy.moderate": "Do %(when)s vracíme celou částku. Poté polovinu ubytování bez úklidu.",
        "bk.refund_now": "Při zrušení dnes vrátíme %(amount)s Kč na kartu.",
        "bk.refund_none": "Při zrušení dnes se nic nevrací.",
        "bk.cancel.open": "Zrušit rezervaci",
        "bk.cancel.confirm": "Opravdu zrušit? Zpět to nejde.",
        "bk.cancel.button": "Ano, zrušit rezervaci",
        "bk.invoice": "Faktura (PDF)",
        "bk.calendar": "Přidat do kalendáře",
        "bk.link_note": "Odkaz na tuto stránku je i v e-mailu.",
        "bk.err.started": "Pobyt už začal, proto ho tady nejde zrušit. Napište hostiteli.",
        "bk.err.busy": "S rezervací se právě pracuje. Zkuste to za chvíli.",
        "bk.err.refund_failed": "Rezervace je zrušená, ale vrácení platby zatím neproběhlo. Hostitel o tom ví a zopakuje ho.",
```

Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_mail_golden.py tests/test_notification_copy.py tests/test_guest_mail.py -q --tb=short -x 2>&1 | tail -15`.

**Step 5.** `App/app/routes/property_page.py`: directly before the `@router.get("/p/{slug}/thanks")` line (and after the 0820 invoice route) add the three guest routes. Imports: add `booking_cancel, booking_manage` to the `from .. import (...)` list (0818 form).

```python
def _booking_or_none(booking_id: int, token: str):
    if not booking_site.token_ok(booking_id, token):
        return None
    booking = booking_site.get(booking_id)
    if booking is None or booking["status"] not in booking_manage.VISIBLE:
        return None
    return booking


def _manage_lang(request: Request, booking) -> str:
    value = request.query_params.get("lang")
    if value in ("cs", "en"):
        return value
    return booking["lang"] if booking["lang"] in ("cs", "en") else "cs"


def _manage_throttle(request: Request, scope: str):
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    return None


@router.get("/p/{slug}/b/{booking_id}/{token}")
def booking_manage_page(request: Request, slug: str, booking_id: int, token: str):
    """0821: the guest's private booking page (signed link from the e-mail)."""
    slow = _manage_throttle(request, "booking_manage")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None:
        return Response(status_code=404)
    lang = _manage_lang(request, booking)
    error = request.query_params.get("e", "")
    response = render(request, "booking_manage.html", {
        "show_nav": False, "lang": lang, "slug": slug, "token": token,
        "v": booking_manage.view(booking, lang),
        "error": error if error in ("started", "busy", "refund_failed") else "",
    })
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@router.post("/p/{slug}/b/{booking_id}/{token}/cancel")
def booking_manage_cancel(request: Request, slug: str, booking_id: int, token: str):
    slow = _manage_throttle(request, "booking_cancel")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None:
        return Response(status_code=404)
    result = booking_cancel.cancel(booking_id, by_host=False)
    lang = _manage_lang(request, booking)
    query = {"lang": lang}
    if result["error"] in ("started", "busy", "refund_failed"):
        query["e"] = result["error"]
    return RedirectResponse(f"/p/{slug}/b/{booking_id}/{token}?{urlencode(query)}", status_code=303)


@router.get("/p/{slug}/b/{booking_id}/{token}/calendar.ics")
def booking_manage_calendar(request: Request, slug: str, booking_id: int, token: str):
    slow = _manage_throttle(request, "booking_manage")
    if slow:
        return slow
    booking = _booking_or_none(booking_id, token)
    if booking is None or booking["status"] != "paid":
        return Response(status_code=404)
    name = (db.query_one("SELECT internal_name FROM apartment WHERE id = ?",
                         (booking["apartment_id"],)) or {"internal_name": ""})["internal_name"]
    return Response(
        booking_manage.calendar_ics(booking, name).encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex",
                 "Content-Disposition": 'attachment; filename="stay.ics"'},
    )
```

(The redirect stays on `/p/`; a POST never redirects off-site.) Ruff as in step 1 on this file.

**Step 6.** Create `App/app/templates/booking_manage.html`. Only existing component classes (`ui-btn`, `ui-btn-secondary`, `ui-btn-danger`, `ui-sub`) and the `pp-bk-*` classes of the partial. Mapping from `Guest.dc.html`: badge, h1 and sub line = `pp-bk-head`; white cards = `pp-bk-card`; grey refund box = `pp-bk-refund`; outlined red button = `ui-btn ui-btn-danger`; grey outlined buttons = `ui-btn ui-btn-secondary`.

```html
{% extends "base.html" %}
{% block title %}{{ t('bk.h1.' ~ v.state) }} · {{ v.name }}{% endblock %}
{% block head_extra %}
<meta name="robots" content="noindex">
{% include "_pp_booking_css.html" %}
{% endblock %}
{% block content %}
{% macro money(n) %}{{ ('{:,}'.format(n) | replace(',', '&nbsp;')) | safe }}&nbsp;{{ t('payments.czk') }}{% endmacro %}
{% set base = '/p/' ~ slug ~ '/b/' ~ v.id ~ '/' ~ token %}
<main class="pp-bk pp-bk-page">
  <div class="pp-bk-head">
    <span class="pp-bk-badge" data-tone="{{ v.tone }}">{{ t('bk.badge.' ~ v.state) }}</span>
    <h1>{{ t('bk.h1.' ~ v.state) }}</h1>
    <p class="pp-bk-note">{{ t('bk.sub.' ~ v.state, email=v.email, refund=v.refunded) }}</p>
  </div>
  {% if error %}<p class="pp-bk-error" role="alert">{{ t('bk.err.' ~ error) }}</p>{% endif %}

  <section class="pp-bk-card">
    <h2>{{ v.name }}</h2>
    <div class="pp-bk-row"><span class="pp-bk-note">{{ t('bk.arrive') }}</span><span>{{ v.arrive }}</span></div>
    <div class="pp-bk-row"><span class="pp-bk-note">{{ t('bk.depart') }}</span><span>{{ v.depart }}</span></div>
    <div class="pp-bk-row"><span class="pp-bk-note">{{ t('bk.guests') }}</span><span>{{ v.guests }}</span></div>
    <div class="pp-bk-row pp-bk-total"><span>{{ t('bk.paid') }}</span><span>{{ money(v.total) }}</span></div>
    {% if v.city_tax %}<p class="pp-bk-note">{{ t('bk.city_tax', amount=v.city_tax) }}</p>{% endif %}
  </section>

  <section class="pp-bk-card">
    <h2>{{ t('pp.book.policy_title', name=t('pp.book.policy_name.' ~ v.policy)) }}</h2>
    <p class="pp-bk-note">{{ t('bk.policy.' ~ v.policy, when=v.deadline) }}</p>
    {% if v.can_cancel %}
    <p class="pp-bk-refund">{% if v.refund_now %}{{ t('bk.refund_now', amount=v.refund_now) }}{% else %}{{ t('bk.refund_none') }}{% endif %}</p>
    <details>
      <summary>{{ t('bk.cancel.open') }}</summary>
      <form method="post" action="{{ base }}/cancel?lang={{ lang }}" class="pp-bk-actions">
        <p class="pp-bk-note">{{ t('bk.cancel.confirm') }}</p>
        <button class="ui-btn ui-btn-danger" type="submit">{{ t('bk.cancel.button') }}</button>
      </form>
    </details>
    {% endif %}
  </section>

  <div class="pp-bk-actions">
    {% if v.has_invoice %}<a class="ui-btn ui-btn-secondary" href="{{ base }}/invoice.pdf" data-no-prefetch>{{ t('bk.invoice') }}</a>{% endif %}
    {% if v.state == 'paid' %}<a class="ui-btn ui-btn-secondary" href="{{ base }}/calendar.ics" data-no-prefetch>{{ t('bk.calendar') }}</a>{% endif %}
  </div>
  <p class="pp-bk-fine">{{ t('bk.link_note') }}</p>
  <nav class="pp-bk-lang" aria-label="{{ t('pp.lang.label') }}">
    <a href="{{ base }}?lang=cs" hreflang="cs" lang="cs"{% if lang == 'cs' %} aria-current="true"{% endif %}>CS</a>
    <a href="{{ base }}?lang=en" hreflang="en" lang="en"{% if lang == 'en' %} aria-current="true"{% endif %}>EN</a>
  </nav>
</main>
{% endblock %}
```

Two notes: (a) the `/cancel` POST redirects with `?lang=` already; the form action may carry the query string. (b) `pp.book.policy_title`, `pp.book.policy_name.*` and `pp.lang.label` come from 0818.

**Step 7.** Tests. Create `App/tests/test_booking_cancel.py`. Fixture and cleanup: copy `tests/test_booking_invoice.py` (0820: apartment with legal entity and Stripe account, webhook-confirmed booking helper) and its fake Stripe client, extended with a `_FakeRefunds` like the one in `tests/test_booking_webhook.py` (it records `params` and `options`; make it raise when `fail` is True). Add the 0818 `host_i18n` cookie `en` on the `TestClient`. A helper `_paid(policy, lang="en", date_from="2027-06-10", date_to="2027-06-13")` saves the settings with that policy and returns a confirmed booking id. Tests:

1. `test_guest_cancel_full_refund_frees_the_dates`: moderate, far ahead: `cancel(id, by_host=False)` returns `refund_czk == total`; Stripe got one refund with `amount == total * 100`, `options["stripe_account"]`, `idempotency_key == f"site_booking_cancel_refund_{id}"`; status `refunded`, `refunded_czk == total`; the reservation is `cancelled`; `property_page.dates_available(aid, date_from, date_to)` is True; two outbox rows (`site_booking_refunded`, `site_booking_host`) with the amount in the text. A second `cancel` returns `not_cancellable` and Stripe still has one refund.
2. `test_non_refundable_cancels_without_a_refund`: status `cancelled`, `refunded_czk == 0`, no Stripe call, guest mail says nothing is refunded, dates free.
3. `test_partial_refund_moderate_late`: pass `now=` 2 days before check-in: amount is cleaning + half of the accommodation (`booking_site.refund_czk` is the authority; assert equality with it); status `refunded`; an `audit` row `site_invoice_needs_correction` exists when the booking has an invoice.
4. `test_host_cancel_is_always_full`: non_refundable, `by_host=True`: amount equals `total`; host mail text uses the "by host" wording.
5. `test_failed_refund_keeps_cancelled_and_retry_refunds_once`: Stripe raises: result `refund_failed`, status `cancelled`, `refunded_czk == 0`, a host mail `refund_failed`; reservation already cancelled; then Stripe works and `cancel(id, by_host=True)` (the retry) refunds once with the SAME stored amount and key, status `refunded`; a further call refunds nothing.
6. `test_guest_cannot_cancel_after_check_in_starts`: `now=` after check-in: `{"error": "started"}`, status still `paid`; `by_host=True` still works.
7. `test_full_refund_issues_the_invoice_storno`: with an invoice from 0820, after a full refund the `invoice` table has a second row for the stay with `kind` `storno` or `corrective`.
8. `test_guest_page_routes`: GET the page by the signed link: 200, `no-store`, `noindex`, shows the property name, the masked e-mail (`j***@`), no full e-mail, `Cancel the booking`; a wrong token, a wrong id and a pending booking are 404; `?lang=cs` shows `Zrušit rezervaci`; the `.ics` is `text/calendar` with `DTSTART;VALUE=DATE:20270610`; POST `/cancel` is 303 to the page and the page then shows `Booking cancelled`.

Run `cd App && .venv/bin/python -m pytest tests/test_booking_cancel.py -q --tb=short -x 2>&1 | tail -30`. Fix once if red.

**Step 8.** Browser test and screenshots. Create `App/tests/test_booking_manage_browser.py` (copy the server, `_launch` and `sync_api` approach from `tests/test_booking_site_page_browser.py` of 0818; seed a confirmed booking through the webhook helper of `test_booking_invoice.py`, or insert a `site_booking` row with status `paid` and an active reservation directly). A test per width (360, 390, 1280) opens the guest page `?lang=cs` and asserts: no horizontal scroll; every `.ui-btn`, `summary` and `.pp-bk-lang a` at least 44 px high; the badge text is `Zaplaceno`; with `java_script_enabled=False`, clicking the `summary` reveals the danger button (`details[open]`) and submitting it lands on a page whose badge says `Zrušeno`. At 390 save the full-page screenshot of the guest page (paid state, `<details>` closed) to `docs/tasks/screenshots-0821/guest-390.png`.

**Step 9.** Notes and docs. Append to `docs/context/decisions.md`:

```
- 2026-11-02 | Booking site cancel: guest self-cancel via signed link, refund per policy; host cancel refunds in full | owner | 0821
```

Append to `docs/context/known-issues.md`:

```
- K-BS01: a partial refund of a site booking leaves the original invoice uncorrected (audit `site_invoice_needs_correction`); the host issues the corrective document by hand. Door codes of a cancelled site stay follow the normal stay rules (not tested here).
```

**Step 10.** Run §6. Look at the screenshot once with the Read tool and compare with `Guest.dc.html`: badge and h1, the policy card with the grey refund box and the closed "Zrušit rezervaci" row, the two grey buttons. Write the report.

## 5. Do not touch

`App/app/booking_site.py` (the rules and the state machine), `booking_checkout.py`, `booking_webhook.py` (only imported from), `booking_ical.py`, `invoices.py`, `stripe_connect.py`, `icalsync.py` (its private helper is only called), `claim.py`, `db.py`, migrations, every file under `static/`, the other public templates. Hard rules 2 (no third-party script, no tracking cookie), 3, 4, 5, 6, 7, 9.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_cancel.py app/booking_manage.py app/routes/property_page.py tests/test_booking_cancel.py tests/test_booking_manage_browser.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_cancel.py tests/test_booking_invoice.py tests/test_booking_webhook.py tests/test_booking_site.py tests/test_booking_checkout.py tests/test_booking_ical.py tests/test_booking_site_page.py tests/test_booking_calendar.py tests/test_property_page.py tests/test_property_page_meta.py tests/test_stripe_connect.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_mail_golden.py tests/test_notification_copy.py tests/test_guest_mail.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_manage_browser.py tests/test_booking_site_page_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`. Any skipped browser test is a failure: report `blocked`.

## 7. Acceptance

- [x] The three §6 runs pass; the browser run shows `0 skipped`.
- [x] `grep -n "refunds.create" App/app/booking_cancel.py` shows `options=` with `stripe_account` and `idempotency_key`, and `params` without `stripe_account`.
- [x] After a guest cancel the nights are bookable again (test 1) and a second click refunds nothing (test 1).
- [x] A failed refund never loses the booking and never refunds twice (test 5).
- [x] `grep -nE 'style=|#[0-9a-fA-F]{3,8}\b' App/app/templates/booking_manage.html App/app/templates/_pp_booking_css.html` prints nothing.
- [x] `git diff --stat origin/main` lists only the §3 files.
- [x] One 390 px screenshot of the guest page at `docs/tasks/screenshots-0821/guest-390.png`, named in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; `site_booking.invoice.note` (0820) or `pp.book.policy_name.moderate` (0818) is missing in `host_i18n.py` (those briefs are not merged); the inline `<style>` block cannot be found in `property_page.html`; a test fails twice; the browser run skips anything or Chromium is missing; you reach 25 tool calls or about 50k tokens (report as `blocked`, list steps done; steps 8 and 9 are the usual ones to hand over); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0821-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the three deviations from §1, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

- `booking_cancel.py`: money. Order is status `cancelled` first (a double click loses at `set_status`), intended amount stored, reservation freed, then the Stripe refund with one key per booking. A crash between "cancelled" and the refund leaves a `cancelled` booking with refund open: the host list (0822) offers "Zopakovat vrácení platby" and the retry uses the stored amount. Stripe idempotency keys expire after 24 h: a retry later than that with the same key creates a new refund; the `refunded` status and `refunded_czk` guard against doing it twice in our data, and the host list (0822) only offers the retry while `refunded_czk` is 0. Check the Stripe dashboard before pressing it after a day.
- The guest cancel is a capability link: anyone holding the e-mail can cancel. 404 for every failure, rate limited, no personal data beyond the masked e-mail and the host-chosen property name on the page.
- `_free_reservation` calls `icalsync._warn_if_guests_registered` (private) so the host gets the same alert as for a calendar cancellation when guest forms exist. A stay already reported to the police is not handled here (same gap as a manual cancellation); door-code behaviour follows the stay status.
- The invoice storno for a full refund is best effort; a partial refund needs a corrective document the host issues by hand (K-BS01).
- The CSS move touches `property_page.html` (0818); `test_booking_site_page.py` covers it.

## Owner steps

1. Merge when CI is green.
2. Nothing to click in Stripe for this brief (refunds are made by us). The host side (cancel button and list) is 0822; test the whole flow end to end in test mode after 0822.
