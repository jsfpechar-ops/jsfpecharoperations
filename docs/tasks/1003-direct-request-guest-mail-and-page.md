# 1003: The guest keeps the payment details: request mail, styled request page

Status: todo
Depends on: 1001 | Base commit: 57f6799f | Branch: task/0999-property-rules-map (commit on the PR #803 branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

After a direct request the guest sees the IBAN, QR, Revolut link and cash note only once, as the response to a POST: no mail repeats them, and a page refresh re-posts and lands on `?book=taken` (seen in review). The page also renders unstyled (class `ui-narrow` exists nowhere, the Revolut "button" is a 19 px text link, `ui-card` has no surface, the property name is missing). This brief mails the guest the same details and styles the page with the public booking card classes.

## 2. Context

Rules: AGENTS.md 1-10; rules.md Privacy (no new personal data: the mail uses the stored guest name and e-mail under the 0814 retention line; the IBAN is the host's), Mail (secrets: none here), Copy (EN/CS parity, no em dash). `App/app/mail.py`: "A new kind added to `KINDS` has to be placed in exactly one of these two groups (`GUEST_KINDS`, `HOST_KINDS`); `test_mail.py` fails until it is". Guest mails go through the same `mail.enqueue(... payload={"text": ..., "lang": lang, "reply_to": host_email})` shape as `booking_cancel._mail_cancelled`.

`App/app/booking_checkout.py` `start_direct`:
```
    from . import booking_direct

    booking_direct.notify_request(booking)
    return {"booking": booking}
```
`App/app/templates/property_page_requested.html` line 4: `<main class="ui-narrow">`; each rail is `<section class="ui-card">`; the Revolut link is `<a class="ui-btn ui-btn-primary" href="{{ r.link }}" rel="noopener noreferrer" data-no-prefetch>`.
`App/app/templates/property_page.html` line 5: `{% include "_pp_booking_css.html" %}` (defines `.pp-bk`, `.pp-bk-card`, `.ui-btn { width: 100%; min-height: 44px; }`, `.ui-btn-primary`).
`App/app/mail.py` `KINDS` contains `"site_booking_request_host",`; `HOST_KINDS` contains `"site_booking_request_host",`. `App/app/host_i18n.py` has `"notification.mail_kind.site_booking_host"` (EN line ~7464, CS ~7514) but no label for `site_booking_request_host`. If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/booking_direct.py | edit | `notify_request_guest(booking)` |
| App/app/booking_checkout.py | edit | call it after `notify_request` |
| App/app/mail.py | edit | kind `site_booking_request_guest` in `KINDS` and `GUEST_KINDS` |
| App/app/host_i18n.py | edit | mail subject/text keys + two `notification.mail_kind.*` labels, EN + CS |
| App/app/templates/property_page_requested.html | edit | booking-card classes, property name |
| App/tests/test_booking_direct_0997.py | edit | mail test, page test |

No other file may change.

## 4. Steps

1. `booking_direct.py`: add, after `notify_request`:
```
def notify_request_guest(booking: Dict[str, Any]) -> None:
    """The guest's copy of the payment details. Best effort."""
    try:
        from . import booking_rails, booking_webhook

        apartment = booking_webhook._apartment(booking)
        lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
        facts = booking_webhook._facts(booking, apartment, lang)
        lines = []
        for rail in booking_rails.guest_view(int(booking["apartment_id"]), booking):
            if rail["key"] == "iban":
                lines.append(host_i18n.translate(lang, "site_booking.mail.request_guest_iban",
                                                 iban=rail["iban"], vs=rail["vs"], amount=rail["amount"]))
            elif rail["key"] == "revolut":
                lines.append(host_i18n.translate(lang, "site_booking.mail.request_guest_revolut", link=rail["link"]))
            else:
                lines.append(rail["note"] or host_i18n.translate(lang, "pp.book.req_cash_default"))
        facts["ways"] = "\n\n".join(lines)
        mail.enqueue(
            kind="site_booking_request_guest",
            idempotency_key=f"site_booking:{booking['id']}:request_guest",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.request_guest_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.request_guest_text", **facts),
                     "lang": lang, "reply_to": booking_webhook._host_email(apartment)},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: guest request mail failed", booking.get("id"))
```
   Before writing, run `grep -n "def _facts" -A15 App/app/booking_webhook.py | head -20` and use only placeholder names `_facts` returns (expected: name, property, dates, guests, total). If `_facts` lacks one of those, STOP.
2. `booking_checkout.py`: after `booking_direct.notify_request(booking)` add `booking_direct.notify_request_guest(booking)`.
3. `mail.py`: add `"site_booking_request_guest",` after `"site_booking_request_host",` in `KINDS`, and after `"site_booking_refunded",` in `GUEST_KINDS`.
4. `host_i18n.py` EN:
   - `"site_booking.mail.request_guest_subject": "Booking request: %(property)s, %(dates)s"`
   - `"site_booking.mail.request_guest_text": "Hello %(name)s,\n\nyour request for %(property)s, %(dates)s, %(total)s CZK is with the host. Pay the host with one of these:\n\n%(ways)s\n\nThe dates are held for 24 hours. The host confirms your booking by e-mail when the payment arrives.\n\nAnswer this e-mail to reach your host."`
   - `"site_booking.mail.request_guest_iban": "Bank transfer: %(iban)s, variable symbol %(vs)s, %(amount)s CZK."`
   - `"site_booking.mail.request_guest_revolut": "Revolut: %(link)s"`
   - `"notification.mail_kind.site_booking_request_host": "website booking request"`, `"notification.mail_kind.site_booking_request_guest": "booking request to the guest"`
   CS:
   - subject `"Poptávka rezervace: %(property)s, %(dates)s"`
   - text `"Dobrý den, %(name)s,\n\nvaši poptávku %(property)s, %(dates)s, %(total)s Kč jsme předali hostiteli. Zaplaťte mu jedním z těchto způsobů:\n\n%(ways)s\n\nTermín držíme 24 hodin. Až platba dorazí, hostitel vám rezervaci potvrdí e-mailem.\n\nNa tento e-mail můžete odpovědět, odpověď dostane hostitel."`
   - iban `"Bankovní převod: %(iban)s, variabilní symbol %(vs)s, %(amount)s Kč."`, revolut `"Revolut: %(link)s"`
   - labels `"poptávka rezervace z webu"`, `"poptávka rezervace hostovi"`
5. `property_page_requested.html`: add `{% include "_pp_booking_css.html" %}` as the first line inside `{% block content %}`; change `<main class="ui-narrow">` to `<main class="pp"><section class="pp-bk">` and close `</section>` before `</main>`; change each `<section class="ui-card">` to `<section class="pp-bk-card">`; change the `<h1>` to `{{ t('pp.book.req_title') }} · {{ page.name }}`. No `style=""`.
6. `test_booking_direct_0997.py`: (a) collect `mail.enqueue` kwargs (monkeypatch) during a direct checkout; assert one `site_booking_request_guest` to the guest e-mail whose text contains the cash note or IBAN of the fixture; (b) the response HTML contains `pp-bk-card` and not `ui-narrow`.

## 5. Do not touch

`booking_rails.py`, `routes/property_page.py`, `_pp_booking_css.html`, `static/*`, migrations. Hard rules 2 (no new outbound request beyond the existing mail outbox; no third-party script), 9.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_booking_direct_0996.py tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_mail.py tests/test_host_i18n.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_page_browser.py -q -rs --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] A direct request enqueues one guest mail with the enabled ways to pay and one host mail.
- [ ] `test_mail.py` green (kind in exactly one group).
- [ ] Request page at 390: the Revolut button is 44 px high, each way to pay is a bordered card, the title names the property; screenshots at 390 and 1280 in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; the owner's mail rules seem to need a newsletter prefix (they should not: this is transactional).

## 9. Report

`docs/tasks/1003-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`booking_direct.notify_request_guest` (never raises; idempotency key), `mail.py` groups, i18n placeholders.

## Owner steps

None.
