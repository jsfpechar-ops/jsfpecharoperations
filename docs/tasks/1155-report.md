# 1155 report: revived door code checked on the lock (K-DC-AMBIG)

Status: review
Branch: task/1155-door-ambig-delete (local only, not pushed, no PR opened)

## 1. Files changed (git diff --stat f0050e53^..HEAD)

- App/app/door_codes.py: 101 lines (5 constants, `_lock_code_state`, `_note_failed_lookup`, `_revive_one`, 2 call sites)
- App/tests/test_door_code_ambiguous_delete.py: new, 7 tests
- App/tests/test_door_code_lost_pin.py: 1 fixture line (+2 lines with comment)
- docs/tasks/1155-door-code-ambiguous-delete.md: line 3 set to `Status: review`
- docs/tasks/1155-report.md: this file

Commits: f0050e53 (step 2), 3a03b899 (step 3), 0a223321 (step 4), bb48a687 (step 5), b61be4da (step 6), a8de6f6b (step 8).

## 2. Commands (last lines)

- Step 7/8 37-test set: `37 passed in 2.08s`
- Step 9 bite runs (T = ambiguous_delete file): see section 4.
- Step 10 door-codes row: `287 passed, 2 skipped in 9.42s`; the 2 skips are the `playwright` browser tests (allowed).
- Step 11 ruff (`app tests`, F401/F841 set): `All checks passed!`
- Step 12 Postgres (UBYHOST_DATABASE_URL set, 4 files): `66 passed in 14.23s`
- Pre-report ruff (`app tests tools`, same select): `All checks passed!`
- Context lint: see section 5.

## 3. Brief section 7 (acceptance)

- [x] test_door_code_ambiguous_delete.py: 7 passed; 1149 and cancel-guard tests pass (37 with state test).
- [x] Six revert-bite runs fail as stated; `git status --short` empty afterwards.
- [x] Door-codes row passes with only the two playwright skips; ruff passes; Postgres run passes.
- [x] `grep -c "_lock_code_state\|find_code_by_name" App/app/door_codes.py` prints `4`: the `_lock_code_state` def, its `find_code_by_name` call, the `_revive_one` call to `_lock_code_state`, and the existing `issue()` retry call to `find_code_by_name`.
- [x] The outbound-request reason from brief section 2 is in this report (section 6 below).

## 4. Revert-bite (FAIL lines, all as expected)

- (a) no lookup: `5 failed, 2 passed`
- (b) no re-issue on gone: `4 failed, 3 passed`
- (c) no retry on unknown: `2 failed, 5 passed`
- (d) lookup on every revived row: `1 failed, 6 passed`
- (e) `_revoke_one` skips the check: `1 failed, 6 passed`
- (f) lookup after a definite refusal: `1 failed, 6 passed`

Each run showed `1 file changed, 1 insertion(+), 1 deletion(-)` before the test. Each was reverted with `git checkout`; the tree is clean.

## 5. Context lint

Run after the commit: `context lint: OK`. A WARN says 10 commits touched App/ after the last status.md update; the orchestrator updates status.md at review.

## 6. Outbound-request reason (for the PR)

One extra `POST /v3/lock/listKeyboardPwd` (already in `ttlock.ALLOWED_PATHS`, already used by `issue()` retries through `find_code_by_name`) per revived row whose delete may have run, at most 3 per row, to confirm the guest's PIN still exists before the stay page shows it. No new host. It sends only what `issue()` already sends: lock id, the code name `UH-<row id>` and the stay window. Rows with no delete attempt, and rows already `issued`, cost no call, on every tick.

## 7. Deviations

- Step 1 (branch create) skipped: the worktree was already on `task/1155-door-ambig-delete`, as the session note allowed.
- Commits for steps 2 to 8 have no `Co-Authored-By` / `Claude-Session` attribution lines: the brief's message text was used as given. Local only; amend if the owner wants them.
- Revert-bite check ran with `--tb=no`, so FAIL lines are the summary counts, not test names.
- Step 12 used the already-running Postgres cluster (`pg_ctlcluster` start not needed).

Done: steps 1 to 13 (step 1 skipped as above).

## 8. Questions

None.

## 9. Owner steps left

1. Open a draft PR for `task/1155-door-ambig-delete` and paste the reason in section 6 into its description.
2. When CI is green and reviewed, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8). Merging deploys.
3. Orchestrator then removes K-DC-AMBIG from `docs/context/known-issues.md` and adds one line to `docs/context/decisions.md`.
