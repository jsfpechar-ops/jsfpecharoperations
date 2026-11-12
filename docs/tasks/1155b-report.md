# 1155b report: a delete of a code that is already gone counts as deleted

Status: review

## 1. Files changed (`git diff --stat 24f975af..HEAD`)

- `App/app/door_codes.py`: new `_already_gone` helper above `_reissue_lost_pin`; inner try in `_revoke_one` around `ttlock.delete_code`. 27 lines changed.
- `App/tests/test_door_code_recancel.py`: new, 5 tests (6 cases).
- `docs/tasks/1155b-door-recancel-gone.md`: line 3 set to `Status: review` (step 10).
- `docs/tasks/1155b-report.md`: this file.

## 2. Commands (last lines of output)

- Step 1: `grep -c "def _lock_code_state"` -> `1`.
- Step 2 and 3 import check: no output, exit 0.
- Step 4: `.venv/bin/python -m pytest tests/test_door_code_recancel.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short` -> `32 passed in 0.94s`.
- Step 6 (a): `3 failed, 3 passed in 0.42s`.
- Step 6 (b): `3 failed, 3 passed in 0.39s`.
- Step 6 (c): `1 failed, 5 passed in 0.40s`.
- Step 7 (door-codes row): `293 passed, 2 skipped in 9.50s` (the two skips are the `playwright` skips, nothing else).
- Step 8: `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841` -> `All checks passed!`.
- Step 9 (Postgres): `46 passed in 8.73s`.
- Final ruff with `tools`: `All checks passed!`.
- `git status --short` after the bite runs: empty.

## 3. Acceptance (§7)

- [x] `test_door_code_recancel.py` is 6 passed (5 tests, one parametrized twice); step 4 shows `32 passed` with the others.
- [x] The three revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [x] The door-codes row passes with only the two `playwright` skips; ruff passes; Postgres run passes.
- [x] The real TTLock not-found errcode is still unknown. It is not in the repo, and no value was guessed.

## 4. Deviations

- Step 1: the branch was already checked out as `task/1155b-door-recancel-gone`, so `git switch -c` was not run. The base is HEAD `24f975af` (1155 merged). The `claude/zealous-maxwell-a7ub54` branch name in the brief was not used.
- Revert-bite runs used `-rf` to print the FAILED names. The rest of the command is as in the brief.
- Step 9 ran with `UBYHOST_DATABASE_URL` set. Postgres was reachable, so nothing was skipped. I did not separately confirm which backend the tests used.
- Step 5 commit message is the one the brief gives, with the attribution lines. Steps 2 and 3 have their own `1155b step k` commits, per the executor rules.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR for `task/1155b-door-recancel-gone` as a draft.
2. When CI is green and reviewed, run `scripts/merge-pr-on-green.sh <PR number>`.
3. The orchestrator removes K-DC-RECANCEL from `docs/context/known-issues.md`.
4. If a log line shows the real TTLock errcode for "passcode does not exist" (`ttlock path=/v3/keyboardPwd/delete ... errcode=N`), tell the orchestrator. Mapping it removes the extra lookup.
