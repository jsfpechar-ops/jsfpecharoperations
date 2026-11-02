# 0894 report (Haiku executor, second pass)

Status: blocked
Base: 41e86bd3 (branch claude/project-thread-56y70c). Nothing committed or staged; no push.

## Files changed (this pass, on top of the committed WIP)
- `App/app/static/admin2-system.css`: added desktop `.ui-btn` 40 px (>=1024 px), `.ui-btn-group` 8 px gap with `form+form` margin 0 (funnel ads export geometry).
- `App/app/templates/admin_operations.html`: filings title no longer split by `tip_label`, so "Hlášení vyžadující pozornost" is one text node; `help_tip` imported; CSS key bumped to `0894e`.
- `App/app/templates/admin_billing.html`: CSS key bumped to `0894e`.
- `App/tests/static_versions.json`: regenerated with `--write` (45 files).

## Fixes and checks
1. Czech title (test_admin_operations.py ~line 103): fixed. Last lines: `7 passed in 1.40s`.
2. Funnel ads export button 37 px vs 40: NOT pre-existing. Base 41e86bd3 passes, branch HEAD a9d7ebf9 fails. Fixed in our files (billing page hosts that section). Last line: `2 passed in 3.97s`.
3. Design guardrails (admin layout): NOT pre-existing either, and NOT fixable in our files. Main passes; the branch fails with 71 findings on admin-users, admin-customers and admin-customer (table past right edge at 390 px, tap targets 37 px and 24 px on "?"). Those pages load `admin2.css` (0893) and are out of this brief's scope. Owner of 0893 must fix.

## Commands (last lines)
- `tests/test_admin_operations.py tests/test_billing_admin.py tests/test_admin_funnel.py tests/test_admin_section_tabs.py tests/test_design_admin.py tests/test_static_versions.py`: `34 passed in 4.18s`
- `tests/test_0419_admin_billing_browser.py tests/test_funnel_ads_geometry_browser.py tests/test_0893_admin_airbnb_browser.py tests/test_0894_admin_airbnb_billing_ops_browser.py` (with -rs): `33 passed in 37.36s`, 0 skipped.
- `tests/test_design_guardrails_browser.py`: `E     admin-customer 390 open: ['tap-target-small', 'button.help-tip-btn "?"', 25, 24]` / `AssertionError: 71 admin layout findings`, `1 failed, 10 passed in 68.23s`.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Acceptance (§7)
- [x] Command 1 (0894 test) passed, 0 skipped (within the 33 above).
- [x] Command 2 except guardrails (not in §6 list, but in the executor's list) passed.
- [ ] Form/table/section counts before and after: NOT done.
- [x] 390 and 1280 screenshots exist in `docs/tasks/screenshots-0894/` (from the first pass; not re-taken).
- [ ] Taps for "mark an invoice paid" and "export the month": NOT measured.

## Deviations
- Funnel group uses literal `8px` gap, not `var(--space-2)`: that token computes to 7 px on these pages.
- Guardrail failure left as is (outside the touch list).

## Questions
- Owner of 0893: fix `admin2.css` (or the admin-users, admin-customers, admin-customer templates) so the guardrail test is green. Cause: table overflow at 390 px and 37 px tap targets on those pages, which main did not have.

## Owner steps left
1. Assign the guardrail findings to the 0893 owner, then rerun `tests/test_design_guardrails_browser.py`.
2. Look at the 390 px screenshots of billing and operations.
3. Measure the two taps on staging.
4. Commit and open the PR after the above.
