# NNNN: <title>

Status: todo
Depends on: <NNNN or none> | Base commit: <sha> | Branch: task/NNNN-<short-name>
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

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

The exact commands and their expected output (tests from `App/`, `python3 scripts/context_lint.py`). Always include CI's lint, from `App/`: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` → `All checks passed!` (CI runs it before the tests; a red lint makes the whole `test` job red).

## 7. Acceptance

- [ ] Each item can be checked by a command or a visible fact. UI work: screenshots at 360, 390 and 1280 px.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/NNNN-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

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
