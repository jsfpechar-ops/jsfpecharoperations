# 0415 report: billing enforcement

Status: review. Branch task/0415-billing-enforcement, worktree w0415.

## Files changed (vs 12f6286, the branch head before the executor's commits)

- App/app/auth.py: read-only guard in require_login (POST refused while paused; paying, account, export, filing paths and impersonation exempt).
- App/app/ttlock.py: allowed_for asks billing.entitlements(owner).ttlock.
- App/app/havel.py: plan_multiplier; weekly and monthly limits scaled.
- App/app/leon.py: plan_multiplier; door cap scaled.
- App/app/icalsync.py: import_paused; paused feeds skipped in sync_all.
- App/tests/test_billing_enforcement.py: copied from docs/plans/billing-0415 (one fixture fix, see Deviations).
- docs/tasks/0415-billing-enforcement.md: Status set to review.

## Commands (§6)

1. `pytest tests/test_billing_enforcement.py tests/test_billing_core.py -q --tb=short -x`
   ```
   ............................                                             [100%]
   28 passed in 1.75s
   ```
2. `pytest tests/test_ttlock.py tests/test_ttlock_host_provider.py tests/test_door_codes_safeguards.py tests/test_havel_support.py tests/test_icalsync.py -q --tb=short -x`
   ```
   ........................................................................ [ 59%]
   ..................................................                       [100%]
   122 passed in 8.22s
   ```
3. leon and havel files (18 files, `ls tests | grep -E '^test_(leon|havel)'`, browser files included)
   ```
   ........................................................................ [ 56%]
   ........................................................                 [100%]
   128 passed in 42.54s
   ```
   No skips in the summary.
4. `pytest tests/test_legal_acceptance.py tests/test_login_acceptance.py tests/test_impersonation_config.py tests/test_auth_forms_no_js.py -q --tb=short -x`
   ```
   .......................                                                  [100%]
   23 passed in 3.42s
   ```
5. `python3 scripts/context_lint.py` (repo root): `context lint: OK`, with the usual WARN list (open briefs naming shared files).

## §7 acceptance

- [x] All commands pass.
- [x] Diff touches only §3 files (6 files, 175 insertions, 6 deletions).
- [x] `grep -n billing App/app/reporting.py` prints nothing.

## Deviations

- Step 7 test fix: the copied test's apartment insert lacked `created_at` (NOT NULL). Added `"created_at": db.utcnow()` to that one insert, as other tests do. Committed separately as `0415 step 7 fix`. The test file is otherwise unchanged.
- Executor checkpoint: the run went past the 25-call checkpoint while step 7 was finishing. All steps were done and verified before the report was written, so the status is review, not blocked.
- Base mismatch: the brief says the base is the head of `claude/billing-phase1-impl`. This branch is not a descendant of it (10 commits on that branch are missing here, including 0414 implementation files such as `_billing_banner.html`). `git diff --stat claude/billing-phase1-impl` therefore shows 0414 files as deletions. The 0415 change itself is the 6 files above. Not rebased, per "already at the right base".

## Questions

- Confirm whether the branch base is correct, or whether it should be rebased on `claude/billing-phase1-impl` once 0414 merges.

## Owner steps left

- None for this brief. Merge via `scripts/merge-pr-on-green.sh` after review; deploy is manual.
