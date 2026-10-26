# 0414 report: billing trial

Status: review. Executed by Haiku 5.5 in worktree w0414.

## Files changed
Steps 1-6 (one commit each, `0414 step k`), plus `0414 step 1 fix`. Created: App/app/billing_trial.py, App/app/templates/_billing_banner.html, App/tests/test_billing_trial.py, App/tests/test_0414_billing_banner_browser.py, docs/tasks/screenshots-0414/dashboard-390.png. Edited: App/app/signup.py, App/app/routes/admin.py, App/app/scheduler.py, App/app/templating.py, App/app/templates/base.html, App/app/mail.py, App/app/mail_notify.py, App/app/host_i18n.py, App/tests/test_claim_mail.py.

## Commands (last lines)
1. billing_trial + billing_core + billing_invoices: `43 passed in 1.56s`
2. claim_mail + ses_mail + signup + scheduler: `114 passed, 1 warning in 8.65s`
3. browser (0414 banner + dashboard phone): `2 passed in 9.41s`, 0 skipped
4. test_host_i18n: `3 failed, 11 passed`. FAILED: test_language_endpoint_sets_cookie_and_rejects_open_redirects, test_a_signed_in_dashboard_keeps_vietnamese, test_language_endpoint_accepts_vietnamese. Error: `sqlite3.OperationalError: no such table: apartment`. The same 3 fail on claude/billing-phase1-impl with the same command, so they are not caused by this brief.
Lint: `context lint: OK` (warnings only, existing).

## Acceptance (§7)
- [ ] Command 4 not green (pre-existing, see above). Command 3 has 0 skipped.
- [x] Screenshot exists. Looked once: dashboard at 390 px, no horizontal scroll. The billing line is NOT visible in this capture (see Questions).
- [ ] `git diff --stat claude/billing-phase1-impl` shows the 0415 files as deleted (see Questions), besides the §3 files.

## Deviations
- Step 1 test fix: the copied test_billing_trial.py inserted an apartment without created_at (NOT NULL). Added created_at (commit `0414 step 1 fix`).

## Questions
1. test_host_i18n.py fails on the base branch too. Needs a decision: fix separately or accept.
2. `git diff --stat claude/billing-phase1-impl` lists deletions of docs/plans/billing-0415/test_billing_enforcement.py and docs/tasks/0415-billing-enforcement.md. This branch does not contain them. The brief said the base is the head of claude/billing-phase1-impl. Not changed by me; check the base.
3. The 390 px capture shows no billing line. Likely billing is off in the capture fixture. Confirm the banner renders with billing on.

## Owner steps left
None. Do not push. No PR opened (per instructions).
