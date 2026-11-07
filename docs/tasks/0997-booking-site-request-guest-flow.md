# 0997: Booking site "request to book", part 2 of 3: guest request flow

Status: todo
Depends on: 0996 merged | Base commit: <sha of main after 0996> | Branch: task/0997-request-guest-flow
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A guest on `/p/<slug>` can send a booking request (dates, guests, name, e-mail) when the host accepts direct payment: the dates are held for 24 hours, the guest sees the host's payment details (IBAN with QR, Revolut link, cash note), and an unconfirmed request expires by itself after 24 hours. Confirming the payment is 0998; this brief never creates a reservation.

## 2. Context

Rules: AGENTS.md 1-10; guest pages: [rules: guest pages](../context/rules.md#guest-pages) (read that one section). Privacy: only the existing name and e-mail are stored (0814 line in `retention.py`); no new field; no new outbound request (the two mails use the existing `mail.enqueue`). No tracking cookies, no third-party script.

State after 0996 (verify with grep, STOP if not found): `booking_site.create_pending(..., status="requested", pay_method="direct", request_expires_at=...)`, `booking_rails.enabled(apartment_id)`, `booking_rails.ready`, status `requested` with transitions `requested -> paid | expired | cancelled`.

Today, `App/app/booking_checkout.py`:
```python
HOLD_MINUTES = 15
```
```python
def hold_dates(apartment_id: int, date_from: str, date_to: str,
               *, minutes: int = HOLD_MINUTES) -> Optional[int]:
```
`hold_dates` already takes `minutes`, so a 24 h hold is `minutes=24 * 60`; it re-checks active reservations and live holds under `db.lock_key`. `App/app/property_page.py`:
```python
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
    return account is not None and account["onboarding_state"] == "complete"
```
(end of `widget_ready`). `App/app/routes/property_page.py` `property_page_checkout` (POST `/p/{slug}/checkout`) validates quote, name (>= 3 chars), e-mail, `terms=1` and `terms_version`, then calls `booking_checkout.start` and renders `property_page_pay.html` (no-store, noindex). The widget form is `templates/property_page_book.html` (posts to `/p/{{ slug }}/checkout`, hidden `date_from`, `date_to`, `guests`, `lang`, button `pp.book.send_request`). The IBAN source and QR: `routes/guest.py` `_fee_pay_panel` uses `payments.spayd(account, total, vs, message)` and `payments.qr_data_uri(payload)` with `payments.format_iban(account)`; the account is `legal_entity.iban` else `payments.normalise_account(legal_entity.bank_account)[1]`.

Scheduler: `App/app/scheduler.py` `_job_mail` iterates `("expire_holds", claim.expire_holds), ("drain", mail.drain), ...`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/property_page.py | edit | `widget_ready`: Stripe complete OR `booking_rails.ready` |
| App/app/booking_rails.py | edit | add `guest_view(apartment_id, booking)` (rails with QR for the guest) |
| App/app/booking_checkout.py | edit | `REQUEST_HOURS = 24`, `start_direct`, `expire_requests` |
| App/app/routes/property_page.py | edit | branch on `pay_method` in `property_page_checkout`; `pay_modes` in the page view |
| App/app/templates/property_page_book.html | edit | pay-mode choice when both Stripe and direct are on; hidden field when one |
| App/app/templates/property_page_requested.html | create | the "request sent, now pay" page |
| App/app/scheduler.py | edit | add job step `expire_requests` |
| App/app/host_i18n.py | edit | EN and CS keys (guest page keys live where the `pp.book.*` keys live) |
| App/tests/test_booking_direct_0997.py | create | tests |

No other file may change. If `widget_ready` is covered in `tests/test_property_page.py` for "no Stripe -> not bookable", update that one assertion to "no Stripe and no rail".

## 4. Steps

Commit after each step: `0997 step k`. Grep each anchor with `grep -nF` first.

**Step 1.** `property_page.py` `widget_ready`: replace the last line `return account is not None and account["onboarding_state"] == "complete"` with
```python
    if account is not None and account["onboarding_state"] == "complete":
        return True
    return booking_rails.ready(apartment_id)
```
and add `from . import booking_rails` next to the existing local `from . import booking_site` inside the function.

**Step 2.** `booking_rails.py`: append
```python
def pay_modes(apartment_id: int, owner_user_id: int) -> List[str]:
    """Ways the guest can book: 'stripe' and/or 'direct'."""
    from . import stripe_connect

    modes = []
    account = stripe_connect.account_for_owner(owner_user_id)
    if account is not None and account["onboarding_state"] == "complete":
        modes.append("stripe")
    if ready(apartment_id):
        modes.append("direct")
    return modes


def guest_view(apartment_id: int, booking: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The rails a guest sees on the request page, host's default first.
    VS is the booking id; the QR payload is built here and never stored."""
    from . import payments

    apartment = _apartment(apartment_id)
    if apartment is None:
        return []
    total = int(booking["total_czk"])
    vs = str(int(booking["id"]))
    first = apartment["stay_fee_guest_default_rail"] or ""
    first = "iban" if first == "qr" else first
    order = ([first] if first in RAILS else []) + [r for r in RAILS if r != first]
    live = set(enabled(apartment_id))
    out: List[Dict[str, Any]] = []
    for rail in order:
        if rail not in live:
            continue
        if rail == "iban":
            entity = db.query_one(
                "SELECT iban, bank_account FROM legal_entity WHERE id = ?",
                (apartment["legal_entity_id"],),
            )
            account = entity["iban"] or payments.normalise_account(entity["bank_account"])[1]
            payload = payments.spayd(account, total, vs, f"Stay {vs}")
            out.append({"key": "iban", "iban": payments.format_iban(account),
                        "qr": payments.qr_data_uri(payload), "vs": vs, "amount": total})
        elif rail == "revolut":
            out.append({"key": "revolut", "link": apartment["stay_fee_guest_revolut_link"]})
        else:
            out.append({"key": "cash", "note": apartment["stay_fee_guest_cash_note"] or ""})
    return out
```
Check the exact `payments` function names first with `grep -n "^def spayd\|^def qr_data_uri\|^def format_iban\|^def normalise_account" App/app/payments.py`; if any differs or `normalise_account` returns something other than a tuple whose item 1 is the IBAN, STOP. Command: `cd App && .venv/bin/python -c "from app import booking_rails" 2>&1 | tail -30`.

**Step 3.** `booking_checkout.py`: append
```python
REQUEST_HOURS = 24


def start_direct(apartment_id: int, q: Dict[str, Any], *, guest_name: str,
                 guest_email: str, lang: str) -> Dict[str, Any]:
    """{"booking": row} or {"error": "taken"|"unavailable"}. Holds the dates for
    24 hours and stores a `requested` booking. No reservation yet (0998)."""
    from . import booking_rails

    apartment = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))
    if apartment is None or not booking_rails.ready(apartment_id):
        return {"error": "unavailable"}
    hold_id = hold_dates(apartment_id, q["date_from"], q["date_to"], minutes=REQUEST_HOURS * 60)
    if hold_id is None:
        return {"error": "taken"}
    expires = (datetime.now(timezone.utc) + timedelta(hours=REQUEST_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    booking = booking_site.create_pending(
        apartment_id, int(apartment["owner_user_id"]), q, guest_name=guest_name,
        guest_email=guest_email, lang=lang, hold_id=hold_id, status="requested",
        pay_method="direct", request_expires_at=expires,
    )
    db.audit("site_booking_requested", f"id={booking['id']}",
             owner_user_id=int(apartment["owner_user_id"]))
    return {"booking": booking}


def expire_requests() -> int:
    """Scheduler job: requests not confirmed within 24 h expire and free their dates."""
    now = db.utcnow()
    rows = db.query(
        "SELECT id, hold_id FROM site_booking WHERE status = 'requested'"
        " AND request_expires_at IS NOT NULL AND request_expires_at <= ?", (now,))
    done = 0
    for row in rows:
        if booking_site.set_status(int(row["id"]), "expired"):
            done += 1
        if row["hold_id"]:
            db.execute("DELETE FROM booking_hold WHERE id = ?", (row["hold_id"],))
    return done
```
Command: `cd App && .venv/bin/python -c "from app import booking_checkout" 2>&1 | tail -30`.

**Step 4.** `scheduler.py`: after the line `("expire_holds", claim.expire_holds),` insert `("expire_requests", booking_checkout.expire_requests),` and add `booking_checkout` to the module's import line (`grep -n "^from \. import\|^from app import" App/app/scheduler.py` to find it; add it there, nothing else).

**Step 5.** `routes/property_page.py`. (a) In `property_page_checkout`, right after the `terms_version` check block and before `result = booking_checkout.start(`, insert:
```python
    mode = str(form.get("pay_mode") or "stripe")
    modes = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
    if mode not in modes:
        return _book_error(slug, "unavailable", lang, form)
    if mode == "direct":
        sent = booking_checkout.start_direct(apartment_id, q, guest_name=name,
                                             guest_email=email, lang=lang)
        if sent.get("error"):
            return _book_error(slug, sent["error"], lang, form)
        booking = sent["booking"]
        response = render(request, "property_page_requested.html", {
            "page": _page_context(apartment_id) or {}, "show_nav": False, "lang": lang,
            "booking": booking, "rails": booking_rails.guest_view(apartment_id, booking),
            "dates": f"{q['date_from']} – {q['date_to']}", "total": q["total_czk"],
        })
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex"
        return response
```
(b) Add helper above it: `def _owner_of(apartment_id: int) -> int:` returning `int(db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))["owner_user_id"])`. (c) In the page view (`page["booking"] = _booking_view(...)` branch) add `page["pay_modes"] = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))`. (d) Add `booking_rails` to the file's `from .. import` line. Do not touch the other routes. Command: `cd App && .venv/bin/python -c "import app.routes.property_page" 2>&1 | tail -30`.

**Step 6.** `templates/property_page_book.html`: before the `<button class="ui-btn ui-btn-primary" type="submit">` line insert
```jinja
    {% if page.pay_modes|length > 1 %}
    <fieldset class="ui-field">
      <legend class="ui-label">{{ t('pp.book.pay_mode') }}</legend>
      <label class="checkline"><input type="radio" name="pay_mode" value="stripe" checked> <span>{{ t('pp.book.mode.stripe') }}</span></label>
      <label class="checkline"><input type="radio" name="pay_mode" value="direct"> <span>{{ t('pp.book.mode.direct') }}</span></label>
    </fieldset>
    {% else %}
    <input type="hidden" name="pay_mode" value="{{ page.pay_modes[0] if page.pay_modes else 'stripe' }}">
    {% endif %}
```
Check with `grep -n "page\.\|booking\." App/app/templates/property_page_book.html | head` how the template names the page object; use that name (if the variable is not `page`, adapt only this name). The submit label stays `pp.book.send_request`.

**Step 7.** Create `templates/property_page_requested.html` (extend `base.html` like `property_page_pay.html`; no inline `style`, use existing `ui-*` classes):
```jinja
{% extends "base.html" %}
{% block title %}{{ t('pp.book.req_title') }}{% endblock %}
{% block content %}
<main class="ui-narrow">
  <h1>{{ t('pp.book.req_title') }}</h1>
  <p>{{ t('pp.book.req_lead', dates=dates, total=total) }}</p>
  {% for r in rails %}
  <section class="ui-card">
    {% if r.key == 'iban' %}
      <h2>{{ t('stay_fees.guest_pay.rail.iban') }}</h2>
      <p class="ui-mono">{{ r.iban }}</p>
      <p>{{ t('pp.book.req_vs', vs=r.vs, amount=r.amount) }}</p>
      <img src="{{ r.qr }}" alt="{{ t('pp.book.req_qr_alt') }}" width="200" height="200">
    {% elif r.key == 'revolut' %}
      <h2>{{ t('stay_fees.guest_pay.rail.revolut') }}</h2>
      <p><a class="ui-btn ui-btn-primary" href="{{ r.link }}" rel="noopener noreferrer" data-no-prefetch>{{ t('pp.book.req_revolut') }}</a></p>
    {% else %}
      <h2>{{ t('stay_fees.guest_pay.rail.cash') }}</h2>
      <p>{{ r.note or t('pp.book.req_cash_default') }}</p>
    {% endif %}
  </section>
  {% endfor %}
  <p class="ui-sub">{{ t('pp.book.req_hold') }}</p>
</main>
{% endblock %}
```
CSP: the Revolut link is a normal `<a>` (not a form POST), so `form-action 'self'` is unaffected; the QR is a data URI, as on the stay-fee page (STOP if the CSP in `security.py` blocks `img-src data:`: `grep -n "img-src" App/app/security.py`).

**Step 8.** `host_i18n.py`: add to the EN and CS blocks, next to the other `pp.book.*` keys (same commit; CS with `\u` escapes). EN:
```python
        "pp.book.pay_mode": "How do you want to pay?",
        "pp.book.mode.stripe": "Pay now by card",
        "pp.book.mode.direct": "Send a request, pay the host directly",
        "pp.book.req_title": "Request sent",
        "pp.book.req_lead": "%(dates)s, %(total)s CZK. Pay the host with one of these. The host confirms your booking when the payment arrives.",
        "pp.book.req_vs": "Variable symbol %(vs)s, amount %(amount)s CZK.",
        "pp.book.req_qr_alt": "Payment QR code",
        "pp.book.req_revolut": "Pay with Revolut",
        "pp.book.req_cash_default": "Pay the host in cash at check-in.",
        "pp.book.req_hold": "These dates are held for 24 hours. Without a confirmation they are released.",
```
CS: `"pp.book.pay_mode": "Jak chcete platit?"`, `"pp.book.mode.stripe": "Zaplatit hned kartou"`, `"pp.book.mode.direct": "Odeslat poptávku a platit přímo ubytovateli"`, `"pp.book.req_title": "Poptávka odeslána"`, `"pp.book.req_lead": "%(dates)s, %(total)s Kč. Zaplaťte ubytovateli níže. Rezervaci potvrdí, až platba dorazí."`, `"pp.book.req_vs": "Variabilní symbol %(vs)s, částka %(amount)s Kč."`, `"pp.book.req_qr_alt": "QR kód pro platbu"`, `"pp.book.req_revolut": "Zaplatit přes Revolut"`, `"pp.book.req_cash_default": "Zaplaťte ubytovateli v hotovosti při příjezdu."`, `"pp.book.req_hold": "Termín máte rezervovaný 24 hodin. Bez potvrzení se uvolní."`. Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`.

**Step 9.** Tests `App/tests/test_booking_direct_0997.py` (reuse the fixtures of `test_booking_site.py` / `test_property_page.py`; copy their imports):
1. `test_widget_ready_direct_only`: published, priced, cash rail, no Stripe -> `widget_ready` True; no rail and no Stripe -> False.
2. `test_request_holds_24h`: POST `/p/<slug>/checkout` with `pay_mode=direct` and valid fields -> 200, page lists the rail, `site_booking.status == "requested"`, `pay_method == "direct"`, `booking_hold.expires_at` about 24 h ahead (between 23 h and 25 h), no `reservation` row.
3. `test_second_request_same_dates_taken`: a second POST for overlapping dates -> the "taken" error, one booking only.
4. `test_pay_mode_not_offered`: `pay_mode=direct` for a Stripe-only host -> error, no row.
5. `test_expire_requests`: set `request_expires_at` in the past, `expire_requests()` -> status `expired`, hold row gone, dates bookable again; a not-yet-due row stays `requested`.
6. `test_iban_rail_shows_qr_and_vs`: IBAN rail -> page contains the formatted IBAN and the booking id as variable symbol.
7. `test_no_stripe_call`: the direct path never calls `stripe_connect._api` (monkeypatch it to raise).
Command: `cd App && .venv/bin/python -m pytest tests/test_booking_direct_0997.py tests/test_booking_direct_0996.py tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -30`.

## 5. Do not touch

`booking_webhook.py`, `booking_cancel.py`, `booking_manage.py`, `routes/payments.py`, migrations, `routes/stay_fees.py`, `routes/guest.py`, `static/*.css` (use existing `ui-*` classes; if a class is missing, STOP). Hard rules: 2 (no cookie, script or outbound request), 6, 9 (the cash/IBAN/Revolut labels reuse `stay_fees.guest_pay.rail.*`; the hold sentence lives only in `pp.book.req_hold`).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30` (test-map rows: Booking site, Public property pages, Page booking widget):
- `.venv/bin/python -m pytest tests/test_booking_direct_0997.py tests/test_booking_direct_0996.py tests/test_booking_site.py tests/test_property_page.py tests/test_booking_widget.py tests/test_stripe_connect.py tests/test_host_i18n.py -q --tb=short -x`
- Guest-page template change (rule 7): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -x -rs` and the guest browser tests for the property page (`ls tests | grep -i "property.*browser\|booking.*browser"`; run those found, 0 skipped).
- Repo root: `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

- [ ] A published page of a host with only a cash rail shows the Book card; a request creates a `requested` row and a 24 h hold, no reservation.
- [ ] The request page shows the IBAN with QR and variable symbol, the Revolut button, the cash note, as the host enabled them; the hold sentence appears once.
- [ ] `expire_requests` frees dates after 24 h and is in the scheduler list.
- [ ] A host with both Stripe and a rail shows the choice; with one, a hidden field.
- [ ] Tests in section 6 pass, 0 skipped.
- [ ] One 390 px screenshot of the book form and of the request page (CS and EN for the request page); 360 and 1280 if the layout changed. Guest pages are report-only in the lint; state per page "390: ...; 768: ...; 1280: ..." in the PR (rule 10 is for host pages, this brief changes none).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found (including the 0996 names listed in section 2);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (`blocked`, executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (for example a CSS class is missing);
- `payments` helpers differ from step 2, or CSP blocks the QR data URI;
- the guest page needs a phone number or any new personal field (it must not: ask the owner);
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0997-report.md` (600 tokens at most), `Status: review`: files changed, each command with last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `booking_checkout.start_direct` and `property_page_checkout` branch: the 24 h hold must go through `hold_dates` (lock plus overlap check), and `pay_mode` must be validated against `pay_modes`.
- A guest could request dates, then never pay: a host sees only `requested` rows (0998); a flood of requests can block dates for 24 h each. The existing `property_page_checkout` rate limit applies; flag to the owner if this is not enough (see decisions line).
- `guest_view`: the QR payload uses the host's IBAN, VS = booking id; nothing is stored.

## Owner steps

1. Review and merge with `scripts/merge-pr-on-green.sh` once CI is green.
2. Do not deploy before 0998 is merged.
