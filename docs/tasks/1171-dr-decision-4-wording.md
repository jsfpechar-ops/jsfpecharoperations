# 1171: Correct DR plan decision 4 wording

Status: review
Depends on: none | Base commit: 748098d | Branch: task/1171-dr-decision-4
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Decision 4 of the DR plan says that removing `submit` from `UBYHOST_GO_JOB_KINDS` stops filing on the old server. It does not: Python then files guests itself. Correct the wording so it matches "Two servers never file at once" in docs/DISASTER_RECOVERY.md. Owner approved the wording on 2026-11-13.

## 2. Context

docs/plans/portable-disaster-recovery.md, line 57, verbatim:

`4. The old server is always stopped (or `submit` removed from `UBYHOST_GO_JOB_KINDS`) before a new one files.`

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/plans/portable-disaster-recovery.md | edit | line 57 only |
| docs/tasks/1171-dr-decision-4-wording.md | edit | Status line only |
| docs/tasks/1171-report.md | create | report |

No other file may change.

## 4. Steps

1. Replace line 57 with exactly:
`4. The old server is always stopped before a new one files, or set `UBYHOST_ENABLE_SCHEDULER=0` on it and remove `submit` from both `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS`. Removing it from `UBYHOST_GO_JOB_KINDS` alone does not stop filing: Python then files guests itself.`
2. Run the commands in §6.

## 5. Do not touch

Every other file. Do not commit, push or open a PR (the orchestrator does).

## 6. Commands

`git diff --stat | tail -30` expects one file changed (plus the report).
`python3 scripts/context_lint.py | tail -30` expects no errors.

## 7. Acceptance

- [ ] Line 57 matches step 1 exactly.
- [ ] No other line of the plan changed.
- [ ] context_lint has no errors.

## 8. Stop and ask

Stop and write the report as `blocked` if line 57 is not found verbatim, lint fails twice, or a file outside §3 needs a change.

## 9. Report

Write `docs/tasks/1171-report.md` (600 tokens at most), set `Status: review`: files changed, command output (last 5 lines), §7 ticked, deviations.

## Risk list (for the reviewer)

docs/plans/portable-disaster-recovery.md

## Owner steps

Merge with `scripts/merge-pr-on-green.sh`.
