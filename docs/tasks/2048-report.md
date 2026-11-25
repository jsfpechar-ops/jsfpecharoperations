# 2048 report: pg restore test flakes, lone-dash grep fix

Status: review

## Bug

The previous rewrite of the bare `grep -q` calls produced `grep - <pattern> >/dev/null`. The lone `-` makes grep take `-` as the PATTERN and the real pattern as a FILE name, so the check always failed. Example: `ps -q ... | grep - . >/dev/null` never matched.

Fix: remove the lone ` -` after `grep` (`sed -i -E 's/grep - /grep /g'` on the 12 changed scripts). Flags kept (`-x`, `-E`) and patterns unchanged.

## Before list (discovery `grep -nE 'grep - '`, lone dash)

| File | Lines | Count |
|---|---|---|
| deploy/lightsail/scripts/backup-gdrive.sh | 30 | 1 |
| deploy/lightsail/scripts/backup-s3.sh | 30 | 1 |
| deploy/lightsail/scripts/deploy.sh | 77, 79, 89, 288, 294 | 5 |
| deploy/lightsail/scripts/finish-bootstrap.sh | 28, 71 | 2 |
| deploy/lightsail/scripts/lib-docker.sh | 62, 68 | 2 |
| deploy/lightsail/scripts/monitoring-watchdog.sh | 50, 51, 62, 63 | 4 |
| deploy/lightsail/scripts/rollback-schema-prep.sh | 14 | 1 |
| deploy/lightsail/scripts/smoke-remote.sh | 91, 93 | 2 |
| scripts/rollback-prod.sh | none | 0 |

Total before: 18. After: 0 (both discovery commands print nothing).

## Guard tests

- `App/tests/test_pg_go_slot_script.py`: new `test_pipefail_scripts_grep_has_no_lone_dash_argument` (regex `\bgrep\s+-(\s|$)`), sharing a file-list helper with the existing `grep -q` test. The file now has 23 passing tests.

## Test results

- `bash -n` on every changed script: no failures.
- Pipefail behaviour check: ok1, ok2, ok3.
- `tests/test_pg_go_slot_script.py`: 23 passed.
- Flake loop, `tests/test_pg_backup_scripts.py` x20: `20 87 passed`.
- `tests/test_pg_app_role_script.py`: 9 passed.
- `tests/test_pg_cutover_script.py`: 7 passed.
- `tests/test_pg_schema_dump_script.py`: 7 passed.
- `python3 scripts/context_lint.py`: OK (warnings only, pre-existing).
