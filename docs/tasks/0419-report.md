# 0419 report: operator billing page

Status: review

## Files changed

- `App/app/billing_admin.py` (new, copied from docs/plans/billing-0419)
- `App/app/routes/admin_billing.py` (new, copied)
- `App/app/templates/admin_billing.html` (new, copied)
- `App/app/main.py` (router import and include)
- `App/app/templating.py` (settings tab tuple)
- `App/app/templates/_shell_sidebar.html` (admin menu link)
- `App/app/host_i18n.py` (46 EN and 46 CS keys via insert_keys.py)
- `App/tests/test_billing_admin.py` (new, copied)
- `App/tests/test_0419_admin_billing_browser.py` (new, copied)
- `docs/tasks/screenshots-0419/admin-fakturace-390.png` (new)
- `docs/tasks/0419-report.md` (this file)
- `docs/tasks/0419-admin-billing.md` (Status line only)

## Commands (last 5 lines)

1. `pytest tests/test_billing_admin.py tests/test_bank_import.py tests/test_billing_invoices.py tests/test_billing_order.py -q --tb=short -x`: `40 passed in 4.44s`
2. `pytest tests/test_design_tokens.py tests/test_privacy_first.py tests/test_dev_ui.py tests/test_host_i18n.py -q --tb=short`: `25 passed, 1 warning in 9.81s` (no failures; the 3 known test_host_i18n failures did not occur)
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0419=1 pytest tests/test_0419_admin_billing_browser.py tests/test_0416_plan_page_browser.py -q -rs --tb=short -x`: `2 passed in 7.80s` (0 skipped)
4. `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, pre-existing)
5. `python3 docs/plans/billing-0419/insert_keys.py`: `inserted 46 EN and 46 CS keys`

## Acceptance (§7)

- [x] All commands pass, 0 skipped in the browser run.
- [x] `docs/tasks/screenshots-0419/admin-fakturace-390.png` exists; nothing scrolls sideways at 390 px.
- [x] `git diff --stat` shows only the §3 files (plus the untracked `App/.venv` symlink, which is not committed).

## Deviations

- Commit: one commit at the end, as the run instructions asked, not one commit per step.
- No other deviations. No copied file was edited.

## Questions

- None.

## Owner steps left

- Review the PR (not opened by this run) and merge with `scripts/merge-pr-on-green.sh`.
