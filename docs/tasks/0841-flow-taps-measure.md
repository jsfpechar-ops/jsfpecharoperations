# 0841: Measure taps and typed fields for six flows at 390 px

Status: dropped (script and test removed 2026-11-02: only 2 of 6 flows measurable; numbers kept in 0841-report.md)
Depends on: none (run first; 0836-0840 report against it) | Base commit: b8c87df | Branch: task/0841-flow-taps
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `App/scripts/flow_taps.py`, a Playwright helper that walks six host and guest flows at 390 px and counts taps and typed fields, plus a browser test that runs it on seeded data. It also settles the open items of the 2026-11-02 baseline audit, so speed briefs are judged on numbers, not estimates.

## 2. Context

Baseline estimates (from code, not a browser): add stay 3 taps + 2 typed; guest link copy 2 taps on phone; 2nd guest about 9 taps; invoice about 7 taps; property quick-create 3 taps. Open items to verify (inspect only):
1. Calendar move, extend, cancel: is there any drag/resize or action on a calendar event? (`App/app/static/dashboard-calendar.js`; event click opens details, line 736 area; quick edit is `POST /reservations/{reservation_id}/quick-edit`, `App/app/routes/admin.py` line 3633.)
2. Cleaning mark-cleaned and assign: `App/app/routes/cleaning.py` has no such route on b8c87df (routes at lines 128-398: list, schedule, new, events, edit, delete, properties, code, shares, shared). Confirm in the UI.
3. Single-stay police send (`POST /reservations/{reservation_id}/submit`, `admin.py` line 3827): does the stay page ask the host to confirm before it sends?

**UbyPort rule 1: never press a police send button, batch or single, and never call the submit routes.** Item 3 is answered by reading the DOM (a `data-confirm` attribute, a dialog, or a second step) only.

Playwright is already a test dependency (tests import `playwright.sync_api`). Reusable test helpers: `_launch` and `_browser_session_cookie` in `App/tests/test_invoice_stay_browser.py`; `make_stay` in `App/tests/invoice_stay_helper.py`; `_first_person_done` in `App/tests/test_guest_residence_prefill.py`.

Selectors verified on b8c87df: add stay `[data-toggle-panel="add-stay-panel"]`, `#new_apartment`, `#date_from`, `#date_to`; calendar `[data-cal-day]`, `[data-cal-create]`, `#cal-arrival`, `#cal-departure`, `[data-cal-save]`; invoice `/invoices/new`, `button[name="fill_from_guest"]`, `#buyer_name`; property `/apartments/new`, `#property-create-form`, `#legal_entity_id`; guest `#surname`, `#res_street`; stay row copy `[data-copy^="stay-link-"]`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/flow_taps.py` | new | Recorder + flows + CLI |
| `App/tests/test_flow_taps_browser.py` | new | Seeds data, runs flows at 390 px, writes JSON |
| `docs/tasks/0841-report.md` | new | Report with the numbers table |

No other file may change.

## 4. Steps

1. `App/scripts/flow_taps.py` (standard library + Playwright only):
   - `class Recorder` wrapping a Playwright `page` with `tap(selector)` (click, taps += 1), `type(selector, text)` (fill, typed += 1), `confirm(selector)` (counts a prefilled visible field the user must check: `prefilled += 1`, no input) and `result()` returning `{"taps", "typed", "prefilled"}`.
   - One function per flow, each taking `(rec, base, ids)` and stopping at the last tap **before** saving: `add_stay_panel`, `add_stay_calendar`, `copy_guest_link_row`, `guest_second_person`, `invoice_for_stay`, `property_quick_create`. A flow counts the save tap as `+1` without pressing it, except add-stay and property create, which may save in the test database.
   - Before a fill, read the field's value; if it is already right, call `confirm` instead of `type`.
   - `inspect_open_items(page, base, ids)` returns a dict with keys `calendar_move_extend_cancel`, `cleaning_mark_assign`, `single_send_confirm`, each `{"present": bool, "evidence": "<selector or route>"}`. It only reads the DOM.
   - `main()`: `--base`, `--cookie`, `--ids` (JSON), `--out`; runs all flows at 390×844 and writes JSON. Docstring: owner use against a local dev server only, never production.
   Commit.
2. `App/tests/test_flow_taps_browser.py`: start the app with uvicorn and log in as `test_invoice_stay_browser.py` does; seed one entity, two properties, one stay with a complete guest (`make_stay` and the guest insert pattern of `tests/test_invoice_autofill.py` `_complete_guest`), import `scripts/flow_taps.py` by path (`importlib.util.spec_from_file_location`). Run each flow and `inspect_open_items`; assert every flow returns `taps >= 1`; write the JSON to `$UBYHOST_SHOTS_DIR/flow-taps.json` and one 390 px screenshot per flow's last screen. The guest flow: seed with `_first_person_done` and copy its cookies into the Playwright context; if that does not work within 3 tool calls, mark the guest flow `"not_measured"` with the reason and go on. Commit.
3. Run §6 command 1. Put the JSON as a table in the report: flow, taps, typed, prefilled, baseline estimate; then the three open items with evidence. Commit.

## 5. Do not touch

Any app code, template or static file. Police send routes and buttons (never click them). Wizard, onboarding and property-editor files. No new dependency, no analytics or tracking.

## 6. Commands

From `App/`:
1. `UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0841 .venv/bin/python -m pytest tests/test_flow_taps_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
2. Module row: `.venv/bin/python -m pytest tests/test_flow_taps*.py -q --tb=short -x 2>&1 | tail -30`
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] `docs/tasks/screenshots-0841/flow-taps.json` exists with all six flows and the three open items.
- [ ] No request to `/reservations/*/submit` or `/reservations/submit-ready` during the run (assert it in the test with `page.on("request", …)`).
- [ ] Commands pass, 0 skipped; one 390 px screenshot per flow.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0841-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, the numbers table, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/tests/test_flow_taps_browser.py` (no police request; seeded data only), `App/scripts/flow_taps.py` (no clicks on send buttons).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
2. After each of 0836-0840 merges, the reviewer reruns command 1 and compares the table.
