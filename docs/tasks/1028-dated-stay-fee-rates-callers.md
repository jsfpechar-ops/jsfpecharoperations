# 1028: dated stay-fee rates, part 2 of 3: call sites, save hook, guest estimate

Status: ready
Depends on: 1027 merged | Base: `origin/main` after 1027 | Branch: `claude/dated-rates-1028` | No PR (push only)
Executor: Haiku 5.5, one run, 30 tool calls. No template or CSS change in this brief (the host date field is 1029).

## 1. Objective

1027 added `stay_fee_rate.py` (`schedule_for`, `rate_on`, `is_uniform`, `record`), per-night pricing in `stay_fee.property_period`/`charge_for_reservation`, and `stay_fee_filing.correction_rate`. Today every caller still forces ONE rate. Wire them so a rate change is recorded with a date and used per night, and sealed periods stay frozen.

Rules (decided):
- Seal of a new period: `rate_czk=None` (price per night). Correction of a sealed period: `rate=stay_fee_filing.correction_rate(apartment, sealed)` (None for a mixed period, the sealed flat rate otherwise).
- When a save changes the rate, call `stay_fee_rate.record(apartment_id, new_rate, effective_from)`. `effective_from` = form field `stay_fee_rate_from` (ISO date) if present and valid, else today. A past date is clamped to today (never an error, never retroactive). First-ever rate: `record` itself uses 2000-01-01.
- Guest estimate: amount is per night; the JS live recalculation (`live`) is switched off (`None`) when the stay spans two rates, because signature.js multiplies by one rate.

## 2. Files

| Path | Action |
|---|---|
| App/app/routes/stay_fees.py | edit: 3 sealed-rate call sites + the seal handler (step 1); optionally a helper `rate_effective_from(form)` (step 3) |
| App/app/stay_fee_auto.py | edit: `confirm` (step 1) |
| App/app/routes/guest.py | edit: `_fee_liable_days`, `_fee_estimate` (step 2) |
| App/app/routes/admin.py, App/app/routes/onboarding_wizard.py | edit: call `record` after the apartment write (step 3) |
| App/tests/test_stay_fee_rate_dates_1028.py | create (step 4) |
| docs/tasks/1028-report.md | create |

## 3. Steps

Same conventions as 1027 (anchors with `grep -nF`, STOP when missing, commit `1028 step k`, attribution lines, `| tail -30`). Step 0: clean tree, `git checkout -B claude/dated-rates-1028 origin/main`; `ls App/app/stay_fee_rate.py` must exist, else STOP (1027 not merged).

1. **Sealing and correction.**
   - `routes/stay_fees.py`: three places pass `rate=sealed["rate_czk"]` (`grep -nF 'rate=sealed["rate_czk"]' App/app/routes/stay_fees.py`, about lines 780, 1030, 1254). Replace each with `rate=stay_fee_filing.correction_rate(apartment, sealed)` (the 1254 one stays inside its `if correcting else None`).
   - Seal handler (about line 1263): `rate = period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])` then `save(..., rate_czk=rate, ...)`. Change so `save` gets `rate_czk=stay_fee_filing.correction_rate(apartment, sealed) if correcting else None`, and delete the now unused `rate` variable only if nothing else reads it (grep within the function).
   - `stay_fee_auto.confirm` (about line 72): `rate_czk=None` in the `save` call; drop the `rate` line if unused.
   Check: `.venv/bin/python -m pytest tests/test_stay_fee_finalize.py tests/test_stay_fee_auto.py tests/test_stay_fee_auto_job.py tests/test_stay_fee_bulk_0845.py tests/test_stay_fee_rate_dates_1027.py -q --tb=short -x 2>&1 | tail -30`. Commit.

2. **Guest estimate.** `routes/guest.py`:
   - `_fee_liable_days` (about line 2265) returns the liable day count; add a sibling returning `(days, amount)`: call `stay_fee.guest_period(typed, reservation, date.min, date.max, apartment=apartment, schedule=stay_fee_rate.schedule_for(apartment))`, apply `_apply_scope_boundary`, return `(share["liable_nights"], share["amount_czk"])`, `(0, 0)` for None. Keep `_fee_liable_days` as a thin wrapper if other code calls it (`grep -n "_fee_liable_days" App/app/routes/*.py App/tests/*.py | tail`).
   - `_fee_estimate` (about line 2293-2301): `amount` = that per-night amount instead of `days * rate`; `rate` stays the current column rate; `live` becomes `None` when `not stay_fee_rate.is_uniform(schedule, first_night, last_night)` (first_night = start + 1 day, last_night = end, parsed with `validation.parse_iso_date`). Add `from .. import stay_fee_rate` in the function like the existing local imports.
   - `_fee_pay_panel` (about line 2180) needs no change: `charge_for_reservation` already returns the per-night total; `rate` shown is the last-night rate (see Questions).
   Check: `tests/test_stay_fee_guest_pay_0897.py tests/test_stay_fee_pay_steps.py tests/test_stay_fee_rules_1026.py tests/test_stay_fee_obec_0898.py`. Commit.

3. **Save hook.** The rate is written by every path that applies `stay_fee_routes.fee_form_values(form)`: `grep -n "fee_form_values" App/app/routes/admin.py App/app/routes/onboarding_wizard.py | tail`. There must be exactly the call sites at about admin.py 1723, 1780, 2339 (2339 is a draft/refusal render: do NOT record there) and onboarding_wizard.py 252. For each real write (apartment insert/update, after the DB write succeeded and inside the same request), call a new helper in `routes/stay_fees.py`:
   `def record_rate_change(apartment_id: int, new_rate: int, form) -> None`: parse `_form_str(form, "stay_fee_rate_from")` with `date.fromisoformat` (invalid or empty -> today; earlier than today -> today), then `stay_fee_rate.record(apartment_id, new_rate, effective_from)`; swallow nothing else.
   Find the write by following the payload: `grep -n 'db.update("apartment"\|db.insert("apartment"' App/app/routes/admin.py App/app/routes/onboarding_wizard.py | tail`. Call `record_rate_change` only when the payload contains `stay_fee_rate_czk`. If a path updates the column in a way you cannot follow in 2 reads, or there are more than 4 write sites, STOP and report them.
   Also `grep -rn "stay_fee_rate_czk" App/app --include=*.py | grep -i "update\|SET" | tail`: any other UPDATE of the column (besides `db.py`'s one-time reset) goes in the report.
   Commit.

4. **Tests** `App/tests/test_stay_fee_rate_dates_1028.py`:
   - seal with a mixed fixture (rows inserted directly like 1027) through `stay_fee_auto.confirm` stores `rate_czk == rate on the last day`, `total_due_czk == 140`, payload has `rate_segments`; the sealed row is unchanged after a later row `(2026-05-01, 99)`.
   - correction of a sealed legacy flat period (row `rate_czk` 30, schedule now 30 then 99 from after the period) recalculates at 30: `correction_rate` returns 30; of a mixed period returns None and the total stays 140.
   - admin edit changes the rate 30 -> 45 with `stay_fee_rate_from` = today (use the HTTP editor test helpers in `App/tests/test_property_form_save.py`: `host`, `_payload`, `_apartment`) -> a row `(today, 45)` exists and a night in the past is still priced 30; a past `stay_fee_rate_from` is stored as today; no `stay_fee_rate_from` -> today; an unchanged rate adds no row.
   - guest estimate (`_fee_estimate`, import as in `test_stay_fee_rules_1026.py`) over a rate change: amount per night, `live is None`; over a single rate: `live` present, unchanged amount.
   Run these plus the test-map row `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_property_form_save.py -q --tb=short 2>&1 | tail -30`. Commit, report, `Status: review`, push `claude/dated-rates-1028`. No PR.

## 4. Acceptance

- [ ] New seal and the daily auto-seal price per night and store the last-day rate plus segments.
- [ ] Corrections of a sealed period: legacy flat rate kept, mixed period priced per night.
- [ ] Any rate change through editor, create or wizard writes a dated row; never in the past; unchanged rate writes nothing.
- [ ] Guest estimate/pay total per night; live JS estimate off for a stay across a rate change.
- [ ] No template, JS or CSS changed; no new dependency.

## 5. If unsure, STOP and report

- More than 4 apartment write sites for the rate, or one you cannot follow in 2 reads.
- `correcting` branch variables differ from the names above and the replacement is not obvious.
- A test needs the guest page markup changed (that is a UI change: report it, do not do it).
- 25 tool calls reached: commit, report `Status: blocked` with `Done: steps 1 to k. Left: ...`.

## 6. Questions for the owner (report)

1. The guest pay panel shows "N CZK per person for each counted night" with the last-night rate. For a stay across a rate change that line is slightly off while the total is right. Hide the line in that case (needs a guest-page change and browser tests, a follow-up brief)?
2. Booking-site city tax display (`booking_site.py`) keeps using the current column rate. Leave?
