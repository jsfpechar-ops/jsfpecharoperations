# 0851: Unit test leftovers for the v2 Faktury and Poplatek z pobytu pages

Status: todo
Depends on: 0796, 0799 (in checkout) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix the non-browser failures of PR #707 (CI job test-postgres-full, run 41446464644) listed in §2. Static versions and design lint are NOT yours (0798).

## 2. Context

- `tests/test_design_fees.py::test_fee_list_and_detail_have_the_v2_shells` (assert 0 == 1) and `::test_templates_have_no_raw_style_or_legacy_control` (stay_fees.html)
- `tests/test_design_invoices.py::test_invoice_list_has_the_v2_list_shell` (0 == 1) and `::test_templates_have_no_raw_style_or_legacy_control` (invoices.html)
- `tests/test_page_help_0277.py::test_every_main_page_has_one_closed_help[en|cs|vi]`: stay_fees has no (or more than one) closed help disclosure. Fix the page: exactly one closed `details.ui-how` like `/reservations` has (`grep -n "ui-how" App/app/templates/reservations.html App/app/templates/host_page.html`).
- `tests/test_stay_fee_pay_steps.py::test_steps_are_locked_until_the_period_is_confirmed`: expects `class="ui-section fee-pay"`; the v2 page uses `.card.fee-pay`. Update the selector; keep the lock assertions.

Rule: the v2 pages intentionally use the stays list markup (`.head.stays-head`, `.card.stays-desk`, `.stays-phone`, `.btn`) instead of the old ui-* list shell. Where a test asserts the old shell, update it to the v2 markup (comment "v2, 0792/0794"); do not put old classes back. A "legacy control" check: if it flags `.btn`/`.pill` that the v2 stays page also uses, exempt the page like 0795 did for housebook in `test_design_reports.py`; if it flags a raw `style=` attribute, remove the style from the template.

## 3. Files

The four test files above; `App/app/templates/stay_fees.html` (help disclosure, raw styles only), `App/app/templates/invoices.html` (raw styles only).

## 4. Steps

Run each test, read the assertion, fix per §2, rerun.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS. Another executor (0850) edits invoices.html/housebook.html and app2.css at the same time: small exact Edit replacements only.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

`.venv/bin/python -m pytest tests/test_design_fees.py tests/test_design_invoices.py tests/test_page_help_0277.py tests/test_stay_fee_pay_steps.py -q --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0851-report.md`, 250 tokens at most. Do not commit or push.
