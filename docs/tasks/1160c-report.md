# 1160c report: lookup answer guard

Status: review

## 1. Files changed

```
App/app/ttlock.py                        | 20 ++++++------
App/tests/test_door_code_lookup_pages.py | 52 ++++++++++++++++++++++++++++++++
docs/tasks/1160c-door-lookup-answer-guard.md (status line 3 only)
```
Commit: `f83d6a83 1160c: a lock answer without a list is unknown; a full page always reads on`

## 2. Commands (last 5 lines)

- Step 3, five test files: `49 passed in 1.59s`
- Step 5 (a) guard off: `5 failed, 19 passed in 0.68s`
- Step 5 (b) missing list as gone: `5 failed, 19 passed in 0.65s`
- Step 5 (c) pages trusted: `2 failed, 22 passed in 0.74s`
- Step 5 (d) match on name: `1 failed, 23 passed in 0.64s`
- Step 6, test-map row: `321 passed, 2 skipped in 10.21s` (skips: two playwright, `test_property_navigation_browser.py`, `test_ttlock_setup_0954_browser.py`)
- Step 6, ruff: `All checks passed!`
- Step 7, Postgres (UBYHOST_DATABASE_URL set): `30 passed in 7.81s`

## 3. Acceptance (§7)

- [x] Step 3 shows 49 passed.
- [x] Four revert-bite runs fail as stated; `git status --short` empty afterwards.
- [x] Test-map row passes with only playwright skips; ruff passes; Postgres run passes.
- [x] Outbound-request reason: unchanged except that an exact-multiple-of-20 list now costs one extra call (page N+1 comes back empty). Same endpoint, still 1 to 5 calls.

## 4. Revert-bite

- (a) FAIL as stated: `5 failed, 19 passed`
- (b) FAIL as stated: `5 failed, 19 passed`
- (c) FAIL as stated: `2 failed, 22 passed`
- (d) FAIL as stated: `1 failed, 23 passed`

## 5. Deviations

- Step 1: did not run `git switch -c`. The worktree was already on `task/1160c-door-lookup-answer-guard`. The brief's expected branch name `claude/zealous-maxwell-a7ub54` did not match the checked-out branch; the 1160b merge (b5a7b358) is in history.
- Step 2: patch saved to the scratchpad, not `/tmp`. `git apply --check` passed without edits.
- Step 8: no PR opened, no push (per the brief's owner steps and the instruction for this run).
- Step 7: did not check the backend was actually Postgres; the tests passed with the URL set.

## 6. Questions

None.

## 7. Owner steps left

1. Open a draft PR for `task/1160c-door-lookup-answer-guard`.
2. When CI is green and reviewed: `scripts/merge-pr-on-green.sh <PR number>`.
