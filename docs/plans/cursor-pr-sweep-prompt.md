# Cursor prompt: review, finish and merge the open PRs

A prompt, not a brief. Paste the block below into one new Cursor chat (Cursor needs a working `gh`). The owner authorizes merging in this chat only, for the PRs the prompt lists, using `scripts/merge-pr-on-green.sh`. No production deploy.

```
Read AGENTS.md, then docs/context/status.md. Open nothing else except what this prompt or a brief names.

GOAL: for every open PR that implements a brief in docs/tasks/ (0043, 0044, 0045, 0046, 0047, 0048, 0051, 0054, 0055, 0061, 0062) or is named under "Next" in docs/context/status.md, check that the PR did what its brief says, fix or finish it, and when ALL of them are ready, merge them in the order below. Then monitor until main is green.

OWNER AUTHORIZATION (this chat only): you may merge these PRs, and only with scripts/merge-pr-on-green.sh <pr> (default --merge). Never push to main. Never deploy. No new dependency, no secrets. Feature branches only; if you must update a PR branch, rebase it on origin/main and push with --force-with-lease to that PR's own branch, nothing else.

STEP 1: inventory
- gh pr list --state all --limit 60 --json number,title,headRefName,state,mergeable,reviewDecision
- Map each brief to its PR by branch name (task/NNNN-*, cursor/*NNNN* or the brief's "Branch:" line). Write one table: brief, PR, state, CI, mergeable, review.
- A brief with no PR: its branch may exist (git branch -r | grep NNNN). If it has commits, open the PR. If not, implement the brief (Step 3).
- Any open PR not covered by a brief or status.md (for example #278, #279): do not touch it. List it in the final report for the owner.

STEP 2: review each PR against its brief (one at a time, small context)
1. gh pr checks <pr>: CI is the truth. Red means find the cause and fix it (Step 3).
2. gh pr diff <pr> --name-only versus brief §3 "Files". An extra file means revert it. A needed extra file means stop on that PR and report.
3. Walk brief §4 step by step and §7 acceptance item by item. Tick each by a command or a visible fact. Anything not done or only half done is a gap.
4. Check the hard rules in AGENTS.md that apply: UbyPort filing untouched; a new personal-data field has its line in App/app/retention.py; a new outbound request (0055 ARES) states its reason in the PR and sends only the IČO; no new dependency; SQL only through App/app/db.py; a schema change is a new App/app/migrations/ file (0051 only); light mode only; auth forms work without JavaScript; copy follows rule 9; new i18n keys sit next to keys with the same prefix.
5. Template, CSS or guest-page changes: the browser and geometry tests pass with 0 skipped, and the PR has screenshots at 360, 390 and 1280 px. Missing screenshots are a gap.
6. From App/: .venv/bin/python -m pytest tests -q. From the repo root: python3 scripts/context_lint.py. Never set PYTHONPATH=App.

STEP 3: fix and implement
- Fix every gap on the PR's own branch, in a git worktree (git fetch origin && git worktree add ../uby-NNNN <branch>), touching only the files in brief §3. One commit per gap, clear message, push, wait for CI.
- If a brief's stop condition (§8) fires, or a fix needs a file outside §3, a new dependency, a decision about filing or law: stop that PR, leave it unmerged, and put the question in the final report.
- Brief 0048 needs the owner's logo files in App/app/static/platforms/. If they are missing, do not merge 0048; report it.
- Each brief that depended on another (0044 and 0045 on 0043; 0062 and 0054 after 0045) is rebased on origin/main after its parent merges; re-run the tests after every rebase.

STEP 4: ready gate
Do not merge anything until every in-scope PR is: CI green on its current head, mergeable, tests and lint passing locally, §7 fully ticked, and a report docs/tasks/NNNN-report.md present with Status: review. Print the readiness table. If a PR is not ready and cannot be fixed, ask me in this chat whether to merge the rest without it; do not decide alone.

STEP 5: merge order (dependencies first, then the plan's lane order)
0043, 0045, 0044, 0046, 0055, 0061, 0048, 0051, 0047, 0062, 0054. Then, per status.md: #339 (PostHog) if still open and approved, and close #337 unmerged only after #339 is merged; #341 if still open and reviewed OK.
For each PR: git fetch origin; if it is behind main, rebase it and re-run the tests; run scripts/merge-pr-on-green.sh <pr>. It pins the head SHA and refuses on red or pending checks; if it refuses, fix the cause, never bypass it. After each merge, check the next PR is still mergeable and CI is green on its new base before running the script on it.

STEP 6: monitor
After the last merge, watch main: gh run list --branch main --limit 5, and gh run watch on the newest run, until it is green. If main goes red, stop merging, find the PR that caused it, and report with the failing output; do not revert on your own.

STEP 7: close out
- Open one docs-only PR that updates docs/context/status.md (5 lines at most: what merged, what is left), appends to docs/context/decisions.md and docs/context/known-issues.md if anything was decided or found, set each merged brief to Status: done, run python3 scripts/context_lint.py, and merge it with the script.
- Final report in this chat, under 400 words: table of PR, verdict, fixes made, merge result; PRs left open and why; questions for me; owner steps left (deploy to staging, then production, are mine).
```
