# Workflow

This file is the single source of truth for how work is done. When the process changes, edit this file and add a `[workflow]` line in [decisions](decisions.md).

## Roles and models

| Role | Who | Does | Never |
|---|---|---|---|
| Orchestrator | Any chat AI | Plans in `docs/plans/`, briefs in `docs/tasks/`, reviews reports, context updates | Edits `App/`, runs tests, implements, audits nobody asked for, carries one chat across tasks |
| Executor | **Haiku 5.5 only** ([rules](executor.md)) | Applies one brief and writes its report | Designs, guesses, touches files outside the brief, merges, spawns subagents |
| Search helper | Haiku subagent of a Claude orchestrator | Grep and summarise in 200 words; no file dumps | Writes files |
| Owner | Josef | Decides, merges, deploys, secrets, servers | |

- A **Claude** orchestrator implements only by spawning a Haiku 5.5 subagent (Agent tool, `model: haiku`) with one brief. It reads the report, not the transcript. Briefs run one after another; in parallel only when their §3 file lists do not overlap.
- Any **other** AI (ChatGPT, Gemini, Copilot) ends with the [executor prompt](prompts.md#executor) filled in; the owner pastes it into a Haiku 5.5 session.
- Only the owner's exact words "implement it yourself" let an orchestrator implement.
- HIGH RISK areas (filing, migrations, auth, legal copy, deletion) are still Haiku's work, but the brief is an exact diff only, and the review reads the full diff of those files.

## Owner-authorized host design execution

Closed 2026-10-17. The Luna 6.0 and Cursor-executor exception is retired; Haiku 5.5 is the only executor. Never push main, bypass CI, merge for preview or deploy production. See [decision](ui-decisions.md).

## Token budget (every AI, every session)

- **Every chat, orchestrator or Haiku:** checkpoint at 60k tokens, hard stop at 100k. Agents cannot count tokens exactly, so also count calls: an orchestrator stops after 25 tool calls and 5 file reads, Haiku after 30 tool calls. At the checkpoint, stop new work and hand over (see below). Orchestrators aim for 40k.
- **No audit and no full test suite** unless the owner asks in the current message. Run only the [test-map](test-map.md) row for the changed area. CI runs the rest.
- **Cap every command's output:** `| tail -30`, `grep -m 20`, `head -50`. Never print a full traceback, log or diff.
- The orchestrator's deliverable is a brief and, for non-Claude AIs, the executor prompt with the brief between `<<<BRIEF` and `BRIEF>>>`.
- Read AGENTS.md, then status, then one routing row. Grep before you read; ranges of 150 lines or less. Fetch single files, never the whole repo.
- Bugs: confirm the root cause with at most 5 greps and 2 range reads. Fixes of 40 lines or fewer go into the brief as an exact diff; bigger ones as files, change and test to add.
- No council or review swarm unless the owner names it in the current message and the change is HIGH RISK. Then 3 Haiku advisors, no peer-review round.
- Role files stay separate: orchestrators never open [executor](executor.md); Haiku never opens this file. Keep AGENTS.md free of dates and status so its start never changes.
- One chat per task. Reviews stay under 15k tokens. Uploaded PDFs: convert to text and grep. Never print passwords, IDUBs, addresses or guest data; this repo is public.
- Reply: at most 150 words plus the prompt. Screenshots: one per changed page at 390 px.

## When Haiku reaches the cap

1. Haiku commits after every step (`NNNN step k`), so a cutoff loses nothing.
2. At its checkpoint it writes the report with `Status: blocked`, `Done: steps 1 to k. Left: steps k+1 to n.`, and stops.
3. Cut off at 100k without a report: the orchestrator reads `git log --oneline -10` and `git diff --stat` on the branch and finds the last `step k` commit.
4. The orchestrator writes a continuation brief `NNNN-cont-1.md` (same branch, `Depends on` the first; only steps k+1 to n, anchors re-copied from the branch as it now stands) and starts a **fresh** Haiku. A Claude orchestrator spawns it; another AI hands the owner the prompt. A fresh Haiku inherits nothing, so the brief carries everything.
5. A task gets at most 3 Haiku sessions in all (first, then continuations or one rewrite after a repeated test failure). After the third the orchestrator stops and asks the owner; the brief is probably too big and should be split.

## Flow

0071–0086: [staging-first protocol](../plans/host-navigation-execution-protocol.md).

1. **Plan** (only for big or HIGH RISK work): the orchestrator writes `docs/plans/<name>.md`.
2. **Brief:** the orchestrator writes `docs/tasks/NNNN-name.md` from [TEMPLATE](../tasks/TEMPLATE.md). Each brief must fit one Haiku session of 30 tool calls. Split big work into ordered briefs with `Depends on`.
3. **Execute:** Haiku runs only a brief whose Status is `todo` (`replaced`, `done` or `blocked` means do not run). It sets `Status: in-progress`, works, writes `NNNN-report.md`, sets `Status: review` and opens one PR.
4. **Review** (a new orchestrator chat, under 15k tokens):
   1. Read the report.
   2. Run `gh pr checks <pr>`. CI is the truth.
   3. Run `gh pr diff <pr> --name-only` and compare with brief §3. Any extra file means a correction brief.
   4. Read the diff only for the files on the brief's risk list.
   5. Verdict: approve (the owner merges with `scripts/merge-pr-on-green.sh`), or write `NNNN-fix-1.md`.
   6. Update status, decisions and known-issues, then set `Status: done`.
5. **Deploy:** the owner deploys; the orchestrator updates the Production lines in [status](status.md).

Statuses: `todo → in-progress → review → done`, plus `blocked` (with the reason on the Status line) and `replaced` (a newer brief takes its place; name it on the Status line).

## Writing briefs for Haiku

- Paste the context into the brief. Quote exact code excerpts with the file path. Excerpts are anchors: if one isn't found verbatim, Haiku stops.
- Give the full code or exact diffs, never "implement X". Name every file. Number every step. One step changes one place in one file.
- Every step ends with its command, written out, and the expected result.
- Acceptance must be checkable by a command or a visible fact. Tests come from the [test-map](test-map.md), never the full suite. UI work: the browser and geometry tests plus the screenshots.
- Haiku can't push to `main`, merge, set secrets, SSH or deploy, and its `gh` is often read-only. The brief says what to hand to the owner, with exact commands.
- Owner steps are numbered and click-by-click, in plain words.
- One brief owns each piece of copy. When a new brief replaces an old one, mark the old one `Status: replaced by NNNN` in the same commit that adds the new brief.
- Anchors are the safety net, not the rule: a brief that runs after a brief it overlaps stops at its first anchor that is no longer there. `context lint` warns when two open briefs name the same file in section 3; the orchestrator says which goes first.

## Update triggers

| When this changes | Update |
|---|---|
| A dependency | [architecture](architecture.md) and a decisions line with the reason |
| A personal-data field | `App/app/retention.py`, `docs/privacy/ROPA.md`, and a privacy-policy copy task |
| An outbound request or a processor | The PR reason, `docs/privacy/`, `App/app/subprocessors_i18n.py` |
| A route or module | [architecture](architecture.md) code map, and the [test-map](test-map.md) row |
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
   - peak session under 100k tokens,
   - zero unrequested audits.
3. The orchestrator prunes stale context and reads the reports' Deviations sections for repeated executor mistakes. A mistake seen twice becomes a line in [executor](executor.md) or the template.
