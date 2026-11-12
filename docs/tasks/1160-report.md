# 1160 report: door lookup hardening

Status: review

## Files changed (`git diff --stat` from the base, 4 files plus the new test file)

- App/app/ttlock.py: `LIST_PAGE_SIZE`, `LIST_MAX_PAGES`, `code_is_listed` (39 lines added)
- App/app/door_codes.py: `_lock_code_state`, `_delete_result_unknown`, `_note_failed_lookup(row_id, claim, claimed)`, the `issued -> revoke_pending` UPDATE now clears `last_error`
- App/tests/test_door_code_ambiguous_delete.py: fixture patches `code_is_listed`; 2 assertions changed to `lookup_failed:<n>`
- App/tests/test_door_code_recancel.py: fixture patches `code_is_listed`
- App/tests/test_door_code_lookup_pages.py: new, 9 tests
- docs/tasks/1160-door-lookup-hardening.md: line 3 set to `Status: review`
- docs/tasks/1160-door-lookup-hardening-report.md: this file

## Commands (last lines of output)

- Step 2 import check: no output; `git diff --stat` 4 files changed, 88 insertions, 40 deletions.
- Step 3: `41 passed in 1.28s` (1149, 1155, 1155b, cancel_guard and lost_pin files with the new file).
- Step 5 revert-bite, `T` = lookup_pages + ambiguous_delete:
  - (a) `7 failed, 9 passed in 0.69s`
  - (b) `2 failed, 14 passed in 0.57s`
  - (c) `1 failed, 15 passed in 0.65s`
  - (d) `1 failed, 15 passed in 0.67s`
  - (e) `1 failed, 15 passed in 0.67s`
  - `git status --short` after: empty.
- Step 6: `311 passed, 2 skipped in 10.32s` (both skips are `playwright` not installed); `All checks passed!` (ruff).
- Step 7 (Postgres, `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest`): `22 passed in 6.22s`.
- Step 8: context lint, see the commit log.

## Bite lines

- FAIL (a) stop after page 1: 7 failed (`code_on_page_two_is_present`, `code_missing_from_every_page_is_gone`, `list_longer_than_the_page_limit`, `answer_without_a_pages_field`, `cancelled_stay_whose_code_is_on_page_two`, `revived_row_whose_code_is_on_page_two`, `incomplete_list_keeps_a_cancelled_row_pending`)
- FAIL (b) incomplete counts as gone: 2 failed (`list_longer_than_the_page_limit`, `incomplete_list_keeps_a_cancelled_row_pending`)
- FAIL (c) no pages field, no read-on: 1 failed (`answer_without_a_pages_field`)
- FAIL (d) claim counted as a lookup: 1 failed (`lookups_through_the_claim_give_up_after_exactly_three`)
- FAIL (e) stale error kept: 1 failed (`stale_error_on_an_issued_row_does_not_hide_a_lost_pin`)
- PASS on the restored code: 41 passed (step 3), 22 passed on Postgres.

## Acceptance (§7)

- [x] `test_door_code_lookup_pages.py` has 9 tests, all pass; the 41-test run includes the 1149, 1155 and 1155b files.
- [x] The five revert-bite runs fail as stated; `git status --short` is empty afterwards.
- [x] Door-codes row passes with only the two `playwright` skips; ruff passes; Postgres run passes (22).
- [x] Report repeats the outbound-request reason below and notes `cleaning_codes._find`.

## Outbound request (for the PR description, rule 2)

`_lock_code_state` used 1 `POST /v3/lock/listKeyboardPwd`; it now uses 1 to 5 (one per page of 20 codes, stopping at the page that holds the code, at the last page, or at the limit of 5). Same endpoint (already in `ttlock.ALLOWED_PATHS`), same host, same payload plus `pageNo`; only for a revived row whose delete may have run, or an unmapped delete refusal; at most 3 lookups per row. Reason: concluding that a PIN is gone from a partial list leaves a working PIN on the door or a second code on the lock. No new personal data.

Not changed here: `cleaning_codes._find` has the same page-1 limit with an exact operation name (orchestrator note for known-issues).

## Deviations

- Step 1: the worktree was already on `task/1160-door-lookup-hardening`, so `git switch -c` was not run. The brief's expected branch `claude/zealous-maxwell-a7ub54` was not checked out; the 1156 check (`_tell_host_reissued`) returned 1.
- Commits: executor.md asks for a commit after each step, so the work is in `1160 step 2` (665ffe01) and `1160 step 3` (729dc460), not one commit at step 4. Step 4's commit has the same five files.
- Step 6 was run with the test-map glob (`tests/test_door_code*.py tests/test_ttlock*.py ...`), not only the 1160 files.

## Questions

- None.

## Owner steps left

1. Open the PR for `task/1160-door-lookup-hardening` as a draft; paste the outbound-request reason above into its description.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>`. Merge 1160 before 1160b.
