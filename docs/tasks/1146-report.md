# 1146 report: test_endtoend.py gets its own database

Status: review

## 1. Files changed

- `App/tests/test_endtoend.py` (13 insertions, 2 deletions vs base 7a7e32de)
- `docs/tasks/1146-report.md` (this file)

No app code, conftest, or other test file changed. Ruff check on `tests` is clean.

## 2. Commands (last 5 lines each)

a. Predecessors then endtoend (fix applied)
```
............................................................             [100%]
60 passed in 6.13s
```

b. Claim and filing files plus form_chrome plus endtoend
```
...............................................................          [100%]
207 passed, 1 warning in 9.25s
```
(The one warning is a pre-existing DeprecationWarning for `utcnow()` in `app/mail.py`.)

c. endtoend alone
```
............................                                             [100%]
28 passed in 3.85s
```

d. form_chrome alone
```
......................                                                   [100%]
22 passed in 1.48s
```

e. Successor check, run with `-rs` (0 skipped)
```
........................................................................ [ 76%]
......................                                                   [100%]
94 passed in 5.28s
```

f. Revert-bite (base test file restored, command a)
```
.....................................F.FF.FFFF.FFF.FF.......             [100%]
=========================== short test summary info ============================
FAILED tests/test_endtoend.py::test_06_calendar_import_creates_the_stay_and_skips_the_block
...
12 failed, 48 passed in 4.71s
```
FAIL line: `FAILED tests/test_endtoend.py::test_06_calendar_import_creates_the_stay_and_skips_the_block`, summary `12 failed, 48 passed`.
PASS line (fix restored, command a): `60 passed in 4.81s`.

## 3. Acceptance (§7)

- [x] Command a: 0 failed
- [x] Commands b, c, d, e: 0 failed, 0 skipped
- [x] Revert-bite: failed without the fix, passed after restore
- [x] `git diff 7a7e32de --stat -- App` shows only `App/tests/test_endtoend.py`

## 4. Deviations

- Brief §6f says `git stash push -- tests/test_endtoend.py`. The fix was already committed (steps 1 and 2 each committed), so there was nothing to stash. I used `git checkout 7a7e32de -- App/tests/test_endtoend.py` to restore the base version, ran command a, then `git checkout HEAD -- App/tests/test_endtoend.py`. Same effect; working tree was clean afterwards.
- Command e was run with `-rs` added so the 0-skipped criterion is visible in the output.

## 5. Questions

None.

## 6. Owner steps left

1. Review the branch `task/1146-e2e-isolation` (commits 7000627b and 1011dad4 for the code, a50cac8b for this report).
2. Open the draft PR and merge with `scripts/merge-pr-on-green.sh` after review.
