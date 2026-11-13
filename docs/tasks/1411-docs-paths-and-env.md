# 1411: Repo-relative paths in briefs and the Go retention env var in ENVIRONMENT.md

Status: review
Depends on: none | Base commit: 3d75651dd | Branch: cursor/1411-docs-paths-and-env-4de2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Replace the absolute home-directory paths that old briefs and reports carry (45 files, 165 lines) with paths that do not depend on the reader's directory (`$(git rev-parse --show-toplevel)`, a `<ubyhost-obec checkout>` placeholder, or `/tmp/<name>`), and document `UBYHOST_GO_RETENTION_APPLY` in `docs/ENVIRONMENT.md` next to `UBYHOST_RETENTION_AUTOPURGE`. The repo convention is repo-relative paths, and the Go retention job reads a switch that no doc names.

## 2. Context

Rules: AGENTS.md hard rule 3 (public repo: no machine-specific paths), rule 9 (one explanation in one place).

Overlap with 1410: none. 1410 edits seven briefs and reports about 1301, 1302 and 1320; none of them carries a home-directory path, and 1410 touches neither `ENVIRONMENT.md` nor the 45 files below. So `Depends on: none`; the two briefs can run in any order.

The prefix to remove is the home-directory path of the old developer machine, `/home/` followed by `user`. This brief writes it as `/home/us[e]r` inside regexes so that this file never contains the string itself (otherwise the acceptance grep would match this brief).

The prefix appears in these forms (counts from `git grep -ho`): `<prefix>/jsfpecharoperations` (the repo root, about 160 lines including `/App`, `/go`, `/docs`, `/deploy`), `<prefix>/ubyhost-obec` (a git worktree, 15 lines, brief 1031 only), `<prefix>/wt`, `wt-a`, `wt-1144`, `wt-1147`, `wt-1173d` (worktrees), `<prefix>/scratchpad_1150_step1.py` and `_step2.py` (1154 report), `<prefix>/1381-prewritten` (owner-side bundle, brief 1381). The new text must not depend on the directory the reader is in. The repo root becomes `$(git rev-parse --show-toplevel)`. Checkouts and files outside the repo become a placeholder or a `/tmp/` path, never a guessed relative path.

Mapping applied by the single `sed` command in step 2 (rules run in this order: 1 and 2 before 3, `<prefix>` = the home-directory path):

| # | Old | New |
|---|---|---|
| 1 | `cd <prefix>/jsfpecharoperations && ` | (removed: the command runs from the repo root) |
| 2 | `cd <prefix>/jsfpecharoperations/<dir> && ` (`<dir>` = one name such as `go` or `App`) | `cd <dir> && ` |
| 3 | every other `<prefix>/jsfpecharoperations`, including `PY=<prefix>/jsfpecharoperations/App/.venv/bin/python` | `$(git rev-parse --show-toplevel)`, so that `PY=` becomes `PY=$(git rev-parse --show-toplevel)/App/.venv/bin/python` |
| 4a | `<prefix>/ubyhost-obec` | `<ubyhost-obec checkout>` (a placeholder: the worktree location is the reader's own) |
| 4b | `<prefix>/wt`, `<prefix>/wt-a`, `<prefix>/wt-1144`, `<prefix>/wt-1147`, `<prefix>/wt-1173d`, `<prefix>/1381-prewritten`, `<prefix>/scratchpad_...` | `/tmp/` plus the same name, e.g. `/tmp/wt-1147`, `/tmp/1381-prewritten`, `/tmp/scratchpad_1150_step1.py` |

Examples that step 3 checks by `grep -n` (old line -> new line, from the brief writer's dry run on a copy in `/tmp`):

- `docs/tasks/1250-go-guide-import.md:100` (rule 2): `cd <prefix>/jsfpecharoperations/go && gofmt -l internal/anthropic; ...` -> `cd go && gofmt -l internal/anthropic; ...`
- `docs/tasks/1031-stay-fee-same-town-and-end-to-end.md:175` (rules 4a and 3): `cd <prefix>/ubyhost-obec/App && PY=<prefix>/jsfpecharoperations/App/.venv/bin/python && ...` -> `cd <ubyhost-obec checkout>/App && PY=$(git rev-parse --show-toplevel)/App/.venv/bin/python && ...`
- `docs/tasks/1031-stay-fee-same-town-and-end-to-end.md:61` (rule 4a): `cd <prefix>/ubyhost-obec && git branch --show-current && ...` -> `cd <ubyhost-obec checkout> && git branch --show-current && ...`
- `docs/tasks/1173d-report.md:4` (rule 4b): `(worktree <prefix>/wt-1173d)` -> `(worktree /tmp/wt-1173d)`
- `docs/tasks/1270-go-public-legal-pages.md:50` (rule 3): ``Work from the repo root `<prefix>/jsfpecharoperations` unless a step says `App/`.`` -> ``Work from the repo root `$(git rev-parse --show-toplevel)` unless a step says `App/`.``
- `docs/tasks/1381-go-layout-shell-data.md:72` (rule 4b): ``cd <prefix>/1381-prewritten && sha256sum -c MANIFEST.sha256 ...`` -> ``cd /tmp/1381-prewritten && sha256sum -c MANIFEST.sha256 ...``
- `docs/tasks/1154-report.md:38` (rule 4b): `<prefix>/scratchpad_1150_step1.py` -> `/tmp/scratchpad_1150_step1.py`
- `docs/tasks/0287-ci-two-old-pins.md:4` (rule 4b): `worktree <prefix>/wt,` -> `worktree /tmp/wt,`

ENVIRONMENT.md anchor (must exist verbatim at line 60 of `docs/ENVIRONMENT.md`, exactly once):

```
| `UBYHOST_RETENTION_AUTOPURGE` | `0` | `1` lets the daily `retention` job delete what the schedule covers. Off is a dry run: it audits the exact row set and deletes nothing (BE-2, G-D4). |
```

The Go source (`go/internal/retention/retention.go` line 67) is `cfg := Config{DryRun: !(on("UBYHOST_RETENTION_AUTOPURGE") && on("UBYHOST_GO_RETENTION_APPLY"))}`: the Go job deletes only when both switches are on; `on` accepts `1`, `true`, `yes` (lowercase).

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/ENVIRONMENT.md` | edit | one new table row after line 60 |
| the 45 files printed by `git grep -l '/home/us[e]r' -- docs` | edit (sed) | prefix replaced per the §2 mapping; they are all under `docs/tasks/`: 0184-report, 0195-report, 0204-report, 0207-design-lint-for-onboarding-fixes, 0207-report, 0208-one-box-fee-account, 0235-round1-verification, 0239-stay-fee-four-boxes, 0241-report, 0247-round2-verification, 0287-ci-two-old-pins, 0288-business-rows-geometry, 0289-business-name-width, 0964-stay-dates-narrow-wrap, 0977-pr790-merge-main, 0990-settings-write-loop, 1021-remove-litestream, 1031-stay-fee-same-town-and-end-to-end, 1052-backup-rollout-cleanup, 1121-host-guest-details-mail, 1122-guest-receipt-what-you-sent, 1124-pr923-ci-fixes, 1134-report, 1140-window-fit-in-lock-and-claim-refresh, 1140b-claim-refresh-before-each-batch, 1142-claim-refresh-respects-ttl, 1144-claim-claimed-at-at-insert, 1144-report, 1147-claim-ttl-test-nits, 1147-report, 1154-report, 1159-fix-1-report, 1173d-report, 1200-go-register-split, 1200-walg-report, 1222-fix-1-report, 1231b-report, 1235-go-lifecycle-mail, 1250-go-guide-import, 1270-go-public-legal-pages, 1271-go-public-legal-pages-render, 1310-fix-1-review-findings, 1310-go-cleaning-schedule-share, 1364-report, 1381-go-layout-shell-data (each `.md`) |
| `docs/tasks/1411-report.md` | create | the report |

No other file may change. The review request mentioned ten files; the real count is 45 (165 lines), so step 1 prints the count and you compare.

## 4. Steps

1. Baseline. From the repo root: `git checkout cursor/1411-docs-paths-and-env-4de2 2>&1 | tail -3; git branch --show-current; git grep -l '/home/us[e]r' -- docs | wc -l; git grep -c '/home/us[e]r' -- docs | awk -F: '{s+=$2} END{print s}'; git grep -n '/home/us[e]r' -- . ':!docs' | wc -l`
   Expected: branch name; `45`; `165`; `0`. A different first or second number is fine if it is larger (briefs added since); a nonzero third number (a hit outside `docs/`): STOP (§8).
2. Rewrite the prefix in one command (GNU sed, from the repo root; copy it exactly; the order of the `-e` rules matters, 1 and 2 must run before 3):
   ```bash
   git grep -l '/home/us[e]r' -- docs | xargs sed -i -E -e 's#cd /home/us[e]r/jsfpecharoperations && ##g' -e 's#cd /home/us[e]r/jsfpecharoperations/([A-Za-z0-9_.-]+) && #cd \1 \&\& #g' -e 's#/home/us[e]r/jsfpecharoperations#$(git rev-parse --show-toplevel)#g' -e 's#/home/us[e]r/ubyhost-obec#<ubyhost-obec checkout>#g' -e 's#/home/us[e]r/(wt[A-Za-z0-9-]*|1381-prewritten|scratchpad_[A-Za-z0-9_.]*)#/tmp/\1#g'
   git grep -n '/home/us[e]r' -- docs | wc -l; git diff --stat | tail -3
   ```
   Expected: `0`, then a summary line of about 45 files changed, 165 insertions(+), 165 deletions(-). If the first number is not `0` (a prefix form the rules do not know): STOP and list the remaining lines in the report.
3. Spot-check the eight examples of §2 (fixed-string grep, from the repo root). One call:
   ```bash
   grep -nF 'cd go && gofmt -l internal/anthropic' docs/tasks/1250-go-guide-import.md | cut -c1-90
   grep -nF 'cd <ubyhost-obec checkout>/App && PY=$(git rev-parse --show-toplevel)/App/.venv/bin/python' docs/tasks/1031-stay-fee-same-town-and-end-to-end.md | head -2 | cut -c1-130
   grep -nF 'cd <ubyhost-obec checkout> && git branch --show-current' docs/tasks/1031-stay-fee-same-town-and-end-to-end.md | cut -c1-90
   grep -nF '(worktree /tmp/wt-1173d)' docs/tasks/1173d-report.md | cut -c1-90
   grep -nF 'repo root `$(git rev-parse --show-toplevel)` unless' docs/tasks/1270-go-public-legal-pages.md | cut -c1-90
   grep -nF 'cd /tmp/1381-prewritten && sha256sum' docs/tasks/1381-go-layout-shell-data.md | cut -c1-90
   grep -nF '/tmp/scratchpad_1150_step1.py' docs/tasks/1154-report.md | cut -c1-90
   grep -nF 'worktree /tmp/wt,' docs/tasks/0287-ci-two-old-pins.md | cut -c1-90
   ```
   Expected: each command prints at least one line (the 1031 `PY=` command prints two). A command that prints nothing: STOP.
4. Look for breakage that a plain replace can cause. One call: `git diff -U0 | grep -E '^\+' | grep -E '&& *&&|^\+ *&&|cd +&&' | head -10 | cut -c1-140`
   Expected: no output. Any output: STOP and put the lines in the report.
5. ENVIRONMENT.md. Insert one row directly after the anchor row of §2 (edit tool: old string = the anchor row, new string = the anchor row, a newline, then the new row):
   ```
   | `UBYHOST_GO_RETENTION_APPLY` | `0` | Go `retention` job only. It deletes only when this and `UBYHOST_RETENTION_AUTOPURGE` are both `1` (`true` and `yes` also count; lowercase only). Anything else is a dry run: it counts the exact row set and deletes nothing. |
   ```
   Check: `grep -n 'UBYHOST_GO_RETENTION_APPLY\|UBYHOST_RETENTION_AUTOPURGE' docs/ENVIRONMENT.md | cut -c1-90` prints two lines, numbers 60 and 61, `AUTOPURGE` first. Do not edit any other row.
6. Lint and final check, one call: `python3 scripts/context_lint.py 2>&1 | tail -30; git grep -n '/home/us[e]r' -- docs | wc -l; git status --short | wc -l`
   Expected: lint ends OK with no new `ERROR`; `0`; `46` (45 briefs/reports plus `ENVIRONMENT.md`; the report adds one more later).
7. Write `docs/tasks/1411-report.md` (§9) and set this brief's line 3 to `Status: review`, then commit and push: `git add -A docs && git commit -q -m "1411: repo-relative paths in briefs; document UBYHOST_GO_RETENTION_APPLY" && git push -u origin cursor/1411-docs-paths-and-env-4de2 2>&1 | tail -5`. Open a normal (not draft) PR against `main` titled `1411: repo-relative paths in briefs and Go retention env var`, body = `docs/tasks/1411-report.md`: `gh pr create --base main --head cursor/1411-docs-paths-and-env-4de2 --title "1411: repo-relative paths in briefs and Go retention env var" --body-file docs/tasks/1411-report.md 2>&1 | tail -5`. If `gh` is read-only or fails, STOP and hand that exact command to the owner. NEVER merge.

## 5. Do not touch

- Everything under `App/`, `go/`, `deploy/`, `scripts/`, `.github/`.
- Any line of the 45 files that does not hold the prefix (the sed only changes matching lines; a diff outside those lines means something went wrong: STOP).
- Any other row of `docs/ENVIRONMENT.md`.
- Hard rules: 3 (no secrets or machine data added), 4 (no dependency), 8 (never push to `main`, never merge).

## 6. Commands

- Step 1, 2, 3, 4 and 6 commands as written. Expected outputs are in each step.
- No tests run: docs only, no test-map row applies.

## 7. Acceptance

- [ ] `git grep -n '/home/us[e]r' -- docs | wc -l` prints `0`.
- [ ] `git grep -n 'UBYHOST_GO_RETENTION_APPLY' -- docs/ENVIRONMENT.md | wc -l` prints `1`, on the line right after `UBYHOST_RETENTION_AUTOPURGE`.
- [ ] `python3 scripts/context_lint.py 2>&1 | tail -30` ends OK.
- [ ] `git diff --stat origin/main...HEAD | tail -3` lists only `docs/tasks/*.md` files, `docs/ENVIRONMENT.md` and this brief with its report; the replaced line count equals the added line count for the 45 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- step 1 shows a prefix hit outside `docs/`, or step 2 leaves a hit behind;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1411-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Do not write the home-directory path itself in the report (the acceptance grep covers `docs/`).

## Risk list (for the reviewer)

- `docs/tasks/1031-stay-fee-same-town-and-end-to-end.md` and `docs/tasks/1250-go-guide-import.md`: most replaced lines. 1031 now uses `<ubyhost-obec checkout>` and `PY=$(git rev-parse --show-toplevel)/App/.venv/bin/python`; 1250 uses `cd go`, `cd App` from the repo root.
- `docs/tasks/1381-go-layout-shell-data.md`: owner-side bundle path is now `/tmp/1381-prewritten`.
- `docs/ENVIRONMENT.md` row 61: wording matches `go/internal/retention/retention.go`.

## Owner steps

1. Open the PR the executor created and wait for the green check.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
