# 0151 report

Status: blocked

Branch: claude/project-thread-td6fpc (not pushed, no PR). Base 5b10d6a.

## Commits
- 70f3f88 0151 step 1 (host2.css, app.js)
- a1b744c 0151 step 2 (two browser test files)
- 2205fab 0151 step 3 (MASTER.md, stays.md)

## Files changed (git diff --stat 5b10d6a)
App/app/static/host2.css, App/app/static/app.js, App/tests/test_host_filter_panels_browser.py, App/tests/test_host_wide_geometry_browser.py, docs/design/MASTER.md, docs/design/pages/stays.md, this report.

## Commands (last lines)
- `python3 scripts/design_lint.py | tail -3`: `design lint: OK`
- ruff `--select E9,F63,F7,F82,F401,F841` on the two test files: `All checks passed!`
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK`
- Step 4, 8 files, one run: `2 failed, 100 passed, 1 warning in 474.51s (0:07:54)`
- Step 4 rerun of the two failing ids alone: `2 failed, 1 warning in 8.83s`

## Failures (not the skeleton flake only, see Deviations)
Both failed in the first run and in the rerun, same assertion:
- `test_phone_guest_sharing_and_clear_setup_actions[True-360-cs]`, tests/test_onboarding_wizard_browser.py:1518: `assert skeleton.is_hidden()` -> `AssertionError: assert False`
- `test_phone_guest_sharing_and_clear_setup_actions[True-1280-en]`, tests/test_onboarding_wizard_browser.py:1518: `assert skeleton.is_hidden()` -> `AssertionError: assert False`

The other 100 tests in the eight files passed.

## Acceptance (§7)
- [x] Step 1 design lint OK; host2.css and app.js only
- [x] Step 2 ruff passes; only the two test files
- [x] Step 3 context lint OK
- [ ] Step 4 0 failed, 0 skipped: 2 failed
- [ ] Step 5 screenshots and K-T02 row: not done (stopped at §8)

## By eye
Not done. The wizard and stays screenshots were not captured (step 4 stopped).

## Deviations
- Stopped at §8: a test failed twice. The brief allows one rerun of the skeleton flake; the rerun failed again on both ids, so I did not run the 0079/0102 capture steps, did not add K-T02, and did not open a PR.
- Done: steps 1 to 3. Left: step 4 (rerun of the wizard test after the skeleton fix or owner decision), step 5.
- A stray background `cat` (my own typo, no file written) was left waiting on stdin; it did not change the repo.

## Questions
- The two failing ids match the flake signature, but both failed on the rerun too. Should the skeleton wait in the test be fixed, or should K-T02 be accepted and the test marked for a fix in a new brief?

## Owner steps left
None until the question above is answered.
