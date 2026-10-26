# 0411 report: billing core (B1)

Status: review. Branch `task/0411-billing-core`, base 1255954.

## Files changed (§3)

- `App/app/migrations/0023_billing.sql`: new. 5 tables, 3 indexes, `apartment.ubyport_verified_at`.
- `App/app/config.py`: 5 billing settings after `SIGNUP_NOTIFY_EMAIL`.
- `App/app/billing.py`: new. Prices, statuses, `quote`, `entitlements`, `set_status`, `apply_change`, founder slots.
- `App/app/retention.py`: workspace deletion handles billing tables (3 new statements plus the `billing_account` delete).
- `App/tests/test_billing_core.py`: new, 16 tests.
- `docs/privacy/RETENTION.md`: 2 rows after the Invoices row.
- `docs/tasks/0411-report.md`: new (this file).
- `docs/tasks/0411-billing-core.md`: the brief, copied in with `Status: review`.

## Commands (last lines)

1. `pytest tests/test_billing_core.py` (step 5):
   `................ 16 passed in 1.09s`
2. `pytest tests/test_migrations.py` (step 1):
   `............. 13 passed in 2.73s`
3. `pytest tests/test_migrations.py tests/test_db_*.py`:
   `.................. 18 passed in 5.42s`
4. `pytest test_retention.py test_retention_job.py test_retention_alignment.py test_workspace_termination.py test_privacy_first.py`:
   `....................................................... 55 passed in 13.69s`
5. `python3 scripts/context_lint.py`: `next free: task 0412 | migration 0024` then `context lint: OK`. WARN lines are shared-file overlaps with other open briefs; 0411 is listed on `docs/privacy/RETENTION.md`, which is expected.
6. Step 2 check: `False 100`. Step 3 check: `1488 1950`.

## §7 acceptance

- [x] 0023 applies (test_migrations passes).
- [x] quote matches the strategy table (test passes).
- [x] Billing unset gives UNBILLED (test passes).
- [x] Paused account has `ubyport_submit == True` (test passes).
- [x] Workspace deletion keeps invoices with NULL owner and removes `billing_account` (test passes).
- [x] `git diff --stat` lists only §3 files (plus the brief, see Deviations).
- [x] No stripe/gopay/comgate strings in `billing.py`.

## Deviations

- The brief was not in this worktree. It was taken from commit 64f072b and copied to `docs/tasks/0411-billing-core.md`, then set to `Status: review`.
- Commits: executor.md asks for a commit per step. The caller asked for one commit, so this is a single commit.
- No code deviation from the brief text.

## Questions

None.

## Owner steps left

None for this brief. Billing stays off (`UBYHOST_BILLING_ENABLED` unset). Not pushed, no PR opened.
