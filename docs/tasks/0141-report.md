# 0141 report (executor: Haiku 5.5)

Status: done

## Done
- Steps 1 to 6 ran, each `ok`, each committed as `0141 step k`: invoices.html, _list_filter.html, invoice_detail.html, invoice_form.html (+ host2.css block), invoice_stay_picker.html, catalog.json.
- Step 6 counts matched exactly: invoices 4, invoice_detail 17, invoice_form 45, stay_picker 0. `python3 scripts/design_lint.py`: `design lint: OK`.
- Step 7: six test edits applied and `App/tests/test_design_invoices.py` created (commit `ea10037`).
- Step 7 run (with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): 226 passed, 1 skipped (screenshot-only), 1 deselected.

## Stopped at
`App/tests/test_invoice_stay_browser.py:127` (`test_issue_with_javascript_off`): `page.click(".invoice-actions button.accent.primary")` times out. The issue button is now `class="ui-btn ui-btn-primary"` (invoice_form.html:295, brief step 4). This file is not in brief section 3, so I did not edit it (section 8).

## Not run
Step 7 remainder (that selector), step 8 browser run, step 9 static versions, step 10 commit.

## Deviations
- Commits per step (executor rule) instead of one commit at step 10.
- Brief 0140 has not run. All anchors and counts matched anyway, so I proceeded.
- Step 7 pytest with the `-x` flag needs `UBYHOST_BROWSER_EXECUTABLE` set (send-panel test).

## Owner or orchestrator steps
Add `App/tests/test_invoice_stay_browser.py` to brief section 3, change the selector to `.invoice-actions button.ui-btn-primary`, then resume at step 7.

## Session 2 (0141-cont-1)
- Step 1: `App/tests/test_invoice_stay_browser.py` selector now `.invoice-actions button.ui-btn-primary`. Run: `2 passed` (0 skipped). Commit `ee940b9`.
- Step 8 browser set (9 files): `2 failed, 82 passed, 1 warning in 85.08s`, 0 skipped. Only the two known failures, same messages: `Remove height differs from the first control at 360px (en)` and `[('rhythm', 'tabs', [0, 8, 16]), ('rhythm', 'toolbar', [20, 24])]`.
- Step 9: `base.html 1`, `ok`. `test_static_versions.py --write` wrote 32 files; `2 passed`. Key `20261019-0141`.
- Step 10: committed. No PR opened (brief says do not push).
- Not staged: `docs/tasks/0140-properties-v2.md`, `docs/design/pages/properties.md`.
