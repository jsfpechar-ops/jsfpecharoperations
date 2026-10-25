# 0316 report: Finding your way and Words we use

Status: blocked
Done: steps 1 to 7 (7 committed, but its test fails, see Questions). Left: step 7 test fix, steps 8 to 10, report sign-off.

## Files changed
- App/app/guide_i18n.py (steps 2, 3: 40 en lines and 40 cs lines; 34 keys per language)
- App/app/templates/guide.html (steps 4, 5, 6: sections list, finding and glossary sections)
- App/tests/test_guide.py (step 7: section list)

## Commands
- Step 2: `.venv/bin/python -c "...print(len(...))"` -> `34`
- Step 3: `pytest tests/test_guide.py -q -k same_keys` -> `1 passed, 2 deselected`
- Step 7: `pytest tests/test_guide.py -q --tb=short -x` -> `1 failed`:
  `AssertionError: assert 'guide.' not in ...`, the match is the copy sentence "a link to this guide." in `guide.finding.how` (the raw-key check in test_guide.py line 14 flags it).
- Group run (test_guide, test_host_i18n, test_no_em_dashes, test_copy_cleanup): `1 failed, 29 passed`.
- Steps 8 to 10 (browser tests, guardrails) not run.

## Deviations
- Step 1: the branch was already checked out; no checkout run.
- Scratch copy files were written outside the repo (scratchpad), not in the worktree.

## Questions
1. `guide.finding.how` ("...a link to this guide.") trips the raw-key test. Options: reword the copy (for example "a link to this page"), or change the test. The brief says not to reword, so I stopped.
2. Czech `guide.finding.computer3` has a doubled word: "v menu menu skryje". Kept as written in the brief; please confirm the fix.

## Owner steps left
- Answer Question 1 and Question 2, then the executor (or you) reruns step 7 and steps 8 to 10.

## Screenshots
None taken (the browser test, step 9, was not reached).
