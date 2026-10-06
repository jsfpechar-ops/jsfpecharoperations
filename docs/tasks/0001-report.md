# 0001 context rollout — report

Status: review

## 1. `git diff --stat main` (last 5 lines)

```
 docs/privacy/TOMS.md                               |   2 +-
 .../0001-context-rollout.md}                       |   0
 .../tasks-TEMPLATE.md => tasks/TEMPLATE.md}        |   0
 .../context-rollout 2 => scripts}/context_lint.py  |   0
 165 files changed, 97 insertions(+), 466 deletions(-)
```

## 2. Lint output

```
next free: task 0002 | migration 0005
context lint: OK
```

(After deleting `.cursor/mcp.json`, one `ERROR` on `docs/context/decisions.md` for a backticked `.cursor/mcp.json` path was fixed by rephrasing that decision line; lint then passed.)

## 3. Pytest summary

```
2789 passed, 2 skipped, 7 warnings in 475.48s (0:07:55)
```

(Same pass/skip count as `main`.)

## 4. Cleanup dry-run and apply

**Dry-run — PRs to close (40):** see `close PR #233` … `close PR #276` in the brief’s list (40 open PRs matched).

**Dry-run — branches:** 39 branches would be deleted; branches with open PRs kept (including `task/0001-context-rollout` once #281 was open).

**Apply result:** `gh pr close` failed for every listed PR with `GraphQL: Resource not accessible by integration (addComment)` — **0 PRs closed**. **39 remote branches deleted** (dead branches without open PRs). Open PRs and their branches remain (e.g. wp-stack series, #276, #274, automation PRs, plus **#281** for this rollout).

## 5. §7 Acceptance

- [x] `docs/archive/` contains the 34 moved paths. `docs/UbyHost_workplan/series` no longer exists.
- [x] `grep -rn "FOLLOWUPS.md" App deploy | grep -v archive` prints nothing.
- [x] Lint passes locally; CI `context` job added (awaiting green on PR #281).
- [x] Pytest passes (2789 passed, 2 skipped).
- [x] `.cursor/mcp.json` deleted. `.gitignore` has `.codex/` and `.obsidian/`.
- [ ] Cleanup fully done: **owner must close the 40 listed PRs** (agent token cannot). Many stale open PRs/branches remain until then.

## 6. Deviations

- Upload bundle lived under `docs/plans/context-rollout/context-rollout 2/` (not flat); flattened with `git mv` before `place_files_0001.py`. Script’s final `git rm` needed `-f` after flatten staging.
- Extra commit `c9b45a6` (`.keep`) between `d72c870` and the file upload; upload parent is not `d72c870` as the brief’s ideal `git log -2` shows.
- `docs/context/decisions.md`: one line rephrased so lint passes after `mcp.json` removal (step 8).

## 7. Questions

- Should the owner close wp-stack and other open PRs outside the brief’s close list, or only the 40 numbered PRs?

## 8. Owner steps left

1. Review PR **#281**: https://github.com/jsfpechar-ops/jsfpecharoperations/pull/281
2. Run the step-12 cleanup block locally with `APPLY=1` (or close the 40 PRs manually) — Cloud Agent `gh` cannot add close comments.
3. Confirm CI is green, then run Cowork review per `docs/context/prompts.md` (NNNN=0001).
4. Merge: `scripts/merge-pr-on-green.sh 281 --squash`
