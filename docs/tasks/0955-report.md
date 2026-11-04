# 0955 report

Status: review

## Done
- Step 1: Today before the arrows, class `cal-today`, stylesheet `?v=20261104-0955`. Commit `0955 step 1`.
- Step 2: two-row grid at >= 768 px. Commit `0955 step 2`.
- Step 2b (owner decision, no ellipsis): with `.has-panel` at >= 1024 px the period title is `clamp(18px, 18px + (100vw - 1024px) * 0.1, 32px)`, so it stays on one line and reaches 32 px from 1280. Stylesheet `?v=20261104-0955b`. Commit `0955 step 2b`.
- Step 3: `test_0955_calendar_toolbar_stable_browser.py` (15 tests).
- Part A: stay page id line (`[data-guest-id-line]`) with birth date and nationality, in desktop table and phone list. Document number removed after CI (owner decision: privacy rule stands; test_0525 unchanged). Commit `0955 step A`.
- Part B: stay-fee detail `data-fee-guest-facts` line; route reads facts for display only; i18n `stay_fees.guest.age` in en/cs/vi. Commit `0955 step B`.
- Part D: `test_stay_fee_detail.py::test_guest_line_shows_birth_date_age_and_nationality` (passed). `test_0955_guest_details_browser.py` (2 tests, 390/768/1280, passed, 0 skipped). Commit `0955 step D5/D7`.
- Part C: test not written in this session (see Deviations).

## Tests (From App/, 0 skipped)
- `test_0955_calendar_toolbar_stable_browser.py`: `15 passed in 40.87s`.
- `test_dashboard_calendar_browser.py` + 0905 + 0898: `48 passed in 108.48s`, no skips.
- `test_0955_guest_details_browser.py`: `2 passed in 11.11s`.
- `test_stay_fee*` + `test_*_i18n.py`: `184 passed` (before the D6 test was added); D6 test: `1 passed`.
- `test_layout_lint_browser.py`: `3 passed in 209.62s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Screenshots (docs/tasks/screenshots-0955/)
- Calendar 768, 1024, 1280 (`calendar-0955-*.png`).
- Calendar month 390: `calendar-calendar-en-390.png`. Opened: the month grid fits.
- Stay page 390, 768, 1280 (`calendar-0955-stay-*.png`). 390 opened: id line on its own line under the name, readable.
- Stay-fee detail 390, 768, 1280 (`calendar-0955-fee-*.png`). 390 opened: "Date of birth ... · Age 36 at check-in · Germany" sits under each guest name and wraps to 2 lines; readable.
- Calendar week 390: not captured.

## Deviations
Done: Steps 1 to 3, 2b, A, B, D (D5, D6, D7). Left: Part C test; calendar week 390 shot; PR.
Shot helper names files with a `calendar-` prefix (from `shot()`), so the stay and fee files carry it too.
Fee screenshots: the brief's fixture (`test_stay_fee_pay_steps_browser.py`) opens `/stay-fees`, not `/stay-fees/<id>`, so the fee shot test uses the `host` fixture from `test_stay_fee_detail.py` (reuse, no new fixture).

- 0710 mockup match (CI browser shard 4): the phone guest row keeps the id line on its own line; `App/tests/v2_mockup.py` `stay` spec has a documented `phone_box_skip` (row height, `b`/`small` width and height). Josef: guest details must stay visible on phone. `test_0710` stay 320/390 now pass.

## Questions
None.

## Owner steps left
None.
