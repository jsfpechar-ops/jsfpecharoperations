# 1001: Make request-to-book reachable from the real booking form, fix test-postgres

Status: todo
Depends on: 0995-1000 (PR #803) | Base commit: 57f6799f | Branch: task/0999-property-rules-map (commit on the PR #803 branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The guest books from the form on `/p/<slug>` (`property_page.html`), but 0997 put the pay-mode radios only in `property_page_book.html`, which no page links to. Result (seen in review): a cash-only host's page shows "Pay 4500 CZK by card" and the submit ends in `?book=unavailable`; a Stripe + direct host never offers the request. This brief puts the choice on the real form and fixes the one red CI job (`test-postgres`).

## 2. Context

Rules: AGENTS.md 1-10. Public property pages are not under `templates/guest/`; the design-system page does not apply, but no `style=""` is added and the form must work without JavaScript. Copy rule 9: one explanation in one place.

`App/tests/test_db_postgres.py` line 290 (CI job `test-postgres` fails: history has 39 rows, the list stops at 38):
```
    assert [row["version"] for row in history] == list(range(1, 39))
```

`App/app/routes/property_page.py`, `property_page_view` already puts the modes on `page`:
```
        page["pay_modes"] = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
```
and `property_page_checkout`:
```
    mode = str(form.get("pay_mode") or "stripe")
    modes = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
```

`App/app/templates/property_page.html` (the real form):
```
        <label class="ui-check"><input type="checkbox" name="terms" value="1" required><span>{{ t('pp.book.terms') }}</span></label>
        <p class="pp-bk-note"><a href="/terms/booking?lang={{ lang }}" target="_blank" rel="noopener">{{ t('pp.book.terms_read') }}</a></p>
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.pay_card', total=b.q.total_czk) }}</button>
        <p class="pp-bk-fine">{{ t('pp.book.stripe_note') }}</p>
```

`App/app/host_i18n.py` has `pp.book.pay_mode`, `pp.book.mode.stripe`, `pp.book.mode.direct` (EN and CS) from 0997. If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_db_postgres.py | edit | `range(1, 39)` to `range(1, 40)` |
| App/app/templates/property_page.html | edit | pay-mode fieldset and mode-dependent button on the real form |
| App/app/routes/property_page.py | edit | default `pay_mode` to the only mode |
| App/app/host_i18n.py | edit | one key `pp.book.send_direct` (EN + CS) |
| App/tests/test_booking_direct_0997.py | edit | two tests that read the real page HTML |

No other file may change.

## 4. Steps

1. `test_db_postgres.py` line 290: replace `list(range(1, 39))` with `list(range(1, 40))`.
2. `property_page.html`: replace the four lines of §2 with:
```
        <label class="ui-check"><input type="checkbox" name="terms" value="1" required><span>{{ t('pp.book.terms') }}</span></label>
        <p class="pp-bk-note"><a href="/terms/booking?lang={{ lang }}" target="_blank" rel="noopener">{{ t('pp.book.terms_read') }}</a></p>
        {% set modes = page.pay_modes or ['stripe'] %}
        {% if modes|length > 1 %}
        <fieldset class="ui-field">
          <legend class="ui-label">{{ t('pp.book.pay_mode') }}</legend>
          <label class="ui-check"><input type="radio" name="pay_mode" value="stripe" checked><span>{{ t('pp.book.mode.stripe') }}</span></label>
          <label class="ui-check"><input type="radio" name="pay_mode" value="direct"><span>{{ t('pp.book.mode.direct') }}</span></label>
        </fieldset>
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.send_request') }}</button>
        {% elif modes[0] == 'direct' %}
        <input type="hidden" name="pay_mode" value="direct">
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.send_direct') }}</button>
        {% else %}
        <input type="hidden" name="pay_mode" value="stripe">
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('pp.book.pay_card', total=b.q.total_czk) }}</button>
        <p class="pp-bk-fine">{{ t('pp.book.stripe_note') }}</p>
        {% endif %}
```
3. `routes/property_page.py` `property_page_checkout`: swap the two lines of §2 so `modes` comes first, and default to the only mode:
```
    modes = booking_rails.pay_modes(apartment_id, _owner_of(apartment_id))
    mode = str(form.get("pay_mode") or (modes[0] if len(modes) == 1 else "stripe"))
```
4. `host_i18n.py`: next to `pp.book.mode.direct` add EN `"pp.book.send_direct": "Send booking request",` and CS `"pp.book.send_direct": "Odeslat poptávku",`.
5. `test_booking_direct_0997.py`: add
   - `test_real_page_offers_direct_only`: cash-only host (reuse the file's `owner` fixture and its slug helper), `GET /p/<slug>?lang=en&month=…&date_from=…&date_to=…&guests=2` with dates the quote accepts (copy them from `_checkout_payload`); assert `name="pay_mode" value="direct"` and `Send booking request` in the HTML and `by card` not in it. Then post the page's hidden fields plus name, e-mail, `terms=1` WITHOUT `pay_mode`: the response is 200 and renders the requested page (assert `pp.book.req_title` EN text `Request sent`).
   - `test_real_page_offers_both_modes`: same host with a complete `stripe_account` row (copy the insert from `tests/test_booking_site_page_browser.py` `seeded`); assert two `type="radio" name="pay_mode"` inputs.
6. Run §6.

## 5. Do not touch

`booking_checkout.py`, `booking_rails.py`, `property_page_book.html` (legacy no-JS page, left as is), CSS, migrations. Hard rules 2, 6, 9.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_booking_direct_0996.py tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_booking_site.py tests/test_host_i18n.py tests/test_property_page.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_booking_site_page_browser.py -q -rs --tb=short 2>&1 | tail -30
```
Expected: all pass, 0 skipped. `test_db_postgres.py` needs PostgreSQL; CI runs it (job `test-postgres` must turn green).

## 7. Acceptance

- [ ] Cash-only host: `/p/<slug>` with dates shows "Send booking request", no "by card", no Stripe note; submitting shows "Request sent".
- [ ] Stripe + direct host: two radios, card checked by default.
- [ ] Stripe-only host: page unchanged (button "Pay N CZK by card").
- [ ] CI `test-postgres` green.
- [ ] 390 px screenshot of `/p/<slug>` booking card for the cash-only host in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; a step is unclear; you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/1001-report.md` (600 tokens at most), set `Status: review`: diff stat, commands with last 5 lines, §7 ticked, deviations, questions, owner steps.

## Risk list (for the reviewer)

`property_page.html` (the form must still post `terms_version`), `routes/property_page.py` checkout default.

## Owner steps

None beyond merging PR #803 with `scripts/merge-pr-on-green.sh`.
