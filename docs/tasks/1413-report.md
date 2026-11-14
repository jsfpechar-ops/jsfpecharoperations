# 1413 report

Status: review

## Files changed

- `.github/workflows/ci.yml`: new job `changes` (lines 19-52). `needs: changes` and `if: needs.changes.outputs.code == 'true'` on test (55), test-postgres (167), test-postgres-full (265), go (318), smoke (354), browser-shard (409), shellcheck (569), docker (581), caddy (608). `browser` (556) now `needs: [changes, browser-shard]`, new shard-or-skip step, comment fixed.
- `.github/workflows/deploy-lightsail.yml`: line 100 one-liner. Accepts a `skipped` job only when check run `changes` concluded `success`.
- `scripts/merge-pr-on-green.sh`: not changed.

## Allowlist (all four kept, none removed)

- `docs/tasks`: browser tests write screenshots there. No runtime read found.
- `docs/plans`: only docstrings and comments.
- `docs/archive`: only docstrings and comments. `.dockerignore` excludes `docs/`.
- `docs/reports`: no references.

## Scenarios

- (a) only `docs/tasks/x.md`: code=false. Heavy jobs skipped. browser passes via `SHARDS=skipped`, `CODE=false`. context and secrets run. Deploy gate accepts skipped because changes=success.
- (b) `App/...` changed: code=true, everything runs, browser needs `SHARDS=success`.
- (c) mixed: loop sets code=true, same as (b).
- (d) workflow_dispatch: `if` not entered, code=true, everything runs.

## merge-pr-on-green.sh

`skipping` is not special-cased. Line 53 counts only `pending`. Line 54 counts only `fail|cancel`. Line 56 merges when total>0 and pending==0. Line 57 refuses only on failed. No edit.

## Checks

- PyYAML safe_load on both workflow files: ok.
- Added `uses:` lines: 1, the existing checkout pin `3d3c42e5...`.
- Gate one-liner on 5 synthetic check-run sets: all pass gives empty output; changes=failure lists the 5 heavy jobs; all success gives empty; no changes run lists the 5; browser failure lists `browser`.
- Allowlist dry-run: `docs/tasks/x.md` allow, `App/app/db.py` code, `docs/context/status.md` code.
- `python3 scripts/context_lint.py | tail -30`: `context lint: OK`. The WARN lines are pre-existing.

## Deviations

- Review fix: `git diff --no-renames --name-only` in the `changes` job, so a rename out of `App/` counts as code.

- Brief header names branch `task/1413-ci-skip-heavy-jobs`. Worked on `claude/optimistic-allen-ybxnjg` as instructed.
- Commits: `040f415b` (step 2), `2e6c802f` (step 3), `df99890c` (step 4), `5587d362` (step 5), then this report (step 9).

## Not verified

- No GitHub Actions run, no actionlint, no pytest (not requested).
- Gate accepts skipped whenever changes=success and does not read the `code` output. Under the `if`, a heavy job skips only when code is not true, so this holds, but the reviewer should know.

## Owner steps

1. Open the PR from `claude/optimistic-allen-ybxnjg` (the executor did not open it).
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
