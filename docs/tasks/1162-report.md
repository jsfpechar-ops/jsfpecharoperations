# 1162 report: cleaning code lookup paging

Status: review
Brief: docs/tasks/1162-cleaning-code-lookup-paging.md | Branch: task/1162-cleaning-code-paging

## 1. Files changed

- App/app/ttlock.py: `Callable` import; `_read_listing` (the one paging loop); `code_is_listed` thin caller; `codes_named`
- App/app/cleaning_codes.py: `_find` uses `codes_named`; `None` raises a transient `TTLockError`
- App/tests/test_cleaning_code_lookup_pages.py: new, 19 cases
- App/tests/test_door_code_lookup_pages.py: docstring 1157 -> 1160
- App/tests/test_door_code_reissue_notice.py: docstring 1157b -> 1160b
- docs/tasks/1162-cleaning-code-lookup-paging.md: line 3 `Status: review`
- docs/tasks/1162-report.md: this file

Commits: `1162 step 2`, `1162 step 4`, then this report.

## 2. Commands (last 5 lines)

- Step 3 door-code and cleaning tests: `68 passed in 9.95s`
- Step 4 `test_cleaning_code_lookup_pages.py`: `19 passed in 4.18s`
- Step 6 baseline (T, 36 tests): `36 passed in 4.47s`
- Step 7 test-map rows: `372 passed, 3 skipped in 19.38s` (skips: playwright not installed, 3 browser files)
- Step 7 ruff: `All checks passed!`
- Step 8 Postgres (`UBYHOST_DATABASE_URL` set to ubytest): `74 passed in 40.66s`
- Step 9 `scripts/context_lint.py`: `context lint: OK` (warning only: App/ commits after the last status.md update, for the orchestrator)

## 3. Revert-bite (all four as stated)

- (a) `_find` returns None on incomplete list: `13 failed, 23 passed`
- (b) non-list guard off: `16 failed, 20 passed`
- (c) page 1 only: `11 failed, 25 passed`
- (d) name filter dropped: `5 failed, 31 passed`
- `git checkout App/app` after each run; `git status --short` empty afterwards.

## 4. Section 7 acceptance

- [x] Step 4 shows 19 passed; step 3 shows no failure
- [x] Four revert-bite runs fail as stated; status clean afterwards
- [x] Test-map rows pass with only the three playwright skips; ruff passes; Postgres run passes (74 passed)
- [x] `grep -c "listKeyboardPwd" App/app/cleaning_codes.py` -> 0
- [x] The two door-code test files start with 1160 / 1156, 1160b
- [x] Outbound request reason (for the PR): before, 1 `POST /v3/lock/listKeyboardPwd` per `_find`; now 1 to 5 (normally 1, one per page of 20 codes whose name contains the operation name), only on a retry (`attempts > 1`) or a revoke with no stored provider id; at most 25 calls per row. Same endpoint, host and payload plus `pageNo`. Reason: an absent verdict from a partial list adds a duplicate code or leaves a working code on the door. No new personal data.

## 5. Deviations

- Step 1: the brief expected branch `claude/zealous-maxwell-a7ub54`. The worktree already had `task/1162-cleaning-code-paging` checked out, so `git switch -c` was skipped (per the orchestrator's instruction). 1160c anchors checked: present.
- Helper script written to the scratchpad directory instead of `/tmp/1162_step2.py` (session rule). Not committed.
- Commits made per executor.md (`NNNN step k`), not one commit at step 5.
- No other deviations. No file outside brief §3 changed; §5 untouched.

## 6. Questions

None.

## 7. Owner steps left

1. Open a draft PR for `task/1162-cleaning-code-paging` and put the outbound-request reason from section 4 in its description.
2. When CI is green and reviewed, run `scripts/merge-pr-on-green.sh <PR number>`.
