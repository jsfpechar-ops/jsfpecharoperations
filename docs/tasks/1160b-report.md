# 1160b report: door-code re-issue notice

Status: review

## Files changed (vs 1160 merge 627515a8)

- App/app/door_codes.py: notice only after issue() returns True; `_no_email` kind, dedupe key and mail variant when the stay has no guest e-mail; the SQL reads `reservation_claim.email` through a LEFT JOIN.
- App/app/host_i18n.py: en and cs, 4 keys changed and 4 added each (the old "stopped working" sentences are gone).
- App/app/host_vi_i18n.py: vi, the same.
- App/tests/test_door_code_reissue_notice.py: guest e-mail in 3 tests, 2 new tests, copy test for both wordings.
- App/tests/test_alert_language.py: one STORED_KINDS entry.

## Commands (last lines)

- `import app.door_codes`: no output.
- `pytest tests/test_door_code_reissue_notice.py tests/test_alert_language.py tests/test_0280_short_notifications.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py`: 66 passed, 1 warning.
- Clean tree, notice file alone: 11 passed.
- Door-codes row (`test_door_code*`, `test_ttlock*`, smart locks, sm state and parity, copy tests): 378 passed, 2 skipped (both `playwright` not installed), 1 warning.
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed!
- Postgres (UBYHOST_DATABASE_URL set), notice file plus `test_door_code_lookup_pages.py`: 20 passed. The backend in use was not separately checked.
- Pre-report `pytest` on the five copy/lint files: 55 passed (66 with the notice file).
- Old-sentence grep on reissue keys: 0.

## Revert-bite

- (a) `if True:` in `_reissue_lost_pin`: FAIL, 1 failed, 10 passed (`test_a_failed_new_code_sends_no_notice`). PASS on restore: 11 passed.
- (b) always `suffix = ""`: FAIL, 1 failed, 10 passed (`test_a_stay_without_a_guest_email_says_the_guest_sees_the_code_on_the_stay_page`).
- (c) always `_no_email`: FAIL, 3 failed, 8 passed (lost race, ambiguous delete, and the PIN test).
- (d) wrong sentence in host_i18n.py: FAIL, 1 failed, 10 passed (`test_the_copy_exists_in_every_host_language[en-e-mail]`).
- `git status --short` empty after each restore.

## 7 acceptance

- [x] Notice file 11 passed; step 4 66 passed.
- [x] Four revert-bite runs fail as stated; tree clean afterwards.
- [x] Door-codes row and copy tests pass with only the two playwright skips; ruff passes; Postgres run passes.
- [x] Old sentences gone from reissue keys (0).
- [x] No template or CSS changed; the UX gate does not apply.

## Deviations

- Step 1: the worktree was already on task/1160b-door-reissue-notice-fix, not claude/zealous-maxwell-a7ub54. No branch was created or switched.
- Commits were made per step (`1160b step 2`, `step 3`, `step 4`), as executor.md asks. Step 5 has no separate commit.
- Step 3 expected 3 changed files; the diff shows 2 because door_codes.py was already committed in step 2.
- Test names in the bite lines are the full pytest ids.

## Questions

- None blocking. The Czech and Vietnamese sentences are written for a host, not translated word for word, and need a reader's check (owner step 3).

## Owner steps left

1. Open the PR for task/1160b-door-reissue-notice-fix as a draft after 1160 is merged.
2. Ask a Czech and a Vietnamese reader to check the new sentences in the diff of host_i18n.py and host_vi_i18n.py.
3. When CI is green, run `scripts/merge-pr-on-green.sh <PR number>`.
