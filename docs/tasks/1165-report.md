# 1165 report: review fixes of 1163 (B1, M1, M2)

Status: review

## 1. Files (git diff --stat 0df37a84 HEAD)

- App/app/cleaning_codes.py (2 lines), App/app/door_codes.py (19), App/app/ttlock.py (25)
- App/tests/test_door_code_ambiguous_delete.py (+24), App/tests/test_ttlock_error_map.py (91), App/tests/test_ttlock_lock_setup.py (new, 160)
- docs/tasks/1165-report.md (new), docs/tasks/1165-errcode-review-fixes.md (Status line only)

Commits: 0aa8d8ad step 2 (code), d729165c step 3 (new test file), 8729af56 step 4 (test edits).

## 2. Commands (last lines)

- Step 4, `pytest tests/test_ttlock_lock_setup.py tests/test_ttlock_error_map.py tests/test_door_code_ambiguous_delete.py -q`: `70 passed in 3.87s`
- §6.2, `pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_cleaning*.py -q -x -rs`: `416 passed, 3 skipped in 22.37s` (skips: `test_property_navigation_browser.py`, `test_ttlock_setup_0954_browser.py`, `test_cleaning_browser.py`, all "No module named 'playwright'")
- §6.3, `ruff check --select E9,F63,F7,F82,F401,F841 app tests`: `All checks passed!`
- Executor pre-report ruff check: `All checks passed!`
- §6.4, `git status --short`: clean; no `App/config` present
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN: 3 commits touched App/ after the last status.md update; orchestrator to update status at review)

## 3. Revert-bite (step 5)

Each case reverts one old behaviour, runs the three test files, restores the file. `git diff --stat` empty afterwards.

- BITES 1 B1 code_missing ambiguous (`LOOKUP_FAILED)` only)
- BITES 6 M1 map -3034 back to config
- BITES 5 M1 delete retry set
- BITES 5 M1 move delay 60
- BITES 2 M1 stale failure cleared
- BITES 2 M1 cleaning retry set
- BITES 3 M2 -1007 on a list is unknown
- BITES 1 Low cleaning _already_gone is False

The counts are the number of failing tests. The script prints counts, not test names.

## 4. Section 7 acceptance

- [x] Step 5 prints eight BITES lines
- [x] B1 test passes; reverting to `LOOKUP_FAILED)` only fails it
- [x] Five lock-side codes map to `lock_setup`; -4063 and 30008 stay `config`
- [x] `lock_setup` delete: retried, `lookups == 0`, one host mail at try 3, `revoke_failed` only past `valid_to`; `config` delete `revoke_failed` at once
- [x] `lock_setup` issue `retrying` then `failed`; `config` issue `failed` at once
- [x] `lock_setup` move waits about 60 min, no mail; later success clears `last_error`
- [x] `-1007` list is `None` from `code_is_listed` and `codes_named`; cleaning retry adds no second code; cleaning delete with unknown lookup not counted deleted
- [x] Commands 1 to 4 of §6 pass; diff only on §3 files

## 5. Deviations

- Step 1: the brief expects branch `claude/zealous-maxwell-a7ub54`. The worktree was already on `task/1165-errcode-review-fixes`, so no branch switch was made. The brief's expected `grep -c CODE_MISSING App/app/ttlock.py` = 2 is wrong: the actual count is 1 (the constant at line 98; the errcode map uses the string). The other step 1 checks matched (`LOCK_SETUP` = 0). All step 2 anchors matched.
- Scripts were extracted from the brief into the scratchpad (`/tmp/claude-0/-home-user-jsfpecharoperations/39c8a7b8-8460-5b3b-80f9-3bc7a1fab9d7/scratchpad/`) instead of `/tmp/`, and run from the worktree root or `App/`.
- §6.2 expects about 417 passed; actual 416 passed, 3 skipped. The three skips are the browser files that need Playwright, which this sandbox lacks. The brief allows these skips and this brief changes no template or CSS. Browser tests were not run here; CI should run them.
- Step 5 prints failing-test counts, not `FAIL` test names.
- Status line in the brief changed from `todo` to `review` (§9). No PR opened, nothing pushed.

## 6. Questions

None.

## 7. Owner steps left

1. Open the PR for `task/1165-errcode-review-fixes` after 1165b is done. Keep it a draft until then.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>` once CI (Postgres) is green.
