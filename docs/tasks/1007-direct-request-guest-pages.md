# 1007: Direct request: no re-post on refresh, honest guest booking page, styled pay choice

Status: todo
Depends on: 1006 | Base commit: 6217fcc8 | Branch: task/0999-property-rules-map (same PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Round 2 of the PR 803 review: refreshing the "Request sent" page still re-posts the form and shows "These dates are already taken"; the guest's booking page and confirm mail for a direct booking promise "Paid", an invoice, a cancel option and "we refund the full amount", none of which is true when the guest paid the host; the request page shows ISO dates and a 17 px Revolut text link; and the new pay-mode radios on `/p/<slug>` render as a browser-default grey fieldset box under a "Continue to payment" button even when "pay the host" is chosen. This brief fixes all five on the guest side.

## 2. Context

Rules: AGENTS.md 1-10 (rule 6: works without JavaScript; rule 7: one 390 px screenshot per changed page; rule 9: copy). Guest pages: `docs/context/rules.md#guest-pages`.

`App/app/routes/property_page.py` `property_page_checkout`, direct branch (current):

```python
        booking = sent["booking"]
        response = render(request, "property_page_requested.html", {
            "page": _page_context(apartment_id) or {}, "show_nav": False, "lang": lang,
            "booking": booking, "rails": booking_rails.guest_view(apartment_id, booking),
            "dates": f"{q['date_from']} – {q['date_to']}", "total": q["total_czk"],
        })
```

Same file, `booking_manage_page` (GET `/p/{slug}/b/{booking_id}/{token}`) renders `booking_manage.html` with `"v": booking_manage.view(booking, lang)`; `_booking_or_none(booking_id, token)` checks the token.

`App/app/booking_site.py` `manage_url(booking)` returns the absolute `https://<host>/p/<slug>/b/<id>/<token>`. `App/app/booking_webhook.py` has `_dates(booking, lang)` (Czech "5. 2. 2027 – 8. 2. 2027").

`App/app/booking_manage.py` `view()` returns `state`, `total`, `can_cancel` (already False for direct), `has_invoice`, `policy`, `deadline`.

`App/app/templates/booking_manage.html` line `<div class="pp-bk-row pp-bk-total"><span>{{ t('bk.paid') }}</span>...` and the policy card `<p class="pp-bk-note">{{ t('bk.policy.' ~ v.policy, when=v.deadline) }}</p>`.

`App/app/booking_webhook.py` `_mail_confirmed` appends `"site_booking.mail.guest_manage"` ("Your booking page with the invoice and the cancellation option: %(link)s") to every confirm mail.

`App/app/templates/property_page.html` pay choice (current):

```html
        <fieldset class="ui-field">
          <legend class="ui-label">{{ t('pp.book.pay_mode') }}</legend>
```

and the button `{{ t('pp.book.send_request') }}` = "Continue to payment" / "Pokračovat k platbě".

`App/app/templates/_pp_booking_css.html` has `.pp-bk .ui-btn { width: 100%; min-height: 44px; }`, which does not size an inline `<a>`.

If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/property_page.py | edit | 303 to the booking page; GET renders the request page for open direct requests |
| App/app/booking_manage.py | edit | `direct` flag in `view()` |
| App/app/templates/booking_manage.html | edit | "Total" and direct policy line for direct bookings |
| App/app/booking_direct.py | edit | booking page link in the guest request mail (step 8) |
| App/app/templates/property_page.html | edit | fieldset class |
| App/app/templates/_pp_booking_css.html | edit | fieldset and link-button rules |
| App/app/booking_webhook.py | edit | direct manage line |
| App/app/host_i18n.py | edit | keys EN + CS |
| App/tests/test_booking_direct_0997.py | edit | 3 tests |

No other file may change.

## 4. Steps

1. `property_page_checkout` direct branch: replace the `render(...)` block and the two header lines after it with

```python
        booking = sent["booking"]
        from urllib.parse import urlsplit
        return RedirectResponse(urlsplit(booking_site.manage_url(booking)).path, status_code=303)
```

   (`RedirectResponse` is already imported in this file; check with grep.)

2. `booking_manage_page`: after `lang = _manage_lang(request, booking)`, add

```python
    if booking.get("pay_method") == "direct" and booking["status"] in ("requested", "expired"):
        apartment_id = int(booking["apartment_id"])
        response = render(request, "property_page_requested.html", {
            "page": _page_context(apartment_id) or {}, "show_nav": False, "lang": lang,
            "booking": booking, "rails": booking_rails.guest_view(apartment_id, booking),
            "dates": booking_webhook._dates(booking, lang), "total": int(booking["total_czk"]),
        })
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex"
        return response
```

   Import `booking_webhook` the way the file imports other app modules (grep the import line first).

3. `booking_manage.view()`: add `"direct": booking.get("pay_method") == "direct",` to the returned dict.

4. `booking_manage.html`: replace `{{ t('bk.paid') }}` with `{{ t('pp.book.total') if v.direct else t('bk.paid') }}`, and replace the policy `<p>` with
   `<p class="pp-bk-note">{{ t('bk.policy.direct') if v.direct else t('bk.policy.' ~ v.policy, when=v.deadline) }}</p>`.

5. `_mail_confirmed`: use `"site_booking.mail.guest_manage_direct"` instead of `"site_booking.mail.guest_manage"` when `booking.get("pay_method") == "direct"`.

6. `property_page.html`: change `<fieldset class="ui-field">` to `<fieldset class="pp-bk-pay">` and `<legend class="ui-label">` to `<legend>`.

7. `_pp_booking_css.html`: append

```css
.pp-bk-pay { border: 0; margin: 0 0 12px; padding: 0; display: grid; gap: 12px; }
.pp-bk-pay legend { padding: 0; margin-bottom: 6px; font-weight: 600; }
.pp-bk a.ui-btn { display: flex; align-items: center; justify-content: center; text-decoration: none; }
```

   (Use the tokens the file already uses if it uses `var(--space-*)`; no raw colours.)

8. `host_i18n.py` EN then CS:
   - `"pp.book.send_request"`: EN `"Continue"`, CS `"Pokračovat"` (edit the existing key).
   - `"bk.policy.direct"`: EN `"You paid the host directly. To change or cancel, answer the confirmation e-mail; the host settles any refund."`, CS `"Platili jste hostiteli přímo. Změnu nebo zrušení domluvte odpovědí na potvrzovací e-mail; případné vrácení řeší hostitel."`
   - `"site_booking.mail.guest_manage_direct"`: EN `"Your booking page: %(link)s"`, CS `"Stránka vaší rezervace: %(link)s"`
   - Add the booking page link to the request mail: in `booking_direct.notify_request_guest` set `facts["link"] = booking_site.manage_url(booking)` and append `"\n\n%(link)s"` text via a new key `"site_booking.mail.request_guest_link"`: EN `"The payment details are also here: %(link)s"`, CS `"Platební údaje najdete i zde: %(link)s"` (append to the payload text with `"\n\n"`).

9. Tests in `App/tests/test_booking_direct_0997.py`:
   - `test_direct_checkout_redirects_to_booking_page`: post the direct checkout; status 303; `Location` starts with `/p/` and contains `/b/`; GET that location: 200 and the IBAN or cash text is in the body.
   - `test_request_page_get_twice_same`: GET the location twice; both 200, no `book=taken`.
   - `test_paid_direct_booking_page_has_no_refund_promise`: confirm the booking; GET its page; `"Paid"` not in the total row and the `bk.policy.direct` EN text is present.
   Update any existing 0997 test that expected the request page body straight from the POST (follow the redirect instead).

## 5. Do not touch

The Stripe checkout branch; `booking_cancel.py`; `templates/guest/`; any host template. AGENTS.md rules 2, 6, 9.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_property_page.py tests/test_booking_site.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_page_browser.py -q --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Reloading the request page shows the same payment details (no "taken" error).
- [ ] Booking page of a confirmed direct booking: "Total", no refund promise, no cancel button.
- [ ] 390 px screenshots: `/p/<slug>` with both modes (no grey fieldset box; button "Pokračovat"), the request page (Revolut button 44 px high, Czech dates).
- [ ] Tests pass, 0 skipped in the browser file.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/1007-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`routes/property_page.py` (redirect, token-checked GET), `booking_manage.html`.

## Owner steps

None.
