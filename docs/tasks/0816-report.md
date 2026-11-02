# 0816 report

Status: blocked (steps 1-3 done; acceptance 7 not met; screenshots taken but not visually reviewed)

## Files changed (uncommitted, nothing committed or pushed)
- App/app/templates/submissions.html, invoices.html, housebook.html, stay_fees.html: h1 wrapper class `head-title-row`; stay_fees: `#fee-list-summary` block removed, databox sub line moved into help body (guarded with `apartment is defined`).
- App/app/static/app2.css: 0791 block (shared help row), 0792 (invoices month row gap 14px, period max-width 360px, filter form margin-bottom 16px), 0793 (housebook card padding 16px, unchanged), 0794 (stay fees `.head` margin-top 16px).
- App/app/templates/base.html: app2.css?v=20261102-0816. App/tests/static_versions.json rewritten by `--write`.
- App/tests/test_host_list_cards_browser.py, test_reporting_help_0097.py, test_host_fee_navigation.py: #fee-list-summary assertions moved to `.stay-fees-page h1` / absent.
- Screenshots: 8 of 9 in docs/tasks/screenshots-0790/ (the 8 page shots, 390 and 1280; not viewed). stay-fees-1280-help-open.png NOT written: the help click timed out in the script. Also submissions-1440.png is an older leftover file.

## Measured (scratch script /tmp/claude-0/scratch-0816/measure.py, not in repo)
- R1 help toggle: +49 px below h1 at 1024+ before; now -4 px (inside the 4 px tolerance). Pass.
- R2 housebook phone card text inset: not measurable (fixture has no housebook rows). Card padding is 16 px. Open.
- R3 invoices month gaps: 0 before (brief) / 8 measured; now 14. Pass.
- R3 invoices filter buttons to empty-state h2: 0 before; now 16. Pass.
- CI test (rightSlack > 40, invoices 1440): 0 before; now 788. Pass.
- R3 stay fees Apply filters to h1: 1 px at 1024 before; the 16 px head margin was added but not re-measured. Unverified.

## Commands
1. Browser geometry: 43 passed, 6 failed, 0 skipped before the last revert. Remaining failures:
   - test_0710 stay_fees 1024/1280/1440: `.head .sub` missing (the removed fee summary line; mockup still has it).
   - test_0710 submissions 390: `.head h1` width 113 px vs mockup 77 px (caused by the new flex row).
   - test_host_button_contrast_browser stay-fees/1280: no small primary buttons found (cause not diagnosed).
2. Static/lint: 15 passed, 3 failed: test_static_versions (app2.css key check after --write), test_static_versions run check, design lint T3 "class not in catalog: head-title-row" on 4 templates.
3. design_lint.py: FAIL, same T3 catalog error.

## Deviations
- Item 3 asks gap:var(--space-3); the root font size makes that 10 px, so 14px used.
- Housebook padding raised to 20px and then reverted to 16px: the mockup test requires 16 px.
- i18n key stay_fees.list.summary left in place (now unused); host.css `.fee-list-summary` rule left (not in brief).
- Environment: my first measure run created App/data/ubyhost.db and App/data/initial_admin_login (gitignored, local dev DB). I deleted initial_admin_login. Owner can delete App/data/ubyhost.db if it was not theirs.

## Questions
1. Keep the removed stay-fees `.head .sub` in the mockup spec, or re-add it?
2. Should the head-title row use a catalog class (name?) so design lint passes?

## Owner steps left
- Decide the two questions above; then re-run commands 1-3 and `.venv/bin/python tests/test_static_versions.py --write` after any app2.css change.
