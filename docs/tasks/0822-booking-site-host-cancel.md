# 0822: Booking site cancellation, host side (bookings list, cancel with full refund)

Status: todo
Depends on: 0819 and 0821 merged (0821 brings `booking_cancel.cancel`, `booking_manage.py`, the guest page and the mail keys; 0819 the page this brief extends) | Base commit: tip of origin/main | Branch: task/0822-booking-site-host-cancel
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the booking site page of 0819 (`/apartments/<id>/booking-site`) the host sees "Rezervace z webu" as in `Host.dc.html` (390 px): the recent bookings (short guest name, dates, total, a status badge) and, per booking, one button "Zrušit a vrátit platbu" that cancels the booking with a full refund to the guest (`booking_cancel.cancel(..., by_host=True)`, built in 0821). A booking whose refund failed (status `cancelled`, nothing refunded) shows "Zopakovat vrácení platby" instead; the retry refunds exactly once with the stored amount. Mails to both sides and the freed nights come from 0821. No other behaviour changes.

Deviation from the mockup, on purpose (name it in the report): the host's list shows the same status words as the guest page (Zaplaceno, Zrušeno, Vráceno) plus "Zrušeno, vrácení čeká" for the open-refund case.

## 2. Context

Plan: `docs/plans/booking-site-v1.md`. Host page rules: `docs/design/MASTER.md` section 13 (extend `host_page.html`, only catalog classes and the macros of `_ui.html`, `_ui_layout.html`; no `<style>`, no `style=""`, no raw colour; one primary button per group; a destructive button is `danger` and sits behind the repo's confirm dialog). The page already exists and is in `docs/design/catalog.json` `enforced_templates` (0819); this brief adds one section and one route and no class.

`booking_cancel.cancel(booking_id, *, by_host, now=None)` returns `{"error": None, "refund_czk": n}` or `{"error": "not_found" | "not_cancellable" | "started" | "busy" | "refund_failed"}`; it is safe to call twice (a second call on a refunded booking returns `not_cancellable` and refunds nothing). Do not change it.

Excerpt `App/app/booking_manage.py` (0821, verbatim; the new function goes at the end of the file, and `List` is added to the typing import):

```python
from typing import Any, Dict
```

Excerpt `App/app/routes/payments.py` after 0819 (verbatim, in `booking_site_setup`; add the bookings key next to `policies`):

```python
            policies=booking_site.POLICIES,
        )
    return render(request, "booking_site_setup.html", context)
```

Excerpt `App/app/routes/payments.py` after 0819 (verbatim; the local import line of `booking_site_setup`):

```python
    from .. import booking_setup, booking_site, property_page as pp
```

(`booking_site_setup` and `booking_site_save` both contain this line; change only the first one, in the GET function.)

Excerpt `App/app/templates/booking_site_setup.html` after 0819 (verbatim; the new section goes after the publish section and before these lines):

```html
{% endif %}
{% endblock %}
```

Excerpt `App/app/templates/property_page_review.html` (verbatim, the confirm-form pattern the repo uses for a destructive host button):

```html
      <form method="post" action="/apartments/{{ apartment.id }}/page/photo-delete" data-confirm data-confirm-message="{{ t('payments.page.photo_delete_confirm') }}" style="position:absolute;top:4px;right:4px;">
```

(The `style=` there is that page's own; do not copy it.)

Excerpt `App/tests/test_design_guardrails_browser.py` (0819 added the `booking-site` route; nothing to add here).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_manage.py` | edit | `host_rows` |
| `App/app/routes/payments.py` | edit | bookings in the page context; `POST /apartments/{id}/booking-site/cancel` |
| `App/app/templates/booking_site_setup.html` | edit | "Rezervace z webu" section |
| `App/app/host_i18n.py` | edit | EN + CS keys `bsite.bookings.*`, flash, errors |
| `docs/design/pages/booking-site.md` | edit | one line for the bookings section (file stays under 40 lines) |
| `App/tests/test_booking_host_cancel.py` | create | route and list tests |
| `App/tests/test_booking_site_host_browser.py` | edit | assert the bookings section at 390 and 1280, second screenshot |
| `docs/tasks/0822-report.md`, `docs/tasks/screenshots-0822/host-390.png` | create | report, screenshot |

No other file may change.

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0822 step k"`.

**Step 1.** `App/app/booking_manage.py`: replace `from typing import Any, Dict` with `from typing import Any, Dict, List`, then append at the end of the file:

```python

def host_rows(apartment_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """The host's recent site bookings: short name, dates, total, status, actions."""
    rows = db.query(
        "SELECT * FROM site_booking WHERE apartment_id = ? AND status IN ('paid', 'cancelled',"
        " 'refunded', 'clash_refunded') ORDER BY date_from DESC, id DESC LIMIT ?",
        (apartment_id, limit),
    )
    out = []
    for row in rows:
        b = dict(row)
        parts = (b["guest_name"] or "").split()
        short = parts[0] + (f" {parts[-1][:1]}." if len(parts) > 1 else "") if parts else ""
        d_from, d_to = date.fromisoformat(b["date_from"]), date.fromisoformat(b["date_to"])
        out.append({
            "id": int(b["id"]), "name": short, "status": b["status"],
            "dates": f"{d_from.day}.–{d_to.day}. {d_to.month}.",
            "total": int(b["total_czk"]),
            "can_cancel": b["status"] == "paid",
            "can_retry": b["status"] == "cancelled" and not int(b["refunded_czk"] or 0),
        })
    return out
```

Run `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_manage.py 2>&1 | tail -5`.

**Step 2.** Routes and page. (a) `App/app/routes/payments.py`: in `booking_site_setup` (0819) replace the two lines shown in section 2 with:

```python
            policies=booking_site.POLICIES,
            bookings=booking_manage.host_rows(apartment_id),
        )
    return render(request, "booking_site_setup.html", context)
```

and change that function's local import line `from .. import booking_setup, booking_site, property_page as pp` to `from .. import booking_manage, booking_setup, booking_site, property_page as pp`. (b) Directly after the `booking_site_save` function add:

```python
@router.post("/apartments/{apartment_id}/booking-site/cancel")
async def booking_site_cancel(request: Request, apartment_id: int):
    """0821: the host cancels a site booking; the guest is refunded in full."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_cancel, booking_site

    here = f"/apartments/{apartment_id}/booking-site"
    form = await request.form()
    raw = str(form.get("booking_id") or "")
    booking = booking_site.get(int(raw)) if raw.isdigit() else None
    if booking is None or int(booking["apartment_id"]) != apartment_id or int(booking["owner_user_id"]) != owner_id:
        return Response(status_code=404)
    result = booking_cancel.cancel(int(booking["id"]), by_host=True)
    if result["error"] == "refund_failed":
        return _back(here, err=_flash(request, "bsite.err.cancel_failed"))
    if result["error"]:
        return _back(here, err=_flash(request, "bsite.err.not_cancellable"))
    return _back(here, msg=_flash(request, "bsite.flash.cancelled"))
```

(c) `App/app/templates/booking_site_setup.html`: before the final `{% endif %}{% endblock %}` (section 2) add this section, in the 0819 style (a `ui_section` call block, a `ui-facts` list, existing macros only):

```html
{% call ui_section(t('bsite.bookings.title')) %}
  {% if bookings %}
  <dl class="ui-facts">
    {% for b in bookings %}
    <div>
      <dt>{{ b.name }} · {{ b.dates }} · {{ b.total }} {{ t('payments.czk') }}</dt>
      <dd>
        {{ ui_badge('done' if b.status == 'paid' else 'neutral', t('bsite.bookings.status.' ~ b.status)) }}
        {% if b.can_cancel or b.can_retry %}
        <form method="post" action="/apartments/{{ apartment.id }}/booking-site/cancel" data-confirm data-confirm-message="{{ t('bsite.bookings.confirm') }}">
          <input type="hidden" name="_csrf" value="{{ csrf_token }}">
          <input type="hidden" name="booking_id" value="{{ b.id }}">
          {{ ui_button(t('bsite.bookings.retry') if b.can_retry else t('bsite.bookings.cancel'), 'danger', type='submit', size='compact') }}
        </form>
        {% endif %}
      </dd>
    </div>
    {% endfor %}
  </dl>
  {% else %}
  <p class="ui-sub">{{ t('bsite.bookings.empty') }}</p>
  {% endif %}
{% endcall %}
```

Run `python3 scripts/design_lint.py 2>&1 | tail -10` (must print OK; the template is already in the catalog from 0819; do not add classes).

**Step 3.** `App/app/host_i18n.py`: keys. Anchor: `grep -nF '"bsite.err.advance_notice_days"' app/host_i18n.py` (0819; two hits: English, then Czech). Insert English after the first, Czech after the second. If the anchor is missing, 0819 is not merged: STOP. Also check `grep -c '"site_booking.mail.cancel_subject"' app/host_i18n.py` prints 2 (0821); otherwise STOP.

English:

```python
        "bsite.bookings.title": "Bookings from the site",
        "bsite.bookings.empty": "No bookings from the site yet.",
        "bsite.bookings.status.paid": "Paid",
        "bsite.bookings.status.cancelled": "Cancelled, refund open",
        "bsite.bookings.status.refunded": "Cancelled",
        "bsite.bookings.status.clash_refunded": "Refunded",
        "bsite.bookings.cancel": "Cancel and refund",
        "bsite.bookings.retry": "Repeat the refund",
        "bsite.bookings.confirm": "Cancel this booking and refund the guest in full?",
        "bsite.flash.cancelled": "The booking is cancelled and the guest is refunded.",
        "bsite.err.cancel_failed": "The refund did not go through. Nothing was lost; try again in a moment.",
        "bsite.err.not_cancellable": "This booking can no longer be cancelled.",
```

Czech:

```python
        "bsite.bookings.title": "Rezervace z webu",
        "bsite.bookings.empty": "Zatím žádná rezervace z webu.",
        "bsite.bookings.status.paid": "Zaplaceno",
        "bsite.bookings.status.cancelled": "Zrušeno, vrácení čeká",
        "bsite.bookings.status.refunded": "Zrušeno",
        "bsite.bookings.status.clash_refunded": "Vráceno",
        "bsite.bookings.cancel": "Zrušit a vrátit platbu",
        "bsite.bookings.retry": "Zopakovat vrácení platby",
        "bsite.bookings.confirm": "Zrušit rezervaci a vrátit hostovi celou částku?",
        "bsite.flash.cancelled": "Rezervace je zrušená a host má platbu zpět.",
        "bsite.err.cancel_failed": "Vrácení platby neproběhlo. Nic se neztratilo, zkuste to za chvíli.",
        "bsite.err.not_cancellable": "Tuto rezervaci už nejde zrušit.",
```

Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -15`.

**Step 4.** `docs/design/pages/booking-site.md` (0819, under 40 lines): add one bullet under the body sections: "Bookings from the site: facts list, one row per booking (short name, dates, total), status badge `done` for paid and `neutral` otherwise; one `danger` compact button per row behind the confirm dialog (full refund); empty text when none." Keep the file under 40 lines.

**Step 5.** Tests. Create `App/tests/test_booking_host_cancel.py`. Fixture, cleanup, fake Stripe refunds client and the `_paid` helper: copy them from `tests/test_booking_cancel.py` (0821); the host login: copy the `owner` / `client` fixtures of `tests/test_property_page.py` (the owner must own the apartment; give the apartment the Stripe row and entity the way `test_booking_cancel.py` does). Tests:

1. `test_page_lists_the_booking`: GET `/apartments/<aid>/booking-site?lang=en` shows `Bookings from the site`, the short name (`Jana N.`), the total and `Cancel and refund`; with no booking it shows `No bookings from the site yet.`.
2. `test_host_cancel_refunds_in_full`: POST `/apartments/<aid>/booking-site/cancel` with `booking_id` (token as `tests/test_property_page.py` posts to `/apartments/<id>/page`): 303; booking `refunded`; Stripe got one refund of `total * 100`; the nights are free; the flash is the success text.
3. `test_other_owner_and_other_apartment_are_404`: a booking id of another owner's apartment, and of a second apartment of the same owner, give 404 and change nothing; a non-number `booking_id` is 404.
4. `test_failed_refund_shows_retry_and_retry_works`: Stripe fails on the first call: redirect with the error flash, the list shows `Repeat the refund`; fix the fake, POST again: `refunded`, exactly one successful refund, same idempotency key.
5. `test_paid_and_cancelled_rows_have_the_right_button`: a `paid` booking shows `Cancel and refund`; a `refunded` one shows no button.

Run `.venv/bin/python -m pytest tests/test_booking_host_cancel.py -q --tb=short -x 2>&1 | tail -30`. Fix once if red.

**Step 6.** Browser. In `App/tests/test_booking_site_host_browser.py` (0819) seed one `paid` booking for the page's apartment (insert a `site_booking` row with status `paid` and the required columns, copy the insert from `tests/test_booking_cancel.py`), assert at 390 and 1280 that the section "Rezervace z webu" is present, its danger button is at least 44 px high at 390, there is no horizontal scroll and the layout guard of `design_guard.js` still passes. Save the 390 screenshot of the page to `docs/tasks/screenshots-0822/host-390.png`.

**Step 7.** Run §6. Look at the screenshot once with the Read tool and compare with `Host.dc.html`: the "Rezervace z webu" card, a badge per row, the red button. Write the report.

## 5. Do not touch

`App/app/booking_cancel.py`, `booking_site.py`, `booking_webhook.py`, `booking_invoice.py`, `stripe_connect.py`, `routes/property_page.py`, every public template, `docs/design/catalog.json` (no new class), CSS and JS files, `db.py`, migrations. Hard rules 3, 4, 5, 6, 7, 9.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_manage.py app/routes/payments.py tests/test_booking_host_cancel.py tests/test_booking_site_host_browser.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_host_cancel.py tests/test_booking_cancel.py tests/test_booking_setup.py tests/test_booking_site.py tests/test_property_page.py tests/test_payments_dashboard.py tests/test_stripe_connect.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_host_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
```

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -5`. Any skipped browser test is a failure: report `blocked`.

## 7. Acceptance

- [x] The three §6 runs pass; the browser run shows `0 skipped`; `design lint: OK`.
- [x] `grep -nE 'style=|<style|#[0-9a-fA-F]{3,8}\b' App/app/templates/booking_site_setup.html` prints nothing.
- [x] A host cannot cancel another owner's or another apartment's booking (test 3).
- [x] A failed refund can be repeated and refunds once (test 4).
- [x] `git diff --stat origin/main` lists only the §3 files.
- [x] One 390 px screenshot at `docs/tasks/screenshots-0822/host-390.png`, named in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; `bsite.err.advance_notice_days` (0819) or `site_booking.mail.cancel_subject` (0821) is missing; a test fails twice; the browser run skips anything or Chromium is missing; the design lint finds a class you cannot replace; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0822-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the deviation from §1, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

- `routes/payments.py`: ownership by owner id AND apartment id of the booking; the cancel route does no Max check on purpose (a host who downgraded must still be able to refund a paying guest).
- The confirm dialog is the repo's `data-confirm` enhancement; without JavaScript the button submits at once. The action is safe to repeat (a second call does nothing), and a full refund to the guest is the host's own decision.
- The retry button appears only while nothing was refunded; Stripe's idempotency key lives 24 h (see the risk list of 0821: check Stripe before repeating after a day).

## Owner steps

1. Merge when CI is green.
2. Test mode, end to end on a phone: book on the public page, cancel as the guest from the e-mail link (check the refund in Stripe), book again and cancel as the host here, then try a non-refundable booking. Only then go live.
