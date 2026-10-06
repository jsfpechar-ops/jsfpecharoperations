# 0003: Put the token-saving workflow in the repo so every AI follows it

Status: review
Depends on: none (if task 0002 is merged first, rebase; on a conflict in decisions.md keep both lines) | Base commit: main | Branch: task/0003-ai-agnostic-workflow
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Any AI that opens this repo (Claude, ChatGPT, Gemini, Copilot, Cursor) must learn that chat AIs only write briefs and Cursor writes code, with a token budget. Today that rule lives only in one person's Cowork account, so other tools ignore it and spend Opus tokens implementing.

## 2. Context

CLAUDE.md already contains only `@AGENTS.md`. AGENTS.md has a "## Roles" section whose first bullet starts `- **Orchestrator** (Opus): plans, writes briefs`. docs/context/workflow.md has `## Roles and models` followed by `## Flow`. scripts/context_lint.py has a `CAPS = {` dict and a `def main()` that calls `check_staleness()`. If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| AGENTS.md | edit | Orchestrator and Executor bullets |
| docs/context/workflow.md | edit | Roles table row, new Token budget section |
| docs/context/prompts.md | edit | New Orchestrator prompt and inline-brief executor prompt |
| docs/context/decisions.md | edit | Append one line |
| docs/context/README.md | edit | Append one line |
| GEMINI.md | create | Pointer |
| .github/copilot-instructions.md | create | Pointer |
| .cursor/rules/agents.mdc | create | Pointer, always applied |
| scripts/context_lint.py | edit | Pointer check |

No other file may change.

## 4. Steps

1. AGENTS.md: replace the whole Orchestrator bullet with:
   `- **Orchestrator** (any chat AI the owner talks to: Claude, ChatGPT, Gemini, Copilot chat, Cowork, Claude Code): plans, writes briefs in docs/tasks/, reviews reports. Never edits App/, never runs the test suite, never implements, even when the owner says "fix this": in this repo that means "write the brief". Only the exact words "implement it yourself" lift this. Follow the [token budget](docs/context/workflow.md#token-budget-every-ai-every-session).`
   At the end of the Executor bullet add: ` If you are Cursor running a brief from docs/tasks/, you are the executor.`
2. docs/context/workflow.md: in the Roles table change the Orchestrator "Who" cell to `Any chat AI (a strong model only for HIGH RISK plans, a cheaper one otherwise)`. Then insert this section directly before `## Flow`:

   ## Token budget (every AI, every session)

   - The orchestrator's deliverable is one Cursor prompt with the brief inside, between `<<<BRIEF` and `BRIEF>>>`. The executor creates the brief file. No patch files, uploads or pushes from the orchestrator.
   - Budget per task: aim for 40k tokens, stop at 80k and hand over what you have as a brief with open questions.
   - Read AGENTS.md, then status, then one routing row. Grep before you read; read ranges of 150 lines or less. Never clone the whole repo to answer one question; fetch single files.
   - Bugs: confirm the root cause with at most 5 greps and 2 range reads. Fixes of 40 lines or fewer go into the brief as an exact diff; bigger ones as files, change and test to add.
   - No council, review swarm or multi-agent mode unless the owner names it in the current message and the change is HIGH RISK (filing, deletion, legal or tax). Then 3 advisors on a cheaper model, no peer-review round.
   - Subagents only search, on cheap models, and return conclusions.
   - Tests run only in the executor or CI, never in the orchestrator chat.
   - One chat per task. Reviews stay under 15k tokens.
   - Uploaded PDFs: convert to text and grep. Never print passwords, IDUBs, addresses or guest data; this repo is public.
   - Reply: at most 150 words plus the prompt.

3. docs/context/prompts.md: add a section `## Orchestrator (any AI)` above `## Executor` with this prompt in a code block:
   `UbyHost orchestrator. Read AGENTS.md and docs/context/workflow.md#token-budget-every-ai-every-session and follow them. Task: <describe it>. Give me one Cursor prompt.`
   Under `## Executor` add a second code block:
   `Read AGENTS.md. Create docs/tasks/NNNN-name.md with exactly the content between the BRIEF markers, commit it on a new branch task/NNNN-name, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/NNNN-report.md in the §9 format and opening one PR.`
4. docs/context/decisions.md: append
   `- 2026-10-06 | [workflow] Every chat AI is the orchestrator and follows the token budget; Cursor writes all code; pointer files for Gemini, Copilot and Cursor point to AGENTS.md | one session spent ~320k tokens on a council plus implementing in the orchestrator | [workflow](workflow.md#token-budget-every-ai-every-session)`
5. Create GEMINI.md and .github/copilot-instructions.md, each with exactly:
   `Read AGENTS.md first and follow it. Unless you are Cursor running a brief from docs/tasks/, you are the orchestrator: write briefs, never code.`
6. Create .cursor/rules/agents.mdc with exactly:
```
   ---
   description: UbyHost entry point
   alwaysApply: true
   ---
   Read AGENTS.md first and follow it. When you run a brief from docs/tasks/ you are the executor: follow the brief exactly.
```
7. scripts/context_lint.py: in `CAPS` add `"GEMINI.md": 50,`, `".github/copilot-instructions.md": 50,`, `".cursor/rules/agents.mdc": 150,`. Below the `CAPS` dict add:
```python
   # Every AI's entry file must exist and send the reader to AGENTS.md.
   POINTERS = ["CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md", ".cursor/rules/agents.mdc"]
```
   Above `def main()` add:
```python
   def check_pointers() -> None:
       for name in POINTERS:
           p = ROOT / name
           if not p.is_file() or "AGENTS.md" not in p.read_text(encoding="utf-8"):
               errors.append(f"{name}: missing or does not point to AGENTS.md")
```
   In `main()`, add `check_pointers()` after `check_staleness()`.
8. docs/context/README.md: append the line `Entry files for every AI (CLAUDE.md, GEMINI.md, .github/copilot-instructions.md, .cursor/rules/agents.mdc) point to AGENTS.md; context_lint.py checks them.`
9. Run §6, commit, push, open the PR titled "Workflow: every AI follows the token budget".

## 5. Do not touch

App/, deploy/, .github/workflows/, any other doc. No secrets.

## 6. Commands

From the repo root: `python3 scripts/context_lint.py` must print `context lint: OK`. Then temporarily rename GEMINI.md, rerun, confirm it prints the GEMINI.md error and FAIL, rename it back, rerun to OK.

## 7. Acceptance

- [ ] Lint OK; the pointer check fails when a pointer file is missing.
- [ ] `git diff --name-only main` lists only the files in §3 plus this brief and its report.
- [ ] The AGENTS.md link to the token budget anchor resolves (lint checks it).

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; a file outside §3 needs a change; a cap is exceeded; a step is unclear; you need merge, secrets or deploy.

## 9. Report

Write docs/tasks/0003-report.md (1,500 tokens at most) and set Status: review: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

AGENTS.md, docs/context/workflow.md, scripts/context_lint.py

## Owner steps

1. Merge with scripts/merge-pr-on-green.sh.
2. In any AI, start with the Orchestrator prompt from docs/context/prompts.md.
