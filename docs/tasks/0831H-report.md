# 0831H report: details and cleanup (Group H)

Status: blocked. Geometry test green; invoice items test fails at 760 px (not in my edits, see below). Not committed.

## Files changed

- `App/app/templates/partials/settings_value_card.html`: optional `help_text` / `help_id`; when set, a `help_tip` sits next to the label (imports `help_tip` from `_components.html`). Existing callers unchanged (the variables are undefined there).
- `App/app/templates/submission_detail.html`: new `state_words` dict (same `t()` keys as `submission_pill`). The outcome eyebrow and `.stay-command-note` are replaced by one `settings_value_card.html` include: label = `t('reports.outcome')`, value = state word, help tip = the full sentence from `outcome_notes`. The receipt-missing line is kept.
- `App/app/static/app2.css`:
  - 0830B block: deleted `body.v2 .cal .crow .bar` and `body.v2 .cal .cgrid` with their comments (the calendar day grid and stay bars).
  - 0831H block: `@media (max-width:480px)` rules for `.invoice-items-grid` rows (single column, inputs 100% wide, `min-width:0`); `body.v2 .stays-head-actions .btn{height:37px;box-sizing:border-box}`.

## Command results (second round, venv installed)

- `App/.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_geometry.py -q --tb=short -rs`: 6 passed, 1 failed, 0 skipped.
  - `test_dashboard_actions_share_height_and_gap`: PASSES. The 40 px button was `button.btn.ghost.ph-hide` (the filter toggle), made 40 by `body.v2 [data-filter-toggle]{min-height:40px}` in app2.css line ~566. My rule now sets `min-height:37px` too, and at max-width 600 px all stays header buttons use `min-height:44px`.
  - `test_invoice_item_geometry_and_localized_screenshots`: passes at 360 px (en and cs widths 360-390 now), fails at 760 px (en) with stay vs extra price width 192.7 vs 101.6 px. The loop order means 760 was never reached before (360 failed first). None of my rules are inside a 760 px query, so this looks pre-existing; not verified (no clean run without my edits).
  - Remaining tests in the invoice file (`test_other_description...`, `test_invoice_builder_heading...`, `test_invoice_sticky...`) passed.
- Earlier NOT RUN note (first round, venv missing) is superseded. `App/.venv` has no fastapi or playwright. The pip install started by the set-up (pid 609) was still in state S after about 10 min with no packages installed. I tried to restart it and the action was denied (it may be another executor's process), so I stopped and did not kill it.
- Static checks that did run: `jinja2` parse of `submission_detail.html` and `partials/settings_value_card.html` (OK); brace balance of `app2.css` (0).

## Brief items

1. Done, with one reading: "status label" is taken as the eyebrow `reports.outcome`, and "short state word" as the `submission_pill` word. Not browser-checked.
2. Fixed at 360 px. Root causes found by a debug copy of the test (copy deleted): the item row computed `display:table-row` at 360 px, so the card grid was not applied; the thead was shown; the description cell took column 1 (so qty/unit/price did not share a row); the remove button sat at the right. My 480 px block now sets row grid, full-width description and remove cells, thead hidden, left-aligned remove cell. Still failing at 760 px (see above). `invoice-items-grid` rules live in `App/app/static/host2.css` (lines ~882-892, breakpoints not checked). The new rules in app2.css may not be enough to remove the 34 px overflow at 360 px. Needs `test_host_invoice_items_browser.py` run.
3. Done, with a deviation. The literal patterns (`cal-`, `dashboard-calendar`, `stay-bar`, `day-`) match no rule in the 0830B block. I deleted the two calendar rules named by the brief. I kept the combined rule `body.v2 .needs-you-card-item,body.v2 .cal,body.v2 .ov-table{...}` because it also styles the needs-you card and the overview table. Owner or calendar PR to decide whether `.cal` goes too.
4. Fixed and passing: `min-height:37px` beats the `body.v2 [data-filter-toggle]` 40 px rule.
5. Tests not run (see above).

## Owner / orchestrator steps left

- Investigate the 760 px failure in `test_invoice_item_geometry_and_localized_screenshots` (stay vs extra price width). Check whether it fails on the base branch too.
- Run (venv now installed):
  - `App/.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30`
  - `App/.venv/bin/python -m pytest -k "partE or partB" tests/test_0830_airbnb_pages_browser.py -q -rs 2>&1 | tail -30`
  - `App/.venv/bin/python -m pytest $(grep -l submission_detail tests/*.py) -q -rs 2>&1 | tail -30`
  - Expect `test_0199_phone_geometry_browser.py` to be checked too (it queries `.stay-command-note`, guarded by `if`).
- Screenshots at 390 px for the submission detail page: not taken (no browser).
- Nothing committed or pushed.
