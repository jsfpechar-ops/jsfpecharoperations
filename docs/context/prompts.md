# Prompts (paste as-is; replace NNNN)

## Orchestrator start

```
UbyHost repo. You are the orchestrator. Read AGENTS.md and docs/context/status.md only, then the routed files for this task. No audits. Ask me if unclear. Task: <one sentence>
```

## Orchestrator (any AI)

```
UbyHost orchestrator. Read AGENTS.md and docs/context/workflow.md#token-budget-every-ai-every-session and follow them. Task: <describe it>. Give me one Cursor prompt.
```

## Executor

```
Read AGENTS.md, then docs/tasks/NNNN-*.md. Follow it exactly, in order. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/NNNN-report.md in the §9 format.
```

```
Read AGENTS.md. Create docs/tasks/NNNN-name.md with exactly the content between the BRIEF markers, commit it on a new branch task/NNNN-name, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/NNNN-report.md in the §9 format and opening one PR.
```

## Review

```
UbyHost orchestrator. Review task NNNN: read AGENTS.md, docs/tasks/NNNN-*.md and NNNN-report.md, then follow docs/context/workflow.md#flow step 4. Don't read other files unless they're on the risk list.
```

## End of session

```
Close out: update docs/context/status.md (5 lines at most), append decisions and known-issues, run python3 scripts/context_lint.py, and list anything I must do.
```

## Monthly

```
UbyHost monthly check. Read docs/context/README.md and docs/context/workflow.md#monthly-check-first-monday-the-owner-runs-it. Here is the spend-doctor output: <paste>. Compare with the baseline, propose at most 3 changes, and prune stale context.
```

## Bug-hunt automation

```
Before reporting, grep docs/context/known-issues.md for the file. Skip listed IDs. Report only new, concrete, reproducible bugs, and append them as K- rows in the same PR.
```
