# 1006: Direct bookings: decline race, cancelled-row state, decline mail, host copy

Status: todo
Depends on: none (on top of PR 803) | Base commit: 6217fcc8 | Branch: task/0999-property-rules-map (same PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Round-2 review of PR 803 found four wrong host or guest outcomes for direct (pay-the-host) bookings. This brief fixes them: (a) a decline that lands just after a confirm cancels a paid booking and leaves its reservation in the calendar; (b) a declined or host-cancelled direct row shows "Cancelled, refund open" and a red "Retry refund" button that only errors; (c) the host cancel flash says "the guest is refunded" for direct bookings; (d) a declined guest is never told, although they already got the payment details by mail; (e) the host's confirm mail says "New paid booking ... Paid" for a cash booking.

## 2. Context

Rules: AGENTS.md 1-10; rule 9 (copy, EN/CS parity, no em dash, no sentence the button already says).

Reproduced in round 2 (`/mnt/project-files/pr803-review/REVIEW-round2.md`, findings N1-N4, N7).

`App/app/booking_direct.py` `decline` (current):

```python
    if booking["status"] not in ("requested", "expired"):
        return {"error": "not_confirmable"}
    try:
        moved = booking_site.set_status(booking_id, "cancelled", cancelled_at=db.utcnow())
    except ValueError:
        return {"error": "not_confirmable"}
    if not moved:
        return {"error": "not_confirmable"}
```

`set_status` allows `paid -> cancelled`, so if `confirm` runs between the check and the move, decline cancels a paid booking. `confirm` (same file, top) already shows the lock pattern to copy:

```python
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute("SELECT status FROM site_booking WHERE id = ?", (booking_id,))
        live = cur.fetchone()
        if live is None or live["status"] not in ("requested", "expired"):
            return {"error": "not_confirmable"}
```

`App/app/booking_manage.py` `host_rows`:

```python
            "can_cancel": b["status"] == "paid",
            "can_retry": b["status"] == "cancelled" and not int(b["refunded_czk"] or 0),
```

`App/app/templates/booking_site_setup.html` prints the badge with `t('bsite.bookings.status.' ~ b.status)`.

`App/app/routes/payments.py` `booking_site_cancel` ends with:

```python
    return _back(here, msg=_flash(request, "bsite.flash.cancelled"))
```

`App/app/booking_webhook.py` `_mail_confirmed` host part uses `"site_booking.mail.host_text"` ("New paid booking ... Paid: %(total)s CZK").

`App/app/booking_cancel.py` `_mail_cancelled` shows how a guest cancel mail is enqueued (kind `site_booking_refunded`, `reply_to` host e-mail); reuse that kind for the decline mail (no new kind, so `mail.KINDS` and `test_claim_mail.py` stay as they are).

If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/booking_direct.py | edit | decline under lock with CAS; guest decline mail |
| App/app/booking_manage.py | edit | `status_key`, `can_retry` only for card bookings |
| App/app/templates/booking_site_setup.html | edit | badge uses `b.status_key` |
| App/app/routes/payments.py | edit | direct flash on host cancel |
| App/app/booking_webhook.py | edit | host confirm text for direct |
| App/app/host_i18n.py | edit | 5 keys EN + CS |
| App/tests/test_booking_direct_0998.py | edit | 4 tests |

No other file may change.

## 4. Steps

1. `booking_direct.decline`: replace the block from `if booking["status"] not in ("requested", "expired"):` to `if not moved: return ...` with:

```python
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute(
            "UPDATE site_booking SET status = 'cancelled', cancelled_at = ?, updated_at = ?"
            " WHERE id = ? AND status IN ('requested', 'expired')",
            (db.utcnow(), db.utcnow(), booking_id))
        if cur.rowcount != 1:
            return {"error": "not_confirmable"}
```

   Keep the hold delete and audit lines after it. Then, after the audit line, call `_mail_declined(booking)` and add:

```python
def _mail_declined(booking: Dict[str, Any]) -> None:
    """Tell the guest the host declined, so they do not pay. Best effort."""
    try:
        from . import booking_webhook

        if not booking["guest_email"]:
            return
        apartment = booking_webhook._apartment(booking)
        lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
        facts = booking_webhook._facts(booking, apartment, lang)
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:declined",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.declined_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.declined_text", **facts),
                     "lang": lang, "reply_to": booking_webhook._host_email(apartment)},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: decline mail failed", booking.get("id"))
```

   (`mail`, `host_i18n`, `log` are already imported in that file; check with `grep -n "^from\|^import\|^log" App/app/booking_direct.py`.)

2. `booking_manage.host_rows`: change the two lines to

```python
            "can_cancel": b["status"] == "paid",
            "can_retry": (b["status"] == "cancelled" and b["pay_method"] != "direct"
                          and not int(b["refunded_czk"] or 0)),
            "status_key": ("cancelled_direct" if b["pay_method"] == "direct" and b["status"] == "cancelled"
                           else b["status"]),
```

3. `booking_site_setup.html`: in the badge call replace `t('bsite.bookings.status.' ~ b.status)` with `t('bsite.bookings.status.' ~ b.status_key)`. Leave the `'done' if b.status == 'paid'` tone as it is.

4. `routes/payments.py` `booking_site_cancel`: replace the last line with

```python
    flash_key = "bsite.flash.cancelled_direct" if booking.get("pay_method") == "direct" else "bsite.flash.cancelled"
    return _back(here, msg=_flash(request, flash_key))
```

5. `booking_webhook._mail_confirmed`: in the host `mail.enqueue`, use `"site_booking.mail.host_text_direct"` when `booking.get("pay_method") == "direct"`, else the old key (same pattern as `text_key` above it).

6. `host_i18n.py`, EN block next to `bsite.bookings.status.cancelled` and the `site_booking.mail.*` keys, then the same keys in the CS block:
   - `"bsite.bookings.status.cancelled_direct"`: EN `"Cancelled"`, CS `"Zrušeno"`
   - `"bsite.flash.cancelled_direct"`: EN `"The booking is cancelled. The guest paid you directly: send any refund yourself."`, CS `"Rezervace je zrušená. Host vám platil přímo: případné vrácení pošlete sami."`
   - `"site_booking.mail.declined_subject"`: EN `"Booking request declined: %(property)s, %(dates)s"`, CS `"Poptávka zamítnuta: %(property)s, %(dates)s"`
   - `"site_booking.mail.declined_text"`: EN `"Hello %(name)s,\n\nthe host cannot take your request for %(property)s, %(dates)s. Please do not send a payment. If you already paid, the host sends the money back.\n\nAnswer this e-mail to reach your host."`, CS `"Dobrý den, %(name)s,\n\nhostitel vaši poptávku %(property)s na %(dates)s nemůže přijmout. Prosím, nic neplaťte. Pokud jste už zaplatili, hostitel vám peníze vrátí.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel."`
   - `"site_booking.mail.host_text_direct"`: EN `"You confirmed a booking from your website.\n\nPlace: %(property)s\nDates: %(dates)s\nGuests: %(guests)s\nTotal: %(total)s CZK\nGuest: %(name)s, %(email)s\n\nThe stay is in UbyHost now; the guest got the link to the guest register."`, CS `"Potvrdili jste rezervaci z vašeho webu.\n\nUbytování: %(property)s\nTermín: %(dates)s\nPočet hostů: %(guests)s\nCelkem: %(total)s Kč\nHost: %(name)s, %(email)s\n\nPobyt už je v UbyHostu a host dostal odkaz do knihy hostů."`

7. Tests in `App/tests/test_booking_direct_0998.py` (reuse the file's fixtures and helpers):
   - `test_decline_after_confirm_keeps_paid`: create a request, call `booking_direct.confirm`, then `booking_direct.decline` on the same id: result `{"error": "not_confirmable"}`, status still `paid`.
   - `test_declined_direct_row_has_no_retry`: decline a request; the `host_rows` row has `can_retry` False and `status_key == "cancelled_direct"`.
   - `test_decline_mails_guest`: monkeypatch `mail.enqueue` to record; decline; one call with `idempotency_key` ending `:declined` and the guest's address.
   - `test_direct_confirm_host_mail_not_paid`: record `mail.enqueue` on confirm; the host mail text contains no `"Paid"` (EN) / `"Zaplaceno"` (CS).

## 5. Do not touch

`booking_site.set_status` and `_TRANSITIONS`; the Stripe cancel and refund path; `mail.KINDS`; migrations. AGENTS.md rules 2, 5, 9.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_booking_direct_0996.py tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_booking_site.py tests/test_booking_site_host.py tests/test_booking_cancel.py tests/test_host_i18n.py tests/test_claim_mail.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass.

## 7. Acceptance

- [ ] A decline after a confirm returns `not_confirmable` and the booking stays `paid` (test).
- [ ] A declined or host-cancelled direct row shows "Zrušeno" / "Cancelled" and no "Retry refund" button (390 px screenshot of the bookings list on `/apartments/<id>/booking-site` with one declined direct row).
- [ ] Host cancel of a direct booking flashes the new text.
- [ ] The declined guest gets one mail (test).
- [ ] `grep -n "cancelled_direct\|declined_text\|host_text_direct" App/app/host_i18n.py` shows each key twice (EN, CS).

## 8. Stop and ask

As in TEMPLATE.md §8. Also stop if `db.immediate()` cursors have no `rowcount` on this DB layer (report it; do not invent a helper).

## 9. Report

`docs/tasks/1006-report.md`, 600 tokens at most, `Status: review` (diff stat, commands with last 5 lines, §7, deviations, questions, owner steps).

## Risk list (for the reviewer)

`booking_direct.py` (lock + CAS), `booking_manage.py`, `routes/payments.py`.

## Owner steps

None.
