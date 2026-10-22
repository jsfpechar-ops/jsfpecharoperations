# 0237 report

Status: review

## Commits (branch claude/project-thread-kbrf7w)

- 262ea7d 0237 step 1: removed the quiet "On guest link from" block (5 lines) from `App/app/templates/reservations.html`. `grep -c link_window` returns 0.
- b7f2789 0237 step 2: `App/tests/test_guest_link_window_0231.py` now asserts the stay list has no `data-link-window=`.
- c5b2720 0237 step 3: `App/app/static/workflow.css`. Removed the `.journey` summary chevron rules, added `.lock-choice-yes > summary::before` to the hidden marker rule, and made the wizard heading selector `.workflow-block > h2.workflow-title` (text-md, line-height 1.3).
- 3450a38 0237 step 4: `App/app/templates/_workflow.html` adds `class="workflow-title"` to `#workflow-title`.
- 38912bd 0237 step 5: `App/app/templates/base.html` bumps the workflow.css version to `20261022-0237`.

## Step 6 (browser run, 600000 ms timeout)

Last lines of output:

```
........................................................................ [ 80%]
..................                                                       [100%]
90 passed, 1 warning in 214.38s (0:03:34)
```

No skips. The only warning is the httpx/starlette TestClient deprecation.

## Step 7 (not done)

The step 7 command was denied by the auto-mode classifier ("Irreversible Local Destruction"). The command combined a copy of the lock shots to `/mnt/project-files/foolproof-round1/lock-question/` with `git checkout -- docs/tasks/0102-evidence/` and `git clean -fq docs/tasks/0102-evidence/`. Every Bash call after that was also denied, including a read-only `git status`. So I could not confirm whether the copy ran, did not look at a 390 px lock shot, and did not restore the evidence folder.

## Deviations

- Done: steps 1 to 6. Left: step 7 (copy lock shots, restore `docs/tasks/0102-evidence/`, look at one 390 px shot), the commit of this report, and the PR (the brief says no PR).
- The brief has no §2 and no §5 to §8, though steps refer to §6, §7 and §8. Step 6 commands were used as written.
- The steps were committed one commit per step. Nothing was pushed.

## Questions

- Owner: is the `git clean -fq docs/tasks/0102-evidence/` in step 7 safe to run? It removes untracked files in that folder. Run `git status --short docs/tasks/0102-evidence/` first and check that only the test-written shots show up.

## Owner steps left

1. Run in the repo root: `cp docs/tasks/0102-evidence/30-lock-instructions-*.png /mnt/project-files/foolproof-round1/lock-question/`, then `ls /mnt/project-files/foolproof-round1/lock-question/`.
2. Restore the folder: `git checkout -- docs/tasks/0102-evidence/`, then review `git status` before any `git clean`.
3. Look at one 390 px lock shot and write one line about it here.
4. Commit this report with `git add docs/tasks/0237-report.md && git commit -m "0237 report"`.

## Orchestrator note

Step 7 done by the orchestrator: 12 lock-step shots copied to /mnt/project-files/foolproof-round1/lock-question/, tracked evidence restored with git checkout. The 390 px EN shot shows the question and two bordered choice cards, no Skip button, no overlap.
