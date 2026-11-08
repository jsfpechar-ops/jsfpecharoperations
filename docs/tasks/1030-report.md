# 1030 report

Status: review

## Files changed
- deploy/lightsail/walg/Dockerfile: added `RUN groupadd -g 70 walg && useradd -u 70 -g 70 -M -d /tmp -s /usr/sbin/nologin walg` as the last line.
- App/tests/test_pg_backup_scripts.py: added `test_walg_dockerfile_has_a_passwd_entry_for_uid_70` after the Dockerfile test.
- docs/tasks/1030-walg-uid70-passwd-entry.md: status set to review.
- docs/tasks/1030-report.md: this report.

## Commands (last 5 lines)
- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x -rs`: `34 passed in 1.58s`, 0 skipped.
- `python3 scripts/context_lint.py`: ends with `context lint: OK` (warnings about other open briefs and status.md age are pre-existing).

## Section 7 acceptance
- [x] `useradd -u 70` present once in the Dockerfile.
- [x] test_pg_backup_scripts.py passes, 0 skipped.
- [x] context lint OK.
- [ ] `git status` empty after push (checked after commit and push).

## Deviations
None. Docker not available, so the image was not built (owner step).

## Questions
None.

## Owner steps left
After merge, on the server: `cd /opt/ubyhost && git fetch origin main && git reset --hard origin/main && cd deploy/lightsail && docker compose build walg 2>&1 | tail -5`, then `docker compose run --rm --no-deps walg wal-g backup-list 2>&1 | tail -5`. Expect no `unknown userid` error.
