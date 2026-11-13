# 1169 report: DR filing guard on a restored box

Status: review. Branch claude/dr-filing-guard, base cd8bf5f. Not pushed.

## 1. Files changed (git diff --stat cd8bf5f)

- deploy/lightsail/scripts/filing-guard.sh (new, 100755, 78 lines)
- deploy/lightsail/scripts/preflight.sh (+6)
- deploy/lightsail/scripts/pg-restore.sh (+9, --file branch only)
- deploy/lightsail/.gitignore (+1: .restored-box)
- App/tests/test_pg_backup_scripts.py (+131 / -3)
- docs/DISASTER_RECOVERY.md (section rewritten; steps 4 and 12)
- docs/plans/portable-disaster-recovery.md (gap 6, step 6 row)
- docs/ENVIRONMENT.md (+1 row)
- docs/tasks/1169-dr-filing-guard.md (Status only; the brief file itself was already on the branch)

## 2. Commands and last 5 lines

- `.venv` not present in App/. Fallback used:
  `python3 -m venv /tmp/v1169 && pip install -q pytest` then
  `/tmp/v1169/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x --noconftest -rs`
  ```
  ...................................ssss................                  [100%]
  =========================== short test summary info ============================
  SKIPPED [4] tests/test_pg_backup_scripts.py:370: could not import 'yaml': No module named 'yaml'
  51 passed, 4 skipped in 0.92s
  ```
  Matches the brief's expected pytest-only result (51 passed, 4 skipped; the skips need yaml).
- `bash -n` on filing-guard.sh, preflight.sh, pg-restore.sh: no output, rc 0.
- shellcheck: not installed in this environment; skipped (CI runs it).
- `python3 scripts/context_lint.py | tail -1`: `context lint: OK` (only pre-existing WARN lines above it).
- `git ls-files -s deploy/lightsail/scripts/filing-guard.sh`: starts with 100755.

## 3. Section 7 acceptance

- [x] filing-guard.sh mode 100755
- [x] pytest: 0 failed (51 passed, 4 yaml skips in pytest-only venv)
- [x] `grep -c restored-box pg-restore.sh` = 1
- [x] `grep -n 'rm .restored-box' docs/DISASTER_RECOVERY.md` = 1 match (line 38)
- [x] `grep -n 1169 docs/plans/portable-disaster-recovery.md` = 2 matches
- [x] context_lint OK
- [x] `git diff --stat cd8bf5f` lists only section 3 files

## 4. Deviations

None. Every step applied as written. Anchors matched exactly once. Step 5 and step 6a text was applied by a script that copied the brief text; the anchors were asserted to occur once each.

## 5. Questions

None.

## 6. Owner steps left

None needed to merge. The current Lightsail box has no `.restored-box`, so nothing changes there.
