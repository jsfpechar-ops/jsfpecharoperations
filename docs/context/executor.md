# Executor: Haiku 5.5

Read this with AGENTS.md and your brief. Open nothing else. You have no subagents.

## Your limits

- 30 tool calls and 60k tokens to your checkpoint. Hard stop at 100k tokens.
- At 25 tool calls or about 50k tokens: finish only the step you are on, commit it, and write the report with `Status: blocked`. Under "Deviations" write `Done: steps 1 to k. Left: steps k+1 to n.` Then stop. A fresh session continues; this is normal, not a failure.

## For every step, in this order

1. Open only the file the step names. Read only the lines around the anchor.
2. Find the anchor with `grep -nF "<exact text>" <file>`. Not found: STOP (brief §8).
3. Apply exactly the diff or code the step gives. Change nothing else, not even typos or spacing elsewhere.
4. Run the step's command. Always end it with `2>&1 | tail -30`.
5. Commit with the message `NNNN step k`. A cutoff must never lose work.

## Tests

- Run only the commands in brief §6. Never the full suite, never `pytest tests`.
- A test fails: read the last 30 lines, fix it once, rerun. It fails again: STOP and report.
- Browser tests: 0 skipped (`-rs`). Skipped means broken, not passed.

## Never

- Explore, audit, refactor, rename, "improve" or fix something the brief does not name.
- Open a file the brief does not name. Add a dependency. Spawn a subagent.
- Push, merge, touch `main`, secrets, servers or deploy. Hand that to the owner with the exact command.
- Print guest data, passwords, IDUBs or addresses. The repo is public.
- Guess. If a step is unclear or two readings are possible, STOP and ask; a question costs less than a wrong guess.

## Screenshots (UI briefs only)

One per changed page, at 390 px wide. Add 360 and 1280 only if the layout changed. Look at each once; do not retake.

## Report

`docs/tasks/NNNN-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, §7 ticked, Deviations, Questions, owner steps left. Then set `Status: review` (or `blocked`) and open one PR.
