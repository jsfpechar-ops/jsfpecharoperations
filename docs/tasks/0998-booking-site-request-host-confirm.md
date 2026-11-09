# 0998: Booking site "request to book", part 3 of 3: host confirms and marks paid

Status: todo
Depends on: 0996 and 0997 merged | Base commit: <sha of main after 0997> | Branch: task/0998-request-host-confirm
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host sees open requests in the existing booking list on the booking-site page, and can "Confirm and mark paid" (creates the reservation, mails the guest) or "Decline" (frees the dates). A direct booking is cancelled by the host only and never refunds automatically. The host is mailed when a request arrives.

## 2. Context

Rules: AGENTS.md 1-10 (rule 10: host page, UX gate applies). UbyPort filing correctness (rule 1): the reservation is created exactly as the Stripe path does, so guest registration and filing are unchanged; read nothing else of UbyPort. No new personal-data field, no new outbound request (existing `mail.enqueue`), no new dependency.

State after 0996/0997 (verify by grep, STOP if missing): `booking_site` status `requested` with `requested -> paid | expired | cancelled` and `expired -> paid`; `site_booking.pay_method` / `request_expires_at`; `booking_checkout.start_direct` and `expire_requests`.

Today, `App/app/booking_webhook.py` `_confirm` creates the reservation (excerpt, must match):
```python
                "INSERT INTO reservation (apartment_id, source, uid, date_from, date_to,"
                " summary, expected_guests_override, guest_email, status, created_at, updated_at)"
                " VALUES (?, 'site', ?, ?, ?, ?, ?, ?, 'active', ?, ?) RETURNING id",
```
under `db.lock_key(cur, "booking_site_dates", apartment_id)` with a clash check against active reservations, then `UPDATE site_booking SET status = 'paid', reservation_id = ?, ... paid_at = ?`, deletes the hold, audits `site_booking_paid`, and calls `_mail_confirmed(booking, reservation_id)`.

`App/app/booking_cancel.py` `cancel`: for a `paid` booking it computes `amount = refund_now(booking, by_host=by_host, now=now)`, sets `cancelled`, frees the reservation (`_free_reservation`), then `if amount > 0:` calls `_stripe_refund`. `App/app/booking_manage.py`: `VISIBLE = ("paid", "cancelled", "refunded", "clash_refunded")`; `host_rows` selects only those statuses and returns `can_cancel = b["status"] == "paid"`; `view()` sets `can_cancel = status == "paid" and not booking_cancel.started(booking)`. The list renders in `templates/booking_site_setup.html` (loop `{% for b in bookings %}`, status badge via `bsite.bookings.status.<status>`, cancel form to `/apartments/{id}/booking-site/cancel`). Host routes live in `routes/payments.py` next to `booking_site_cancel` (use `_bsite_apartment`, `_back`, `_flash`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/booking_direct.py | create | `confirm`, `decline`, `notify_request` |
| App/app/booking_checkout.py | edit | call `notify_request` at the end of `start_direct` |
| App/app/booking_cancel.py | edit | direct bookings: refund 0, no Stripe, no invoice storno; guest cannot cancel |
| App/app/booking_manage.py | edit | `host_rows` shows `requested`/`expired` direct rows with actions; guest `view` hides cancel for direct |
| App/app/routes/payments.py | edit | `POST .../booking-site/confirm` and `.../decline` |
| App/app/templates/booking_site_setup.html | edit | action buttons in the booking list |
| App/app/host_i18n.py | edit | EN and CS keys |
| App/tests/test_booking_direct_0998.py | create | tests |

No other file may change.

## 4. Steps

Commit after each step: `0998 step k`. Grep each anchor with `grep -nF` first.

**Step 1.** Create `App/app/booking_direct.py`:

```python
"""Host confirmation of a direct booking request (brief 0998).

The guest paid the host outside the platform (IBAN, Revolut, cash). The host
marks it paid by hand; only then is the reservation created. Nothing here
talks to Stripe and nothing is refunded automatically.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from . import booking_site, config, db, host_i18n, mail

log = logging.getLogger(__name__)


def confirm(booking_id: int, owner_user_id: int) -> Dict[str, Any]:
    """{"error": None} or {"error": not_found | not_confirmable | taken}.
    A request that expired can still be confirmed while its dates are free."""
    booking = booking_site.get(booking_id)
    if (booking is None or int(booking["owner_user_id"]) != owner_user_id
            or booking["pay_method"] != "direct"):
        return {"error": "not_found"}
    now = db.utcnow()
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute("SELECT status FROM site_booking WHERE id = ?", (booking_id,))
        live = cur.fetchone()
        if live is None or live["status"] not in ("requested", "expired"):
            return {"error": "not_confirmable"}
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (booking["apartment_id"], booking["date_to"], booking["date_from"]),
        )
        if cur.fetchone() is not None:
            return {"error": "taken"}
        cur.execute(
            "SELECT id FROM booking_hold WHERE apartment_id = ? AND expires_at > ?"
            " AND date_from < ? AND date_to > ? AND id != ?",
            (booking["apartment_id"], now, booking["date_to"], booking["date_from"],
             booking["hold_id"] or 0),
        )
        if cur.fetchone() is not None:  # another request holds these nights
            return {"error": "taken"}
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
            "UPDATE site_booking SET status = 'paid', reservation_id = ?, paid_at = ?,"
            " updated_at = ? WHERE id = ? AND status IN ('requested', 'expired')",
            (reservation_id, now, now, booking_id),
        )
        if booking["hold_id"]:
            cur.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    db.audit("site_booking_paid", f"id={booking_id} reservation={reservation_id} direct",
             owner_user_id=owner_user_id)
    from . import booking_webhook  # same guest mail as a Stripe booking

    booking_webhook._mail_confirmed(booking_site.get(booking_id) or booking, reservation_id)
    return {"error": None}


def decline(booking_id: int, owner_user_id: int) -> Dict[str, Any]:
    """The host refuses a request: it becomes `cancelled` and the dates are freed."""
    booking = booking_site.get(booking_id)
    if (booking is None or int(booking["owner_user_id"]) != owner_user_id
            or booking["pay_method"] != "direct"):
        return {"error": "not_found"}
    if booking["status"] != "requested":
        return {"error": "not_confirmable"}
    if not booking_site.set_status(booking_id, "cancelled", cancelled_at=db.utcnow()):
        return {"error": "not_confirmable"}
    if booking["hold_id"]:
        db.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    db.audit("site_booking_declined", f"id={booking_id}", owner_user_id=owner_user_id)
    return {"error": None}


def notify_request(booking: Dict[str, Any]) -> None:
    """One short mail to the host: a request is waiting. Best effort."""
    try:
        from . import booking_webhook

        apartment = booking_webhook._apartment(booking)
        host_email = booking_webhook._host_email(apartment)
        if not host_email:
            return
        facts = booking_webhook._facts(booking, apartment, "cs")
        facts["link"] = (f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                         f"/apartments/{int(booking['apartment_id'])}/booking-site")
        mail.enqueue(
            kind="site_booking_request_host",
            idempotency_key=f"site_booking:{booking['id']}:request_host",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.request_subject", **facts),
            payload={"text": host_i18n.translate("cs", "site_booking.mail.request_text", **facts),
                     "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: request mail failed", booking.get("id"))
```
Before writing, run `grep -n "def enqueue" -A12 App/app/mail.py | head -20` and confirm `reservation_id` is optional (it is omitted in `notify_request`); if it is required, STOP. Command: `cd App && .venv/bin/python -c "from app import booking_direct" 2>&1 | tail -30`.

**Step 2.** `booking_checkout.py` `start_direct`: replace the line `return {"booking": booking}` with
```python
    from . import booking_direct

    booking_direct.notify_request(booking)
    return {"booking": booking}
```

**Step 3.** `booking_cancel.py` `cancel`: (a) after the line `amount = refund_now(booking, by_host=by_host, now=now)` (inside the `paid` branch) insert
```python
        if booking.get("pay_method") == "direct":
            amount = 0  # paid outside the platform: the host settles any refund by hand
```
(b) first statement after the `if booking is None:` block: 
```python
    if booking.get("pay_method") == "direct" and not by_host:
        return {"error": "not_cancellable"}
```
Anything below that uses `amount > 0` then skips Stripe and the invoice storno by itself. Confirm by reading the lines after `if amount > 0:` (they are the Stripe refund block); STOP if `_mail_cancelled` would print a refund sentence for amount 0 in a misleading way: read `_mail_cancelled` (`grep -n "def _mail_cancelled" -A25 App/app/booking_cancel.py | head -40`) and report if the text says "refunded".

**Step 4.** `booking_manage.py`. (a) In `host_rows` replace the status filter `status IN ('paid', 'cancelled', 'refunded', 'clash_refunded')` with `status IN ('requested', 'expired', 'paid', 'cancelled', 'refunded', 'clash_refunded')` and, to keep old Stripe `expired` rows out, add `AND (status != 'expired' OR pay_method = 'direct')` after it. (b) In the dict returned per row add:
```python
            "direct": b["pay_method"] == "direct",
            "can_confirm": b["pay_method"] == "direct" and b["status"] in ("requested", "expired"),
            "can_decline": b["pay_method"] == "direct" and b["status"] == "requested",
```
(c) In `view()` change `can_cancel = status == "paid" and not booking_cancel.started(booking)` to `can_cancel = (status == "paid" and booking.get("pay_method") != "direct" and not booking_cancel.started(booking))`. Do not touch `VISIBLE` (the guest page must not show a `requested` row without a design; it is out of scope: the guest has no manage link for requests).

**Step 5.** `routes/payments.py`: add below `booking_site_cancel`:

```python
async def _direct_action(request: Request, apartment_id: int, action: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_direct, booking_site

    here = f"/apartments/{apartment_id}/booking-site"
    form = await request.form()
    raw = str(form.get("booking_id") or "")
    booking = booking_site.get(int(raw)) if raw.isdigit() else None
    if booking is None or int(booking["apartment_id"]) != apartment_id:
        return Response(status_code=404)
    result = getattr(booking_direct, action)(int(booking["id"]), owner_id)
    if result["error"] == "not_found":
        return Response(status_code=404)
    if result["error"] == "taken":
        return _back(here, err=_flash(request, "bsite.err.direct_taken"))
    if result["error"]:
        return _back(here, err=_flash(request, "bsite.err.not_cancellable"))
    return _back(here, msg=_flash(request, "bsite.flash.direct_" + action))


@router.post("/apartments/{apartment_id}/booking-site/confirm")
async def booking_site_confirm(request: Request, apartment_id: int):
    return await _direct_action(request, apartment_id, "confirm")


@router.post("/apartments/{apartment_id}/booking-site/decline")
async def booking_site_decline(request: Request, apartment_id: int):
    return await _direct_action(request, apartment_id, "decline")
```
Command: `cd App && .venv/bin/python -c "import app.routes.payments" 2>&1 | tail -30`.

**Step 6.** `templates/booking_site_setup.html`, in the booking list loop: after the status badge line add, for rows with `b.direct`, nothing extra; and next to the existing cancel `<form>` (keep its `{% if b.can_cancel %}` condition) add two sibling forms:
```jinja
        {% if b.can_confirm %}
        <form method="post" action="/apartments/{{ apartment.id }}/booking-site/confirm" data-confirm data-confirm-message="{{ t('bsite.bookings.confirm_paid') }}">
          <input type="hidden" name="_csrf" value="{{ csrf_token }}">
          <input type="hidden" name="booking_id" value="{{ b.id }}">
          {{ ui_button(t('bsite.bookings.mark_paid'), 'primary', type='submit', size='compact') }}
        </form>
        {% endif %}
        {% if b.can_decline %}
        <form method="post" action="/apartments/{{ apartment.id }}/booking-site/decline" data-confirm data-confirm-message="{{ t('bsite.bookings.confirm_decline') }}">
          <input type="hidden" name="_csrf" value="{{ csrf_token }}">
          <input type="hidden" name="booking_id" value="{{ b.id }}">
          {{ ui_button(t('bsite.bookings.decline'), 'secondary', type='submit', size='compact') }}
        </form>
        {% endif %}
```
Read lines 87-110 of the template first (`sed -n 87,110p`) to match the surrounding markup and the cancel form's `booking_id`/csrf fields; copy their exact pattern. The status badge tone line `ui_badge('done' if b.status == 'paid' else 'neutral', ...)` stays. Change the cancel confirm text for direct rows is not needed: the existing text mentions a refund, so show for `b.direct` the key `bsite.bookings.confirm_direct` instead: `data-confirm-message="{{ t('bsite.bookings.confirm_direct' if b.direct else 'bsite.bookings.confirm') }}"`.

**Step 7.** `host_i18n.py`, EN and CS (same commit). Status labels first: `grep -n '"bsite.bookings.status' App/app/host_i18n.py` and add `bsite.bookings.status.requested` and `bsite.bookings.status.expired` if `expired` is missing. EN:
```python
        "bsite.bookings.status.requested": "Waiting for payment",
        "bsite.bookings.status.expired": "Expired",
        "bsite.bookings.mark_paid": "Confirm and mark paid",
        "bsite.bookings.decline": "Decline",
        "bsite.bookings.confirm_paid": "The guest has paid you. This books the dates and e-mails the guest.",
        "bsite.bookings.confirm_decline": "Decline this request and free the dates?",
        "bsite.bookings.confirm_direct": "Cancel this booking? Any refund is yours to send, nothing is refunded automatically.",
        "bsite.flash.direct_confirm": "Booking confirmed. The guest has an e-mail.",
        "bsite.flash.direct_decline": "Request declined. The dates are free again.",
        "bsite.err.direct_taken": "These dates are no longer free, so the request cannot be confirmed.",
        "site_booking.mail.request_subject": "New booking request: %(property)s, %(dates)s",
        "site_booking.mail.request_text": "%(name)s asks to book %(property)s, %(dates)s, %(guests)s guests, %(total)s CZK. The dates are held for 24 hours. When the guest has paid you, confirm it here: %(link)s",
```
CS (use `\u` escapes, same keys): "Čeká na platbu", "Vypršelo", "Potvrdit a označit jako zaplaceno", "Zamítnout", "Host vám zaplatil. Tím se termín rezervuje a host dostane e-mail.", "Zamítnout poptávku a uvolnit termín?", "Zrušit rezervaci? Vrácení peněz pošlete sami, automaticky se nevrací nic.", "Rezervace potvrzena. Host dostal e-mail.", "Poptávka zamítnuta. Termín je znovu volný.", "Termín už není volný, poptávku nelze potvrdit.", "Nová poptávka: %(property)s, %(dates)s", "%(name)s chce rezervovat %(property)s, %(dates)s, hosté: %(guests)s, %(total)s Kč. Termín držíme 24 hodin. Až vám host zaplatí, potvrďte to zde: %(link)s". Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`.

**Step 8.** Tests `App/tests/test_booking_direct_0998.py` (fixtures as in `test_booking_site.py`; build a `requested` direct row with `create_pending(..., status="requested", pay_method="direct", ...)` plus a `booking_hold`):
1. `test_confirm_creates_reservation`: confirm -> `paid`, one `reservation` (`source='site'`, `uid='site-<id>'`), hold deleted, guest mail queued (`kind='site_booking_confirmed'`), no Stripe call (monkeypatch `stripe_connect._api` to raise).
2. `test_confirm_twice`: second call -> `not_confirmable`, still one reservation.
3. `test_confirm_expired_if_free`: status `expired` + free dates -> confirmed; with an active reservation overlapping -> `taken`, no reservation inserted.
4. `test_confirm_other_owner_404`: route POST by another owner -> 404; no state change.
5. `test_decline_frees_dates`: `requested -> cancelled`, hold gone, same dates can be held again.
6. `test_host_cancel_direct_no_refund`: confirmed direct booking, `booking_cancel.cancel(id, by_host=True)` -> `error None`, `refund_czk == 0`, status `cancelled`, reservation cancelled, no Stripe call; `by_host=False` -> `not_cancellable`.
7. `test_request_mail_to_host`: `start_direct` queues `site_booking_request_host` once.
8. `test_host_rows_actions`: `requested` row has `can_confirm` and `can_decline`; a paid Stripe row has neither; an old Stripe `expired` row is not listed.
9. `test_setup_page_buttons`: GET the setup page with a requested row shows "Confirm and mark paid" (EN) once.
Command: `cd App && .venv/bin/python -m pytest tests/test_booking_direct_0998.py tests/test_booking_direct_0997.py tests/test_booking_direct_0996.py tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -30`.

## 5. Do not touch

`booking_webhook.py` (only imported), `booking_invoice.py`, `routes/property_page.py`, `property_page.py`, migrations, `static/*.css`, anything under `claim.py`, UbyPort/filing code. Hard rules: 1, 2, 4, 5 (SQL via `db`), 6, 9 (the "refund is yours" sentence lives only in `bsite.bookings.confirm_direct`), 10.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30` (test-map: Booking site, Direct payments):
- `.venv/bin/python -m pytest tests/test_booking_direct_0998.py tests/test_booking_direct_0997.py tests/test_booking_direct_0996.py tests/test_booking_site.py tests/test_property_page.py tests/test_stripe_connect.py tests/test_host_i18n.py -q --tb=short -x`
- UX gate (rules 7 and 10): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q -x -rs` (0 skipped, zero host findings). Open `/tmp/shots/layout-lint/<booking-site page>-{390,768,1280}.png` and look for what the rules miss (three buttons in one row on 390 px, long labels).
- Repo root: `python3 scripts/context_lint.py | tail -5` (OK).

## 7. Acceptance

- [ ] Host confirms a request: reservation exists, guest mail queued, status `paid`; a second click does nothing.
- [ ] Host declines: dates free, no reservation.
- [ ] Unconfirmed requests expire after 24 h (0997 job) and show "Expired"; confirming one is possible only while the dates are free.
- [ ] Host cancel of a direct booking: no Stripe call, no refund, reservation freed; the guest cannot cancel a direct booking.
- [ ] Old Stripe bookings behave exactly as before (existing tests pass).
- [ ] Tests in section 6 pass, 0 skipped; layout lint green; one 390 px screenshot of the booking list with a requested row (plus 768 and 1280); the PR body says per page "390: ...; 768: ...; 1280: ..." and ticks the [design-system checklist](../design/design-system.md) (rule 10; never ask the owner).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found (including 0996/0997 names in section 2);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (`blocked`);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- `mail.enqueue` needs a `reservation_id`, or `_mail_cancelled` would tell a direct guest "refunded";
- the booking list markup differs so much from step 6 that the three forms do not fit (report with the markup, do not redesign);
- an invoice for direct bookings seems required (it is out of scope: ask the owner);
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0998-report.md` (600 tokens at most), `Status: review`: files changed, each command with last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `booking_direct.confirm`: the lock, the clash check and the reservation insert must stay identical in effect to `booking_webhook._confirm` (rule 1: filing starts from this reservation).
- `booking_cancel.cancel` direct guard: no Stripe path may be reachable for `pay_method = 'direct'`.
- `booking_webhook._mail_confirmed` also mails the host "new booking" after the host just confirmed: harmless duplicate; replace with a guest-only mail only if the owner asks.
- No invoice is made for direct bookings (hosts invoice by hand): owner decision needed before the first real use.

## Owner steps

1. Review and merge with `scripts/merge-pr-on-green.sh` once CI is green.
2. After 0996, 0997 and 0998 are all merged: deploy, then on the server run `pg_schema.py apply` (migration 0038 / `00009`), as for earlier migrations.
3. Click-by-click test on staging: Booking site -> "How guests pay" -> tick Cash, Save -> Publish. Open the public page in a private window, request dates, see the payment page. Back in Booking site, press "Confirm and mark paid"; check the guest e-mail arrived.
