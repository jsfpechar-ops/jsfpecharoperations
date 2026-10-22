# 0242: "Send by data box" as the highlighted (primary) button

Status: review
Depends on: 0241 | Base commit: branch head | Branch: claude/project-thread-jf2b3v
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

The owner wants "Send by data box" highlighted so hosts know it is the important step (thread, 2026-10-22). Make it `ui-btn-primary` on the Stay fee list (step 2) and on the report page, keeping one primary per report page.

## 2. Context

- Report page (`App/app/templates/stay_fee_detail.html`): `{% set cta = 'ui-btn ui-btn-primary' %}`; when `frozen`, the header `primary_action` block shows Download PDF as `{{ cta }}`. Test `tests/test_design_fees*.py` asserts the detail has exactly one `class="ui-btn ui-btn-primary"`.
- List (`App/app/templates/stay_fees.html`): `{% set pay_btn = 'ui-btn ui-btn-secondary' %}`; the 0241 form in step 2 uses `class="{{ pay_btn }}"`. The test asserts `'class="ui-btn ui-btn-primary"' not in listing`, and `tests/test_stay_fee_pay_steps_browser.py` `_CHECK_JS` fails if `document.querySelectorAll('.ui-btn-primary').length > 1`.
- Owner exception to the MASTER one-primary rule: on the list, each property card's "Send by data box" may be primary. Nothing else changes.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/stay_fees.html | step 2 databox button class |
| App/app/templates/stay_fee_detail.html | databox button primary; header Download PDF secondary when `send_panel.databox_send` |
| App/tests/test_databox_send_ui.py | assertions |
| App/tests/test_stay_fee_pay_steps_browser.py | primaries count excludes `.fee-databox-send` |
| docs/context/decisions.md | one line |

## 4. Steps

1. `stay_fees.html` step 2 form button: `class="ui-btn ui-btn-primary fee-databox-send"` (not `pay_btn`).
2. `stay_fee_detail.html`:
   - In `#fee-send`, the 0241 button: `class="ui-btn ui-btn-primary fee-databox-send"`.
   - In `primary_action` under `{% if frozen %}`, the Download PDF link: `class="{{ 'ui-btn ui-btn-secondary' if send_panel and send_panel.databox_send else cta }}"`. Check `send_panel` is in scope in that block (it is a page context var); if not, STOP.
3. `test_stay_fee_pay_steps_browser.py` `_CHECK_JS`: `primaries: document.querySelectorAll('.ui-btn-primary:not(.fee-databox-send)').length`.
4. `test_databox_send_ui.py`: in the gateway-on test, assert the list and report each contain `ui-btn ui-btn-primary fee-databox-send`, and the report page has exactly one element whose class contains `ui-btn-primary` outside the filter (`detail.count('ui-btn-primary') == 1`; adjust if the report page has a filter-apply primary and say so). In the gateway-off test assert `fee-databox-send` is absent.
5. `docs/context/decisions.md`: replace the line `- 2026-10-22 ISDS send: draft made on POST only; email links to the app (owner, 0239-0241)` with `- 2026-10-22 ISDS send: draft on POST only; email links to the app; button primary, list exception (owner, 0239-0242)`. Run the lint; if over cap, shorten your line, never others.

## 5. Do not touch

Routes, CSS, i18n, mail. Hard rules 6, 7.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_databox_send_ui.py tests/test_design_fees*.py tests/test_stay_fee_send_panel.py tests/test_stay_fee_pay_steps.py -q --tb=short -x -k "not browser and not geometry" 2>&1 | tail -15`. Root: `python3 scripts/context_lint.py 2>&1 | tail -3`. Browser tests: orchestrator.

## 7. Acceptance

- [ ] Gateway on: the databox button is primary on list and report; report page still has one primary.
- [ ] Gateway off: pages unchanged.
- [ ] Tests and lint pass.

## 8. Stop and ask

As TEMPLATE.md §8.

## 9. Report

`docs/tasks/0242-report.md`, `Status: review`. Do not commit.
