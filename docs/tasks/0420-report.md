# 0420 report: paid-plan legal copy, ČSOB export fit

Status: review

## Files changed
- App/app/bank_import.py (copy of docs/plans/billing-0420/bank_import.py)
- App/tests/test_bank_import.py (copy of docs/plans/billing-0420/test_bank_import.py)
- App/app/terms_i18n.py (§ 15 EN+CS)
- App/app/privacy_policy_i18n.py (§ 11 EN+CS)
- App/app/host_i18n.py (billing.admin.statement.done EN+CS)
- docs/tasks/0420-report.md (this file)
- docs/tasks/0420-billing-legal-csob.md (Status line only)

## Commands
1. `.venv/bin/python -m pytest tests/test_bank_import.py tests/test_billing_admin.py tests/test_billing_invoices.py -q --tb=short -x`
   Last lines: `29 passed in 4.45s`
2. `.venv/bin/python -m pytest tests -q --tb=short -p no:randomly -k "terms or privacy or legal or retention"`
   Last lines: `194 passed, 4705 deselected in 32.36s`
3. `python3 scripts/context_lint.py` (repo root)
   Result: `context lint: OK` (warnings only, about open briefs naming shared files)
4. `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841`
   Result: `All checks passed!`

## Acceptance (§7)
- [x] All commands pass.
- [x] Diff touches only the §3 files.

## Deviations
- Step 1 and step 2 were committed separately as `0420 step 1` and `0420 step 2`.
- Not verified: the brief's base commit (head of claude/billing-phase1-impl) and the 0418/0419 dependencies.

## Questions
- None.

## Owner steps left
- Review and merge the PR through scripts/merge-pr-on-green.sh. Production deploy is manual.
