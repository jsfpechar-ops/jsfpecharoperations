# 1004: Booking-site page: one coral per row, short labels, roomy pay form, expired requests can be dismissed

Status: todo
Depends on: 1002 | Base commit: 57f6799f | Branch: task/0999-property-rules-map (commit on the PR #803 branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Review of `/apartments/<id>/booking-site` with real direct rows (390/768/1280, CS+EN) found: the layout lint fires `tight-stack` ("Zamítnout"/"Decline" 0 px below "Potvrdit a označit jako zaplaceno"); every requested and expired row has its own coral primary (design-system rule 9: coral is the one primary); the label is 33 characters (button rule: under 24); the "How guests pay" form has three grey fine-print lines (rule 7), checkbox rows 22 px high, 8 px apart (rule 3: 12 px; touch target 44 px) and uses the guest-page class `gp-check`; an expired request can only be marked paid, never dismissed, so it stays in the list with a coral button forever. Also `expire_requests` and `decline` raise `ValueError` (500 / aborted job) when a concurrent confirm moved the row to `paid`.

## 2. Context

Rules: AGENTS.md 1-10 (rule 10 UX gate), `docs/design/design-system.md` §1 rules 3, 7, 9 and §2 Buttons/Forms; read the `booking-site` add-on only if `docs/design/pages/` has one (`ls docs/design/pages | grep -i booking`).

`App/app/templates/booking_site_setup.html` (from 0996/0998):
```
<p class="ui-sub">{{ t('bsite.pay.lead') }} <a href="/payments">{{ t('bsite.act.stripe') }}</a></p>
```
```
  <label class="gp-check checkline"><input type="checkbox" name="rails" value="iban"{% if 'iban' in pay.ticked %} checked{% endif %}> <span>{{ t('stay_fees.guest_pay.rail.iban') }}</span></label>
  {% if not pay.iban_ok %}<p class="ui-sub">{{ t('bsite.pay.no_account') }}</p>{% endif %}
```
(and the same `gp-check checkline` label for `revolut` and `cash`), `<p class="ui-sub">{{ t('bsite.pay.shared') }}</p>`, and
```
          {{ ui_button(t('bsite.bookings.mark_paid'), 'primary', type='submit', size='compact') }}
```
`App/app/templates/_ui.html`: `{% macro ui_check(id, label, name='', checked=false, value='1', attrs='') -%}` and `_ui_layout.html`: `{% macro ui_section(title, actions='', id='', tip='') -%}`; `_components.html` has `tip_label(text, id, help, tag='strong')`. Find how another host page passes a help "?" to `ui_section(..., tip=...)` with `grep -rn "ui_section(.*tip=" App/app/templates | head -3` and copy that pattern.

`App/app/booking_site.py`: `"expired": {"paid", "clash_refunded"},`. `App/app/booking_manage.py`: `"can_decline": b["pay_method"] == "direct" and b["status"] == "requested",`. `App/app/booking_direct.py` `decline`: `if booking["status"] != "requested":`. `App/app/booking_checkout.py` `expire_requests`: `if booking_site.set_status(int(row["id"]), "expired"):`. If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/booking_site_setup.html | edit | pay form with `ui_check`, help "?", secondary Mark paid |
| App/app/host_i18n.py | edit | shorter `bsite.bookings.mark_paid`, EN + CS |
| App/app/booking_site.py | edit | `expired` may go to `cancelled` |
| App/app/booking_manage.py | edit | `can_decline` for expired direct rows |
| App/app/booking_direct.py | edit | decline accepts `expired`; `ValueError` becomes `not_confirmable` |
| App/app/booking_checkout.py | edit | `expire_requests` skips a row that moved |
| App/tests/test_booking_direct_0998.py | edit | 2 tests |
| docs/design/catalog.json | edit | drop the `gp-check` entry 0996 added for this page, if the design lint allows |

No other file may change.

## 4. Steps

1. Pay form: replace the three `<label class="gp-check checkline">…</label>` lines with `{{ ui_check('rail-iban', t('stay_fees.guest_pay.rail.iban'), name='rails', value='iban', checked='iban' in pay.ticked) }}` (and `rail-revolut`, `rail-cash`). Delete the `<p class="ui-sub">{{ t('bsite.pay.lead') }} …</p>` and `<p class="ui-sub">{{ t('bsite.pay.shared') }}</p>` lines; pass both sentences plus the Stripe link as the section help instead: `{% call ui_section(t('bsite.step.pay'), id='pay', tip=<the help "?" built like the grep result, text = t('bsite.pay.lead') ~ ' ' ~ t('bsite.pay.shared')>) %}`, and put `{{ ui_button(t('bsite.act.stripe'), 'secondary', href='/payments', size='compact') }}` in the `actions` argument. Keep the `no_account` line (it is a blocking state, not fine print) but render it as `{{ ui_banner('attention', t('bsite.pay.no_account')) }}` above the checkboxes.
2. Bookings list: change the Mark paid button variant `'primary'` to `'secondary'`. Wrap the badge and the forms of one row in one `<div class="ui-btn-group">` if the row is not already one (check the `<dd>`; the lint needs 12 px between Mark paid and Decline; `ui-btn-group` has the gap token).
3. `host_i18n.py`: `"bsite.bookings.mark_paid"` EN "Mark paid", CS "Označit zaplaceno". Leave `confirm_paid` (the confirm dialog keeps the full sentence).
4. `booking_site.py`: `"expired": {"paid", "clash_refunded", "cancelled"},`.
5. `booking_manage.py`: `"can_decline": b["pay_method"] == "direct" and b["status"] in ("requested", "expired"),`.
6. `booking_direct.py` `decline`: `if booking["status"] not in ("requested", "expired"):` and wrap the `set_status` call: `try: moved = booking_site.set_status(...)` / `except ValueError: return {"error": "not_confirmable"}` / `if not moved: return {"error": "not_confirmable"}`.
7. `booking_checkout.py` `expire_requests`: wrap the `set_status` in `try … except ValueError: continue` and only delete the hold when the row was moved (`if moved and row["hold_id"]`).
8. Tests in `test_booking_direct_0998.py`: (a) an expired direct row can be declined and ends `cancelled`; (b) `expire_requests` with a row already `paid` (set via SQL after the SELECT is impossible, so: create a requested row with `request_expires_at` in the past, confirm it, then call `expire_requests()`) returns 0 and does not raise.
9. `docs/design/catalog.json`: if 0996's commit 57f6799f added `gp-check`/`checkline` for this page only, remove those lines and run `python3 scripts/design_lint.py`; if the lint fails, put them back and note it.

## 5. Do not touch

Stripe flow (`booking_checkout.start`, `booking_webhook.py`), `booking_cancel.py`, CSS files, migrations. Hard rules 6, 7, 9, 10.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_booking_direct_0996.py tests/test_booking_direct_0997.py tests/test_booking_direct_0998.py tests/test_booking_site.py tests/test_booking_setup.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -rs --tb=short 2>&1 | tail -30
python3 ../scripts/design_lint.py 2>&1 | tail -10
```
The lint fixture has no direct rows: for the UX gate, seed one requested and one expired direct row (copy `create_pending(..., status="requested", pay_method="direct")` from the 0998 tests) in a throwaway script, open the page at 390/768/1280 and run `tests/layout_lint.js` on it (`page.evaluate(Path("tests/layout_lint.js").read_text())`); 0 findings for the bookings list and the pay form. Do not commit the script.

## 7. Acceptance

- [ ] No coral button in the bookings list; Mark paid label under 24 characters in EN and CS.
- [ ] Pay form: no `ui-sub` paragraph, help "?" inline after the section title, checkboxes from `ui_check`.
- [ ] Expired direct row shows Decline; decline works; `expire_requests` survives a concurrent confirm.
- [ ] layout_lint.js on the seeded page: 0 findings at 390/768/1280; screenshots at the three widths in the report with one line each on what you saw.
- [ ] Design-system checklist (§5 of design-system.md) pasted and ticked in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; `ui_section` has no working `tip` pattern to copy; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1004-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`booking_site._TRANSITIONS` (Stripe `expired` rows: only direct rows get Decline, keep `can_decline` gated on `pay_method`), template help "?".

## Owner steps

None.
