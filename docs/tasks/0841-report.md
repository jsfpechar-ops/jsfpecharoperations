# 0841 report (flow taps)

Status: blocked
Executor: Haiku 5.5 | Branch: claude/project-thread-vxbrde | Base: b8c87df

## Files changed (uncommitted)

- `App/scripts/flow_taps.py` (new): Recorder, six flows, inspect_open_items, CLI.
- `App/tests/test_flow_taps_browser.py` (new): seeds data, runs flows, writes JSON.
- `docs/tasks/screenshots-0841/` (4 PNGs and flow-taps.json from the failing run).
- `docs/tasks/0841-report.md` (this file).

## Commands

1. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0841 .venv/bin/python -m pytest tests/test_flow_taps_browser.py -q --tb=short -x -rs` FAILED (run 2, same result as run 1):
```
E   AssertionError: ('add_stay_calendar', {'taps': 0, 'typed': 0, 'prefilled': 0, 'not_measured': 'TimeoutError: Page.click: Timeout 30000ms exceeded.'})
E   assert 'add_stay_calendar' == 'guest_second_person'
1 failed in 125.39s (0:02:05)
```
2. Module row: not run (blocked). 3. Context lint: not run.

## Measured numbers (390 px, JSON from run 2)

| Flow | Taps | Typed | Prefilled | Baseline estimate | Note |
|---|---|---|---|---|---|
| add_stay_panel | 2 | 2 | 1 | 3 taps + 2 typed | save counted, not pressed |
| add_stay_calendar | 0 | 0 | 0 | n/a | Page.click timeout |
| copy_guest_link_row | 0 | 0 | 0 | 2 taps | Page.click timeout |
| guest_second_person | 0 | 0 | 0 | about 9 taps | Page.input_value timeout |
| invoice_for_stay | 0 | 0 | 0 | about 7 taps | Page.click timeout |
| property_quick_create | 1 | 0 | 1 | 3 taps | save counted, not pressed |

## Open items (DOM only)

- Calendar move/extend/cancel: not present on the default dashboard view. Code shows cleaning-mode events are draggable (`dashboard-calendar.js` line 242); not checked.
- Cleaning mark/assign: no control on `/cleaning`; `routes/cleaning.py` has no such route.
- Single police send confirm: "no submit form on the stay page". Weak evidence; the stay page may not render that form for this seeded stay. Unverified.

## Deviations

- The commit for step 1 was made before I read the "do not commit" instruction; it was soft-reset, so the file is now uncommitted.
- Step 2 test: flow cookie parameter accepts a list (for the guest session); calendar taps use `:visible` after the first run failed.
- Save steps are counted as +1 tap and never pressed (no writes).
- Timeouts in four flows were not diagnosed; the selectors or seeded state likely differ at 390 px. Not investigated, per the stop rule.

## Questions

- Should the four timed-out flows be re-investigated (layout at 390 px, seeded state), or does the owner accept partial numbers?

## Owner steps left

- Decide the question above. No merge, deploy or secrets involved.

## Update: coordinator follow-up (5 s timeouts, diagnostics)

Status stays: blocked.

Ruff (`.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841`): All checks passed.

Test command 1 (run 3): FAILED in 15.81 s at guest_second_person. Cause: TimeoutError (Page.input_value), which the test correctly does not accept.

Measured numbers (390 px, run 3 JSON in docs/tasks/screenshots-0841/flow-taps.json):

| Flow | Taps | Typed | Prefilled | Result |
|---|---|---|---|---|
| add_stay_panel | 2 | 2 | 1 | measured (estimate 3+2) |
| add_stay_calendar | 0 | 0 | 0 | NotAvailable: no [data-cal-day] on dashboard "/" (0 cells, not just hidden) |
| copy_guest_link_row | 0 | 0 | 0 | NotAvailable: no stay-link copy control on /reservations (add-stay panel present) |
| guest_second_person | 0 | 0 | 0 | TimeoutError: no #surname on /l/<token>/1?lang=en |
| invoice_for_stay | 0 | 0 | 0 | TimeoutError: no fill_from_guest button on /invoices/new |
| property_quick_create | 1 | 0 | 1 | measured (estimate 3) |

Caveat: the NotAvailable results rest on DOM counts for the seeded host only. They are not verified against a real phone layout, and the seeded stay may hide the copy control. Not confirmed.

Open items: unchanged from the first run; calendar, cleaning and single-send checks are unverified.
