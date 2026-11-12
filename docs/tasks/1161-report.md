# 1161 report: pg-restore.sh --file

Status: review

## 1. Files changed (`git diff --stat 5b3685b HEAD`)

```
 App/tests/test_pg_backup_scripts.py      | 55 +++++++++++++++++++++++++++
 deploy/lightsail/scripts/pg-restore.sh   | 65 +++++++++++++++++++++++++-------
 docs/DISASTER_RECOVERY.md                | 10 ++---
 docs/LIGHTSAIL.md                        |  2 +-
 docs/plans/portable-disaster-recovery.md |  4 +-
 5 files changed, 113 insertions(+), 23 deletions(-)
```

Plus this report (docs/tasks/1161-report.md). Commits: step 1 bc59c9a, step 2 9a5d201, step 3 183de53, step 4 3ccdff7, step 5 cf54109.

## 2. Commands (last lines of output)

- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x --noconftest -rs`
  ```
  ....................ssss................                                 [100%]
  =========================== short test summary info ============================
  SKIPPED [4] tests/test_pg_backup_scripts.py:242: could not import 'yaml': No module named 'yaml'
  36 passed, 4 skipped in 0.64s
  ```
- `bash -n deploy/lightsail/scripts/pg-restore.sh` : no output, exit 0.
- `shellcheck -S error ...` : not installed, not run.
- `python3 scripts/context_lint.py` : `context lint: OK` (WARN lines are pre-existing; the last one is the orchestrator's status.md note).
- `grep -c 'docker cp' deploy/lightsail/scripts/pg-restore.sh` : 1.

## 3. Acceptance (§7)

- [x] `bash -n` prints nothing.
- [x] Pytest passes; existing stamp tests unchanged (new tests only added).
- [x] `docker cp` count is 1 (stamp branch only).
- [x] `--file` found in DISASTER_RECOVERY.md, LIGHTSAIL.md and the plan file.
- [x] context_lint ends without errors.
- [x] `git diff --stat` lists only §3 files.

## 4. Deviations

- Pytest run with `--noconftest`: `App/tests/conftest.py` imports `requests`, which the brief's venv (pytest only) does not have. The test file itself needs only stdlib and pytest. §6 command as written fails at collection in this venv.
- 4 tests skipped at line 242 (`yaml` not installed). They are outside the new code. Not installed, because that would be a new dependency for this run.
- shellcheck not installed; not run.
- No push and no PR: the task said do not push. Owner or orchestrator opens the PR.
- Commit trailer: the commit messages use the Co-Authored-By line from the task instructions (Opus 5.5).

## 5. Questions

None.

## 6. Owner steps left

- Push the branch and open the PR (draft is fine).
- After merge, use the `--file` form in the step-8 timed drill (`docs/plans/portable-disaster-recovery.md`).
