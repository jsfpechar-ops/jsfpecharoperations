# 0799: Stay fees: remove the sent/paid marks everywhere

Status: todo
Depends on: 0794 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision (#652, 2026-11-02): the stay fee flow has no "Odesláno" (sent) or "Zaplaceno" (paid) marks. Remove the mark buttons, their POST routes, the sent/paid statuses and filter options, their strings and their tests. Keep the database columns (`sent_at`, `paid_at`, `sent_message_id`): no migration.

## 2. Context

- `App/app/routes/stay_fees.py`: `STAY_FEE_STATUSES` (~64-71, drop `sent` and `paid`), `_row_status` (~72-86: a frozen row returns `saved`), POST `/stay-fees/{apartment_id}/filings/{filing_id}/sent` (~797) and `/paid` (~824): delete both handlers and any helper only they use.
- `App/app/templates/stay_fee_detail.html` ~154-190: `<h3 class="fee-send-marks-title">` and the `.fee-send-marks` block: delete. Keep the PDF button and the rest of the send panel.
- `send_panel` context in the route: drop `sent_at`, `paid_at`, `sent_message_id` keys if nothing else reads them.
- Brief 0796 runs at the same time on `stay_fees.html`, `app2.css` and layout tests: do not touch those.

## 3. Files

`App/app/routes/stay_fees.py`, `App/app/templates/stay_fee_detail.html`, the stay-fee module the routes call (only functions used solely by the deleted routes, e.g. `mark_sent`/`mark_paid`; grep callers first), locale files (`grep -rln "send.mark_sent" App/app`; delete the keys `stay_fees.status.sent`, `stay_fees.status.paid`, `stay_fees.send.marks_title`, `sent_on`, `paid_on`, `message_id`, `message_id_label`, `mark_sent`, `mark_paid`, `undo_sent`, `undo_paid` only when no other template or code uses them), CSS rules for `.fee-send-marks*` in `App/app/static/*.css` (delete), and tests under `App/tests/` that exercise the deleted routes or strings (delete those test functions; update assertions that list the statuses).

## 4. Steps

1. `grep -rn "mark_sent\|mark_paid\|/sent\"\|/paid\"\|fee-send-marks\|status.sent\|status.paid\|sent_message_id" App/app App/tests | grep -v invoice | head -40`. Write the list in the report.
2. Delete as in §2/§3. Keep anything an invoice or another feature uses (invoices have their own `/paid`: never touch it).
3. Run the commands.

## 5. Do not touch

`stay_fees.html`, `app2.css` 0794 block, migrations, invoices, anything outside §3.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_fee_setup_compatibility.py tests/test_host_i18n.py tests/test_privacy_first.py -q --tb=short`
2. `.venv/bin/python -m pytest tests/test_design_lint.py -q --tb=short`

## 7. Acceptance

- [ ] grep from step 1 (minus invoice lines) returns nothing except DB column reads in the stay-fee module.
- [ ] Commands 1-2: 0 failed (list any failure whose cause is 0796's files by name; do not fix it).

## 8. Stop and ask

Blocked if a deleted function has a caller outside stay fees, a migration seems needed, a fix fails twice, or 30 tool calls.

## 9. Report

`docs/tasks/0799-report.md`, 300 tokens at most. Do not commit or push.
