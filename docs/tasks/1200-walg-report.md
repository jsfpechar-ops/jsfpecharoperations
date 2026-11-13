# 1200 report

Status: review

## 1. Files changed (git diff --stat 29f86658..HEAD, 5 files, +53 -3)

- deploy/lightsail/walg/walg-ship.sh (+4): key check after the prefix check in `ship_once`
- deploy/lightsail/scripts/walg-backup.sh (+6): in-container key check before `backup-push`
- deploy/lightsail/scripts/setup-server.sh (+21): unattended-upgrades and sshd drop-in (write, `sshd -t`, reload; removed on failure)
- App/tests/test_pg_backup_scripts.py (+23/-2): key in `run_ship` env, 2 new tests, stub case for the key check
- docs/OPERATIONS.md (1 line): sentence appended to "Encryption and key custody"

## 2. Commands

- `sh -n deploy/lightsail/walg/walg-ship.sh`: no output (pass)
- `bash -n deploy/lightsail/scripts/walg-backup.sh`: no output (pass)
- `bash -n deploy/lightsail/scripts/setup-server.sh`: no output (pass)
- `shellcheck -S error ...`: skipped, not installed
- `App/.venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x -k walg -rs`: `21 passed, 55 deselected in 0.59s`, 0 skipped (pass). Run with the main checkout's venv, see Deviations.
- `python3 scripts/context_lint.py`: `context lint: OK` (pass). Pre-existing WARN lines only.

## 3. Section 7 acceptance

- [x] Key check in both scripts; no line prints the value
- [x] setup-server.sh shows all four patterns
- [x] Walg tests pass, including the two new refusal tests
- [x] Diff lists only the five §3 files
- [ ] PR as draft: not done, per session override (orchestrator integrates the commit)
- PR text consequence (spool, `walg-check.sh` alert) and "setup-server.sh only runs on a fresh server; the live server is not changed." go in the PR the orchestrator opens.

## 4. Deviations

- Pytest ran with `$(git rev-parse --show-toplevel)/App/.venv/bin/python` from the worktree `App/` dir, since the worktree has no `.venv` (session override).
- Added `-rs` to the pytest command to confirm 0 skipped.
- Done: steps 1 to 5. Left: none.

## 5. Questions

None.

## 6. Owner steps left

1. Orchestrator: open a draft PR from `exec-1200` (no push or PR from the executor).
2. Read the PR description (spool consequence).
3. Nothing on the live server changes. Optional key-presence check from the brief's Owner steps.
4. Mark ready and run `scripts/merge-pr-on-green.sh` only when ready to deploy.
