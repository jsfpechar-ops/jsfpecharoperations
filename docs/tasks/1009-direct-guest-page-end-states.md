# 1009: Direct booking guest page: honest declined, host-cancelled and expired states

Status: todo
Depends on: 1006, 1007 | Base commit: 22613010 | Branch: task/0999-property-rules-map (same PR #803)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Round 3 of the PR 803 review. Since 1007 the guest's request mail links to the guest booking page, so a declined guest and a guest whose direct booking the host cancelled both land on it. Today both see "Rezervace zrušena · Podle storno podmínek se nic nevrací" ("nothing is refunded under the cancellation terms") plus "Platili jste hostiteli přímo. Změnu nebo zrušení domluvte…". That is false: a declined guest never paid, and the decline and cancel mails say the host sends the money back. An expired request still says "Termín máte rezervovaný 24 hodin". The Czech lead line on the request page has a typo, "Zaplaůte" instead of "Zaplaťte". This brief fixes these four guest-facing texts.

## 2. Context

Rules: AGENTS.md 1-10 (rule 7: one 390 px screenshot per changed page; rule 9: copy, no em dash).

`App/app/booking_manage.py` `view()` (current lines):

```python
    status = booking["status"]
    state = "refunded" if status == "refunded" else status
```

and in the returned dict `"direct": booking.get("pay_method") == "direct",`. A declined direct request has `status == "cancelled"` and `paid_at` empty; a direct booking that the host confirmed and then cancelled has `status == "cancelled"` and `paid_at` set.

`App/app/templates/booking_manage.html` (current):

```html
    <p class="pp-bk-note">{{ t('bk.sub.' ~ v.state, email=v.email, refund=v.refunded) }}</p>
```

and the policy card starts with `  <section class="pp-bk-card">` followed by `    <h2>{{ t('pp.book.policy_title', name=t('pp.book.policy_name.' ~ v.policy)) }}</h2>`.

`App/app/routes/property_page.py` `booking_manage_page`, direct request branch renders `property_page_requested.html` with `"dates": booking_webhook._dates(booking, lang), "total": int(booking["total_czk"]),`.

`App/app/templates/property_page_requested.html` last lines: `  <p class="ui-sub">{{ t('pp.book.req_hold') }}</p>`.

`App/app/host_i18n.py`: EN block has `"bk.badge.paid": "Paid",` (line ~1495) and `"pp.book.req_hold": ...` (~1719); CS block has `"bk.badge.paid": "Zaplaceno",` (~3624), `"pp.book.req_lead": "%(dates)s, %(total)s Kč. Zaplaůte ubytovateli níže. ...` (~3843) and `"pp.book.req_hold": ...` (~3848).

If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/booking_manage.py | edit | `declined` state and `sub` key for direct cancelled |
| App/app/templates/booking_manage.html | edit | use `v.sub`; hide the policy card for direct non-paid |
| App/app/routes/property_page.py | edit | pass `expired` flag |
| App/app/templates/property_page_requested.html | edit | expired line instead of the 24 h hold |
| App/app/host_i18n.py | edit | new keys EN + CS; CS typo |
| App/tests/test_booking_direct_0998.py | edit | 3 tests |

## 4. Steps

1. `booking_manage.py` `view()`: after `state = ...` add:
   ```python
       direct = booking.get("pay_method") == "direct"
       sub = state
       if direct and status == "cancelled":
           state = sub = "declined" if not booking.get("paid_at") else "cancelled"
           if state == "cancelled":
               sub = "cancelled_direct"
   ```
   Use `direct` for the existing `"direct"` entry and add `"sub": sub,` to the dict. Leave `tone` as is (neutral for non-paid).
2. `booking_manage.html`: change `t('bk.sub.' ~ v.state, ...)` to `t('bk.sub.' ~ v.sub, ...)`. Wrap the whole policy `<section class="pp-bk-card">...</section>` (the one with `pp.book.policy_title`) in `{% if not (v.direct and v.state != 'paid') %}` ... `{% endif %}`.
3. `host_i18n.py`, EN block next to `bk.badge.paid`, add:
   - `"bk.badge.declined": "Declined",`
   - `"bk.h1.declined": "Request declined",`
   - `"bk.sub.declined": "The host cannot take this request. Please do not pay; if you already did, the host sends the money back.",`
   - `"bk.sub.cancelled_direct": "The host cancelled this booking. You paid the host directly, so the host sends your money back.",`
   CS block next to `bk.badge.paid`:
   - `"bk.badge.declined": "Zamítnuto",`
   - `"bk.h1.declined": "Poptávka zamítnuta",`
   - `"bk.sub.declined": "Hostitel tuto poptávku nemůže přijmout. Prosím, nic neplaťte; pokud jste už zaplatili, hostitel vám peníze vrátí.",`
   - `"bk.sub.cancelled_direct": "Hostitel rezervaci zrušil. Platili jste mu přímo, peníze vám tedy vrací on.",`
   Use the file's own escaping style for the CS block if the neighbours use `\u` escapes.
4. CS `pp.book.req_lead`: replace `Zaplaůte` with `Zaplaťte` (ť). Change nothing else in that string.
5. Add after `pp.book.req_hold` in both blocks:
   - EN `"pp.book.req_expired": "The 24-hour hold has passed. The host can still confirm while the dates are free; write to the host before you pay.",`
   - CS `"pp.book.req_expired": "Lhůta 24 hodin uplynula. Hostitel může poptávku ještě potvrdit, pokud je termín volný; před platbou mu napište.",`
6. `routes/property_page.py` `booking_manage_page`, direct branch: add `"expired": booking["status"] == "expired",` to the render context.
7. `property_page_requested.html`: replace the `req_hold` line with `<p class="ui-sub">{{ t('pp.book.req_expired') if expired else t('pp.book.req_hold') }}</p>`.
8. Tests in `test_booking_direct_0998.py` (reuse the file's fixtures and helpers for creating, confirming and declining a direct booking, and `booking_site.manage_url` for the page path):
   - `test_declined_guest_page_says_declined`: decline a request; GET its page with `?lang=en`; 200; "Request declined" in body; "nothing is refunded" not in body (match the EN `bk.sub.cancelled` text case-insensitively); the `bk.policy.direct` EN text not in body.
   - `test_host_cancelled_direct_page_says_host_refunds`: confirm, then host-cancel through the same call the route uses (`booking_cancel.cancel(booking_id, by_host=True)` or the file's helper); GET page `?lang=en`; the `bk.sub.cancelled_direct` text is in the body.
   - `test_expired_request_page_has_no_hold_line`: set `request_expires_at` in the past, run `booking_checkout.expire_requests()`; GET page `?lang=en`; the `req_expired` text is in the body and the `req_hold` text is not.

## 5. Do not touch

Stripe bookings' wording and states (`state` for non-direct rows must stay exactly as today); `booking_cancel.py`; `booking_direct.py`; the token check `_booking_or_none`; any host template. AGENTS.md rules 2, 6, 9.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_booking_site.py tests/test_host_i18n.py tests/test_booking_cancel.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_manage_browser.py tests/test_booking_site_page_browser.py -q --tb=short -rs 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Declined direct request page: badge "Zamítnuto", H1 "Poptávka zamítnuta", "nic neplaťte"; no policy card.
- [ ] Host-cancelled direct booking page: "peníze vám tedy vrací on"; no "nic se nevrací"; no policy card.
- [ ] Card (Stripe) booking pages unchanged (same text as before for paid, cancelled and refunded).
- [ ] Expired request page: the expired line, not "rezervovaný 24 hodin". CS lead reads "Zaplaťte".
- [ ] One 390 px screenshot each of the declined page and the expired request page, opened and described in the report.
- [ ] Tests pass, 0 skipped in the browser files.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/1009-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`booking_manage.view()` state mapping (must not change Stripe rows), `booking_manage.html`.

## Owner steps

None.
