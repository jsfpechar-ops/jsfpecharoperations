# 1002: Direct bookings never promise a card refund or a payment that did not happen

Status: todo
Depends on: 1001 | Base commit: 57f6799f | Branch: task/0999-property-rules-map (commit on the PR #803 branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When the host cancels a confirmed direct booking, the guest is mailed "You get the full 0 CZK back to your card" and the host "Refunded to the guest: 0 CZK"; the host's button says "Cancel and refund" / "Zrušit a vrátit platbu". The confirmation mail after "Mark paid" says "confirmed and paid … Paid: N CZK" even for a cash-at-arrival booking. This brief gives direct bookings their own copy (reproduced in review with `booking_direct.confirm` then `booking_cancel.cancel(by_host=True)`).

## 2. Context

Rules: AGENTS.md 1-10, rule 9 (copy), `docs/context/rules.md` Copy (EN/CS parity, no em dash). The 0998 brief said to STOP if `_mail_cancelled` printed a refund sentence for amount 0; it does.

`App/app/booking_cancel.py` `_mail_cancelled`:
```
    if by_host:
        guest_key = "site_booking.mail.cancel_guest_by_host"
    elif amount > 0:
```
and
```
        host_key = ("site_booking.mail.cancel_host_by_host" if by_host
                    else "site_booking.mail.cancel_host_by_guest")
```
`App/app/booking_webhook.py` `_mail_confirmed`:
```
    text = host_i18n.translate(lang, "site_booking.mail.guest_text", **facts)
```
`App/app/templates/booking_site_setup.html`:
```
          {{ ui_button(t('bsite.bookings.retry') if b.can_retry else t('bsite.bookings.cancel'), 'danger', type='submit', size='compact') }}
```
`App/app/host_i18n.py` EN has `"site_booking.mail.cancel_guest_by_host"`, `"site_booking.mail.cancel_host_by_host"`, `"site_booking.mail.guest_text"`, `"bsite.bookings.cancel": "Cancel and refund"`; CS has the same keys. If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/booking_cancel.py | edit | direct keys for guest and host cancel mails |
| App/app/booking_webhook.py | edit | direct key for the guest confirmation text |
| App/app/templates/booking_site_setup.html | edit | `Cancel booking` label for direct rows |
| App/app/host_i18n.py | edit | 4 keys EN + CS |
| App/tests/test_booking_direct_0998.py | edit | 2 tests |

No other file may change.

## 4. Steps

1. `booking_cancel.py`: replace the guest-key block start with
```
    direct = booking.get("pay_method") == "direct"
    if by_host and direct:
        guest_key = "site_booking.mail.cancel_guest_direct"
    elif by_host:
        guest_key = "site_booking.mail.cancel_guest_by_host"
    elif amount > 0:
```
and the host key with
```
        host_key = ("site_booking.mail.cancel_host_direct" if by_host and direct
                    else "site_booking.mail.cancel_host_by_host" if by_host
                    else "site_booking.mail.cancel_host_by_guest")
```
2. `booking_webhook.py` `_mail_confirmed`: replace the `text = …guest_text…` line with
```
    text_key = ("site_booking.mail.guest_text_direct" if booking.get("pay_method") == "direct"
                else "site_booking.mail.guest_text")
    text = host_i18n.translate(lang, text_key, **facts)
```
3. `booking_site_setup.html`: replace `t('bsite.bookings.cancel')` in the line of §2 with `(t('bsite.bookings.cancel_direct') if b.direct else t('bsite.bookings.cancel'))`.
4. `host_i18n.py`, EN next to the existing keys (copy the placeholders exactly from the neighbouring `cancel_guest_by_host`, `cancel_host_by_host` and `guest_text` values; keep their line breaks):
   - `"site_booking.mail.cancel_guest_direct"`: "Hello %(name)s,\n\nwe are sorry: the host had to cancel your booking of %(property)s for %(dates)s. You paid the host directly, so the host sends any money back to you.\n\nAnswer this e-mail to reach your host."
   - `"site_booking.mail.cancel_host_direct"`: "You cancelled a booking from your website.\n\nPlace: %(property)s\nDates: %(dates)s\nGuest: %(name)s, %(email)s\nThe guest paid you directly: send any refund yourself.\n\nThe nights are free again."
   - `"site_booking.mail.guest_text_direct"`: the EN `guest_text` value with "your booking is confirmed and paid." replaced by "your host has confirmed your booking." and the line "Paid: %(total)s CZK" replaced by "Total: %(total)s CZK".
   - `"bsite.bookings.cancel_direct"`: "Cancel booking"
   CS:
   - `cancel_guest_direct`: "Dobrý den, %(name)s,\n\nomlouváme se: hostitel musel vaši rezervaci %(property)s na %(dates)s zrušit. Platili jste hostiteli přímo, peníze vám tedy vrací on.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel."
   - `cancel_host_direct`: "Zrušili jste rezervaci z vašeho webu.\n\nUbytování: %(property)s\nTermín: %(dates)s\nHost: %(name)s, %(email)s\nHost vám platil přímo: případné vrácení pošlete sami.\n\nTermín je znovu volný."
   - `guest_text_direct`: the CS `guest_text` value with "vaše rezervace je potvrzená a zaplacená." replaced by "hostitel vaši rezervaci potvrdil." and "Zaplaceno: %(total)s Kč" replaced by "Celkem: %(total)s Kč".
   - `bsite.bookings.cancel_direct`: "Zrušit rezervaci"
   If the CS closing sentence of `cancel_guest_by_host` differs from the one above, copy the real one.
5. `test_booking_direct_0998.py`: (a) `test_host_cancel_direct_mail_has_no_card_refund`: confirm a direct request, monkeypatch `mail.enqueue` to collect kwargs, `booking_cancel.cancel(id, by_host=True)`; assert no payload text contains "card" / "kartu" or "Refunded to the guest" / "Vráceno hostovi". (b) `test_direct_confirm_mail_says_confirmed_not_paid`: after confirm, the `site_booking_confirmed` text does not contain "Paid:" / "Zaplaceno:".

## 5. Do not touch

Stripe refund logic (`refund_now`, `_stripe_refund`), `booking_direct.py`, migrations, CSS. Hard rules 1, 9.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_booking_direct_0996.py tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_booking_site.py tests/test_booking_cancel.py tests/test_booking_webhook.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs --tb=short 2>&1 | tail -30
python3 ../scripts/context_lint.py 2>&1 | tail -5
```

## 7. Acceptance

- [ ] Direct host cancel: guest and host mails mention no card and no "0 CZK refunded".
- [ ] Direct confirm mail says confirmed, not paid.
- [ ] Booking list: a paid direct row shows "Cancel booking" / "Zrušit rezervaci"; Stripe rows unchanged.
- [ ] 390 px screenshot of `/apartments/<id>/booking-site` bookings list in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; a step is unclear.

## 9. Report

`docs/tasks/1002-report.md`, 600 tokens at most, `Status: review` (diff stat, commands with last 5 lines, §7, deviations, questions, owner steps).

## Risk list (for the reviewer)

`booking_cancel.py` key selection (Stripe paths must keep their keys), i18n placeholders.

## Owner steps

None.
