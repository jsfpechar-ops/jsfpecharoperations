# 0417 report: billing jobs

Status: review

## Files changed
- App/app/billing_jobs.py (create, copy of docs/plans/billing-0417/billing_jobs.py)
- App/tests/test_billing_jobs.py (create, copy)
- App/app/scheduler.py (_job_billing now calls billing_jobs.run())
- App/app/mail.py (kind billing_overdue, both lists)
- App/app/mail_notify.py (build_billing_overdue, billing_overdue)
- App/app/host_i18n.py (6 EN keys, 6 CS keys)
- App/tests/test_claim_mail.py (pinned kinds)
- docs/tasks/0417-report.md

## Commands
1. `.venv/bin/python -m pytest tests/test_billing_jobs.py tests/test_billing_trial.py tests/test_billing_order.py tests/test_billing_invoices.py tests/test_billing_core.py -q --tb=short -x 2>&1 | tail -30`
   ```
   ...............................................................          [100%]
   63 passed in 4.07s
   ```
2. `.venv/bin/python -m pytest tests/test_claim_mail.py tests/test_ses_mail.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`
   ```
   73 passed, 1 warning in 5.97s
   ```
3. `python3 scripts/context_lint.py 2>&1 | tail -30` (repo root): `context lint: OK` (warnings only, pre-existing)

## Acceptance (§7)
- [x] All commands pass.
- [x] Diff shows only the §3 files (plus this report).

## Deviations
- Step 4 (host_i18n) edits were made in the same commit as step 3c (test_claim_mail.py). Step 4 has an empty commit "0417 step 4" marking it.
- No push and no PR: the owner's instruction for this run was "do not push". Owner to push and open the PR.
- App/.venv (untracked symlink) was left out of the commits.

## Questions
- None.

## Owner steps left
- Push `task/0417-billing-jobs` and open the PR, then merge with `scripts/merge-pr-on-green.sh`.
