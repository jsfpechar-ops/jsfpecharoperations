# Workflow

This file is the single source of truth for how work is done. When the process changes, edit this file and add a `[workflow]` line in [decisions](decisions.md).

## Roles and models

| Role | Who | Does | Never |
|---|---|---|---|
| Orchestrator | Opus (Cowork or Claude Code) | Plans in `docs/plans/`, briefs in `docs/tasks/`, reviews, context updates | Edits `App/`, runs audits nobody asked for, carries one chat across tasks |
| Executor | Cursor: composer, Kimi or GLM only | Applies one brief and writes its report | Designs, guesses, touches files outside the brief, merges |
| Search helper | Sonnet or Haiku subagent | Grep and summarise; returns conclusions, not file dumps | Writes files |
| Owner | Josef | Decides, merges, deploys, secrets, servers | |

## Flow

1. **Plan** (only for big or HIGH RISK work): the orchestrator writes `docs/plans/<name>.md`. Run at most one council, and only for HIGH RISK items (filing, deletion, legal).
2. **Brief:** the orchestrator writes `docs/tasks/NNNN-name.md` from [TEMPLATE](../tasks/TEMPLATE.md). Each brief must fit one executor session. Split big work into ordered briefs with `Depends on`.
3. **Execute:** the owner pastes the [executor prompt](prompts.md#executor) into a new Cursor chat. The executor sets `Status: in-progress`, works, writes `NNNN-report.md`, sets `Status: review` and opens one PR.
4. **Review** (a new orchestrator chat, under 15k tokens):
   1. Read the report.
   2. Run `gh pr checks <pr>`. CI is the truth.
   3. Run `gh pr diff <pr> --name-only` and compare with brief §3. Any extra file means a correction brief.
   4. Read the diff only for the files on the brief's risk list.
   5. Verdict: approve (the owner merges with `scripts/merge-pr-on-green.sh`), or write `NNNN-fix-1.md`.
   6. Update status, decisions and known-issues, then set `Status: done`.
5. **Deploy:** the owner deploys; the orchestrator updates the Production lines in [status](status.md).

Statuses: `todo → in-progress → review → done`, plus `blocked` (with the reason on the Status line).

## Writing briefs for a weak executor

- Paste the context into the brief. Quote exact code excerpts with the file path. Excerpts are anchors: if one isn't found verbatim, the executor stops.
- Give the full code or exact diffs, never "implement X". Name every file. Number every step.
- Acceptance must be checkable by a command or a visible fact. UI work: the browser and geometry tests plus screenshots at 360, 390 and 1280 px in the report.
- Cloud agents can't push to `main`, merge, set secrets, SSH or deploy, and their `gh` is often read-only. The brief says what to hand to the owner, with exact commands.
- Owner steps are numbered and click-by-click, in plain words.

## Update triggers

| When this changes | Update |
|---|---|
| A dependency | [architecture](architecture.md) and a decisions line with the reason |
| A personal-data field | `App/app/retention.py`, `docs/privacy/ROPA.md`, and a privacy-policy copy task |
| An outbound request or a processor | The PR reason, `docs/privacy/`, `App/app/subprocessors_i18n.py` |
| A route or module | [architecture](architecture.md) code map |
| A legal obligation | [status](status.md) Blocked section, and a K-L row |
| A deploy | [status](status.md) Production lines |
| A hard rule | The AGENTS.md one-liner and the [rules](rules.md) section |
| A workflow, tool or model | A `[workflow]` decision, then this file, then [prompts](prompts.md) |
| A bug found or fixed | A [known-issues](known-issues.md) row added or deleted |

## Compaction

- If the lint reports a file over its cap, summarise it in the same session.
- `decisions.md`: move lines older than 90 days that nothing references to `docs/archive/decisions-YYYY.md`.
- Briefs and reports that have been `done` for more than 60 days move to `docs/archive/tasks-YYYY/`.
- Never move live rules into the archive.

## Monthly check (first Monday; the owner runs it)

1. Run spend-doctor `--text-only` on the Mac and paste the output into a new orchestrator chat with the [monthly prompt](prompts.md#monthly).
2. The targets, against the 2026-10-06 baseline in [README](README.md):
   - under $800 per 30 days,
   - Opus under 60 % of spend,
   - peak session under 120k tokens,
   - zero unrequested audits.
3. The orchestrator prunes stale context and reads the reports' Deviations sections for repeated executor mistakes. A mistake seen twice becomes a template line.
