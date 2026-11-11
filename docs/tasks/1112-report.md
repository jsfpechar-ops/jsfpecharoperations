# 1112 report

## 1. Files

`App/app/reporting.py`, `App/app/claim.py` — restored `expected_guest_count` and `_declared_count` from `origin/main`. Brief + this report.

## 2. Commands (last lines)

- `test_headcount_1095.py`: **48 passed**
- `test_sm_*.py`: **100 passed**
- Headcount + sm: **148 passed**
- Filing row: **673 passed, 13 failed** — all failures in `test_endtoend.py` (starts `test_06`; cascade). `test_06` alone on **origin/main**: **FAILED** (`TypeError` at line 203) — not introduced by this correction.
- `git diff origin/main --stat App/app/reporting.py App/app/claim.py`: **60+ / 22+** insertions only.

## 3. §7

- [x] Functions match main
- [x] TRANSITIONS blocks intact
- [x] 48/48 headcount
- [x] 100/100 sm pins
- [x] Filing row: endtoend env issue documented

## 4. Deviations

Brief written by Sonnet 5.5 subagent (`claude-sonnet-5-5-high`).

## 5. Questions

Open Q1 (why old bodies on combined branch): unresolved — likely stale merge base.

## 6. Owner

Push landed on `task/sm-round1-combined`; re-run CI on PR #920.
