# 2044 report: deploy retry safety

Status: blocked (executor tool-call checkpoint reached after step 7; verification incomplete)

## Files changed
- deploy/lightsail/scripts/deploy.sh: marker `.deploy-in-progress`, guarded Caddyfile and `:previous` tag copies, `fail_after_switch` helper, six call sites, marker cleared after `.deployed-sha`
- deploy/lightsail/.gitignore: `.deploy-in-progress` added after `.deployed-sha`
- App/tests/test_pg_go_slot_script.py: two static tests appended

## Commits (branch worktree-agent-a318a6358661214bd)
- 40bce67 2044 step 1 (contains steps 1 and 2)
- f87cfdc 2044 step 3-4
- 28b7b89 2044 step 5
- e7790f7 2044 step 6
- 644793f 2044 step 7

## Commands (§6)
- `bash -n deploy/lightsail/scripts/deploy.sh`: no output (pass)
- `shellcheck -S error deploy/lightsail/scripts/*.sh`: shellcheck not installed, not run
- `App/.venv/bin/python -m pytest tests/test_pg_go_slot_script.py tests/test_pg_backup_scripts.py -q --tb=short -x -rs`: 79 passed, 1 failed, then stopped (-x). Failing test: `test_backup_waits_for_a_transient_gap_then_succeeds` (backup script test, file not changed). Remaining tests in that set were not run.
- `python3 scripts/context_lint.py`: OK (warnings only)

## Acceptance (§7)
- [x] marker written before Caddyfile copy, removed after `.deployed-sha`
- [x] copies and both `:previous` tags guarded, NOTE printed to stderr
- [x] `grep -cF fail_after_switch` = 7
- [x] `.deploy-in-progress` in `.gitignore`
- [ ] §6 commands pass (pytest failure above; shellcheck missing)

## Deviations
- Brief path is in the main checkout; the worktree lacks docs/tasks/2044-*; I read it from the main checkout.
- Steps 1 and 2 share one commit; steps 3 and 4 share one commit.
- Commit 40bce67 has no Co-Authored-By / Claude-Session trailers (error). Needs a reword before merge.
- No PR opened; nothing pushed.
- Line 541 (`ERROR: no running app container`, `exit 1`) sits after the removal line, does not call rollback, and is not one of the six named sites. Left unchanged.

## Questions
- Is the backup transient-gap test failure pre-existing? Not checked (budget).
- Should line 541 also call `fail_after_switch`?

## Owner steps left
- Run the full §6 set, including the backup test, once shellcheck is installed.
- Reword 40bce67 trailers.
- Merge via `scripts/merge-pr-on-green.sh` after review.
- Stuck marker on a server: `rm deploy/lightsail/.deploy-in-progress`.
