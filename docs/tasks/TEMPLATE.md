# NNNN: <title>

Status: todo
Depends on: <NNNN or none> | Base commit: <sha> | Branch: task/NNNN-<short-name>
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Two sentences: what changes, and why it matters.

## 2. Context

The rules that apply, pasted in. Exact code excerpts, each with its file path. If an excerpt isn't found verbatim, STOP (§8).

**Context-rollout upload (orchestrator):** put files **flat** in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|

No other file may change.

## 4. Steps

Numbered, in order. Each step gives the full code or an exact diff, plus the command to run.

## 5. Do not touch

Paths, plus the hard rules from AGENTS.md that apply here.

## 6. Commands

The exact commands and their expected output. Tests: only the [test-map](../context/test-map.md) row for the changed area, each ending `2>&1 | tail -30`. Never the full suite.

## 7. Acceptance

- [ ] Each item can be checked by a command or a visible fact. UI work: one 390 px screenshot per changed page (360 and 1280 only if the layout changed).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/NNNN-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

The files whose diff the reviewer must read.

## Owner steps

Numbered, click-by-click, in plain words.
