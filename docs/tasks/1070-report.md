# 1070 report: file registered guests at the deadline cap

Status: review
Branch: claude/1070-file-at-deadline-cap (brief names task/1070-file-at-deadline-cap) | Executor: Fable 5.2

## Files changed (against base 0d851ca4, besides the brief and the status.md compaction cherry-pick eae5f018)

- `App/app/reporting.py`: 21 insertions, 14 deletions (the brief's diff, applied with `git apply`, anchor found once at line 1093)
- `App/tests/test_deadline_cap_filing.py`: new, 352 lines, copied verbatim from the brief
- `docs/tasks/1070-report.md`: this file

## Commands

| Step | Command | Result |
|---|---|---|
| 3 | `git apply --check` then `git apply` | `1 file changed, 21 insertions(+), 14 deletions(-)` |
| 4 | `pytest tests/test_deadline_cap_filing.py` | `12 passed in 3.54s` |
| 5 | same file on the old `reporting.py` (from 0d851ca4) | `7 failed, 5 passed in 3.36s`: the two `due_at_the_cap`, the two `sweep_files`, `later_completion`, `registers_after`, `valid_co_guests`; tree clean after restore |
| 6a | filing row + `test_send_controls.py` (the brief's command) | `407 passed, 3 warnings in 17.64s`, 0 failed, 0 skipped |
| 6b | `pytest tests/test_endtoend.py` | `28 passed in 3.50s` |
| 7 | `python3 scripts/context_lint.py` | `context lint: OK` (warnings only: other open briefs; "2 commit(s) touched App/ after the last status.md update") |

No failure anywhere, so no clean-main comparison was needed. `test_legacy_completed_reservation_is_not_auto_eligible_on_deploy` passes unchanged.

## Acceptance (§7)

- [ ] Step 0 decision line: still the placeholder in the brief. Skipped on the orchestrator's instruction (the decision is recorded elsewhere); see Deviations.
- [x] Only §3 files plus the brief changed (plus the status.md cherry-pick); `reporting.py` is +21/-14.
- [x] 12 passed on the new code; 7 failed, 5 passed on the old code.
- [x] Step 6: 0 failed in both commands.
- [x] Context lint: OK.

## Deviations

- Step 0 placeholder not treated as a stop (§8), on the orchestrator's instruction for this run.
- Step 1: worked on the given branch `claude/1070-file-at-deadline-cap` (detached), not a new `task/` branch. Step 5 took the old code from the base commit 0d851ca4 instead of `origin/main`.
- Cherry-picked eae5f018 (status.md compaction) so the lint passes; it touches `docs/context/status.md`, outside §3.
- Commit messages are `1070 step k`. No PR opened (instructed).
- Backlog rule: the default (all stays past their cap are filed), unchanged from the diff.

## Questions

None.

## Owner steps left

Brief "Owner steps" 1 to 3: count the stays the first sweep will file (required before merge), review and merge with `scripts/merge-pr-on-green.sh`, deploy.
