# 0003 report

Status: review

## Files changed

- `AGENTS.md` — orchestrator/executor role bullets and token-budget link
- `docs/context/workflow.md` — orchestrator “Who” cell; Token budget section
- `docs/context/prompts.md` — Orchestrator (any AI) prompt; inline-brief executor prompt
- `docs/context/decisions.md` — one workflow decision line
- `docs/context/README.md` — entry-file pointer note
- `GEMINI.md` — new pointer
- `.github/copilot-instructions.md` — new pointer
- `.cursor/rules/agents.mdc` — new always-on Cursor rule
- `scripts/context_lint.py` — caps, `POINTERS`, `check_pointers()`
- `docs/tasks/0003-ai-agnostic-workflow.md` — brief (Status: review)
- `docs/tasks/0003-report.md` — this report

## Commands

`python3 scripts/context_lint.py` (OK):
```
next free: task 0004 | migration 0005
context lint: OK
```

`mv GEMINI.md GEMINI.md.bak && python3 scripts/context_lint.py` (FAIL):
```
ERROR GEMINI.md: missing or does not point to AGENTS.md
next free: task 0004 | migration 0005
context lint: FAIL
```

`mv GEMINI.md.bak GEMINI.md && python3 scripts/context_lint.py` (OK):
```
next free: task 0004 | migration 0005
context lint: OK
```

`git diff --name-only main` — only §3 files plus this brief and report (after commit).

## §7 Acceptance

- [x] Lint OK; pointer check fails when GEMINI.md is missing.
- [x] `git diff --name-only main` lists only §3 files plus brief and report.
- [x] AGENTS.md token-budget anchor resolves (context lint link check passed).

## Deviations

- Brief file created with `Status: in-progress` during work; set to `review` in this report. `.cursor/rules/agents.mdc` body matches step 6 without the brief’s indented code-fence padding.

## Questions

None.

## Owner steps left

1. Merge with `scripts/merge-pr-on-green.sh`.
2. In any AI, start with the Orchestrator prompt from `docs/context/prompts.md`.
