# 1589: Stay fee pages on Go: rollout plan (docs only)

Status: todo
Depends on: 1580, 1581, 1582, 1583, 1584, 1585, 1586, 1587, 1588 (the plan describes their routes; the file itself needs none of them to be applied) | Base commit: current tip of the working branch | Branch: task/1589-stay-fee-go-rollout-plan
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier C

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1589 step k` (`k` is the step number). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1589 step'`.

## 1. Objective

Add the one document the owner needs before switching the stay fee pages to Go: `docs/plans/stay-fee-go-rollout.md` (checks, switch order, mail job, what stays on Python). No code, no switch, no change to any env file.

## 2. Context

Rules (AGENTS.md): 3 no secrets or guest data in the file (none); 11 Go first (nothing in `App/app/` changes). The text is pre-written. Sidecar: `docs/tasks/1589-files/docs/plans/stay-fee-go-rollout.md.txt`. Never retype or edit it.

| sha256 | file | action | lines |
|---|---|---|---|
| `547a32c57a32ca264dbc4c84e70502eb15dcfdcd3905a614458a368ee15a8d2e` | `docs/plans/stay-fee-go-rollout.md` | create | 29 |

Why the switch order in the file is what it is: Caddy matches paths, not methods, and `*` also matches `/` (the same reason brief 1427 forbids `/invoices/*`). `/stay-fees/*` therefore catches the detail page, both seal routes and every other route at once, so the single-route steps only exist for the paths that have a fixed shape.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/stay-fee-go-rollout.md` | create | the rollout plan |
| `docs/tasks/1589-files/**` | keep | sidecar (committed with this brief; do not edit) |
| `docs/tasks/1589-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (section 8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls docs/plans/stay-fee-go-rollout.md 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1589-files -name '*.txt' | wc -l | tail -1` prints `1`.

1. Copy the sidecar and check it (one call, repo root):

   ```bash
   cp docs/tasks/1589-files/docs/plans/stay-fee-go-rollout.md.txt docs/plans/stay-fee-go-rollout.md && sha256sum -c - <<'EOT' 2>&1 | tail -3
   547a32c57a32ca264dbc4c84e70502eb15dcfdcd3905a614458a368ee15a8d2e  docs/plans/stay-fee-go-rollout.md
   EOT
   ```

   The line must end with `: OK`. Then commit "1589 step 1".

2. Lint (repo root): `python3 scripts/context_lint.py 2>&1 | tail -10`. Expected: no error line. A cap or link error that names `docs/plans/stay-fee-go-rollout.md`: STOP (do not edit the file). Nothing changed, so no commit.

3. Write the report (section 9), set `Status: review` in this file and commit "1589 step 3".

## 5. Do not touch

`App/`, `go/`, `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `UBYHOST_GO_JOB_KINDS`, the sidecar, `docs/context/*`.

## 6. Commands

Only those of the steps above.

## 7. Acceptance

- [ ] `sha256sum -c` printed `: OK`.
- [ ] `context_lint.py` printed no error.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1589 step')` lists only `docs/plans/stay-fee-go-rollout.md`, the report and this brief.
- [ ] No env, Caddy, compose, Go or Python file changed; nothing pushed to `main`.

## 8. Stop and ask

Stop, and write the report, if an anchor or hash is not as stated, the lint names the new file, you reach 25 tool calls or about 50k tokens (report as `blocked`), or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1589-report.md` (600 tokens at most): files changed, each command with the last 5 lines of output, section 7 ticked, deviations, questions.

## Owner steps

None for this brief. The plan file it adds is the owner's checklist for the later switch.
