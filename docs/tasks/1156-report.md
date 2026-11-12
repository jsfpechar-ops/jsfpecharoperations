# 1156 report: host notice when a lost door code is made again

Status: review
Branch: task/1156-door-reissue-notice (not pushed, no PR opened)

## Files changed (git diff --stat 6a6580ec)

- App/app/door_codes.py: `_tell_host_reissued` helper (one info alert card, dedupe per stay; one host mail, variant `reissued`; swallow-all with log) and one call before `issue()` in `_reissue_lost_pin`.
- App/app/host_i18n.py: en and cs, alert title and detail, mail subject and body (8 lines).
- App/app/host_vi_i18n.py: vi, the same 4 keys.
- App/tests/test_alert_language.py: one `door_code_reissued` fixture entry.
- App/tests/test_door_code_reissue_notice.py: new, 9 tests (6 tests, the copy test run for en, cs, vi).
- docs/tasks/1156-door-code-reissue-host-notice.md: line 3 set to `Status: review`.

## Commands (last lines)

- Door-code, i18n, copy and alert suites (§6 steps 7 to 10 set, `-rs`): `357 passed, 2 skipped` (the 2 skips are `playwright` not installed, as allowed).
- `test_door_code_reissue_notice.py` with lost_pin and ambiguous_delete: `23 passed`.
- Postgres run (`UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest`): `23 passed`.
- Lead lint: `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`.
- Lead tests (test_0280, alert_language, host_i18n, go_host_i18n, no_em_dashes): `55 passed`.
- `python3 scripts/context_lint.py`: see the Deviations section.

## Revert-bite (mandatory)

- (a) FAIL as expected, `4 failed, 5 passed` (no notice). PASS: the bite fails as the brief says.
- (b) FAIL as expected, `2 failed, 7 passed` (one card per call). PASS.
- (c) FAIL as expected, `1 failed, 8 passed` (failing notice stops re-issue). PASS.
- (d) FAIL as expected, `3 failed, 6 passed` (no mail). PASS.
- Each run left `1 file changed, 1 insertion(+), 1 deletion(-)`, and `git status --short` was empty afterwards. The failing test names were not checked one by one; only the counts were compared.

## §7 acceptance

- [x] 9 passed in the new test file.
- [x] Four bites fail as stated; status clean afterwards.
- [x] The named suites pass; the door-codes row passes with only the two `playwright` skips; ruff passes.
- [x] No PIN in card or mail (`test_the_card_and_the_mail_never_hold_the_pin`).
- [x] No UI template or CSS changed; rule 7 and the UX gate do not apply. The card reuses the existing alert component.

## Screenshots

Not required: no template, CSS or guest page changed.

## Deviations

- Step 1: the branch `task/1156-door-reissue-notice` already existed and was checked out, so `git switch -c` was skipped. 1155 is in (`_lock_code_state` present). The brief's expected name `claude/zealous-maxwell-a7ub54` was not the current branch.
- Commits: steps 2 and 3 went into one commit (`71e77c72`), not two. Steps 4 to 7 each have their own commit. Step 8 (the single commit with the brief's message) was not done as a separate commit, since the work was already committed per step.
- Step 4 and 5 scripts and the step 2 helper were written to the scratchpad and run from there.
- Step 9 bites changed the `dedupe_key` line for (b) with a Python replace instead of sed, to avoid quoting problems. The resulting edit is the same.
- Step 13 wording in the brief sets `Status: review`; that line is now set.

## Questions

- Whether the card should be `warning` instead of `info` (one word in `door_codes.py`, step 3). Owner's choice.
- A reviewer who reads Czech and Vietnamese should check the new cs and vi sentences.

## Owner steps left

1. Open a draft PR for `task/1156-door-reissue-notice` after 1155 is merged.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>`.
