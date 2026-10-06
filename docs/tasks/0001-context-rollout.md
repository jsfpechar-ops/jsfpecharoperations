# 0001: Context system rollout

Status: done
Depends on: none | Base commit: the owner's upload commit on `main` that adds `docs/plans/context-rollout/` (parent `d72c870`) | Branch: task/0001-context-rollout
Executor: Cursor (Cloud or Local) | composer, Kimi or GLM | Fits one session

## 1. Objective

Commit the new agent context system, move finished audits and applied patches to `docs/archive/`, and add a CI lint job so it can't silently decay. Then close the stale PRs and delete dead branches, so agents stop wading through 30 PRs and 69 branches.

## 2. Context

The owner uploaded the orchestrator's files to `docs/plans/context-rollout/` (flat names; `MANIFEST.txt` maps each one to its final path). Step 1 puts them in place with `place_files_0001.py`. After that, these files exist. Don't edit them unless a step says so:

- `AGENTS.md` (rewritten)
- `CLAUDE.md`
- `.cursorindexingignore`
- `.cursor/commands/task.md`
- `docs/context/*` (including `domains/_template.md`)
- `docs/tasks/TEMPLATE.md` and this file
- `docs/archive/README.md`
- `docs/plans/README.md` (rewritten)
- `scripts/context_lint.py`
- `scripts/archive_docs_0001.py` (a one-off, deleted in step 4)

Rules that apply:

- Never push to `main`.
- Stage files by name, never `git add -A`.
- Never commit `.env`, databases or secrets.
- Merging is the owner's job, via `scripts/merge-pr-on-green.sh`.

`scripts/archive_docs_0001.py` moves 34 paths with `git mv`. It also rewrites references to them in about 20 tracked files, which are all comments or doc links (for example `FOLLOWUPS.md` → `docs/archive/FOLLOWUPS.md`). The orchestrator tested it on a clone of `d72c870`: 34 moves, 20 files edited, 30 lines changed.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/context-rollout/*` | git mv | to the paths in `MANIFEST.txt` (step 1); the folder is then gone |
| 34 paths in `scripts/archive_docs_0001.py` `MOVE` | git mv | to `docs/archive/…` |
| About 20 files printed by the script | modify | reference rewrites only (the script does this) |
| `.github/workflows/ci.yml` | modify | add the `context` job (step 5) |
| `.gitignore` | modify | append 2 lines (step 6) |
| `.cursor/mcp.json` | delete | Cloudflare MCP servers (decision 2026-10-06) |
| `docs/tasks/0001-report.md` | create | your report |

## 4. Steps

1. **Branch and place the uploaded files:**
   ```
   git checkout main && git pull
   git log -2 --format='%h %s'
   git checkout -b task/0001-context-rollout
   python3 docs/plans/context-rollout/place_files_0001.py
   ```
   Expect `git log` to show the upload commit with `d72c870` directly below it. The script must end with `placed 20 files, bundle removed`. If it prints `STOP`, or `docs/plans/context-rollout/` doesn't exist: STOP.
2. **Check:** run `git status --short`. Expect only `R`, `M` or `D` lines, and every path must be one of the 20 targets in `MANIFEST.txt` or inside `docs/plans/context-rollout/`. Anything else: STOP.
3. **Dry run:** `python3 scripts/archive_docs_0001.py`. Expect the last line to be `34 moves, 20 files with rewritten references` (the edit count may differ by ±2). If it prints `STOP`: stop.
4. **Apply:**
   ```
   python3 scripts/archive_docs_0001.py --apply
   rm scripts/archive_docs_0001.py
   ```
5. **CI job:** in `.github/workflows/ci.yml`, find this exact line (near the end):
   ```
     secrets:
   ```
   Insert this block directly **above** it, with a blank line after the block:
   ```yaml
     context:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v7
           with: { fetch-depth: 50 }
         - name: context lint (caps, links, briefs)
           run: python3 scripts/context_lint.py

   ```
   Indentation: `context:` has 2 spaces, like `secrets:`.
6. **`.gitignore`:** append these two lines at the end:
   ```
   .codex/
   .obsidian/
   ```
7. **Remove the MCP file:** `git rm .cursor/mcp.json`
8. **Lint:** `python3 scripts/context_lint.py`. It must end with `context lint: OK`. A `WARN` line is fine. If you get `ERROR` lines: fix only broken paths or anchors inside `docs/context/` or `AGENTS.md` that the error names (adjust the path to the real file). If the fix isn't obvious: STOP.
9. **Tests**, from `App/`: `.venv/bin/python -m pytest tests -q`. Expect the same pass count as on `main`; only comments changed.
10. **Stage by name:**
    ```
    git add AGENTS.md CLAUDE.md .cursorindexingignore .cursor/commands/task.md docs/context docs/tasks docs/archive docs/plans/README.md scripts/context_lint.py .github/workflows/ci.yml .gitignore
    git add -u
    git status --short
    ```
    Every line of the status must be `A`, `M`, `R` or `D`, and there must be no `.env`, `.db` or `.codex`.
11. **Commit, push, open the PR:**
    ```
    git commit -m "Cut per-session agent context cost: L0/L1 context, archive audits, CI lint"
    git push -u origin task/0001-context-rollout
    gh pr create --title "0001: context system rollout" --body "See docs/tasks/0001-context-rollout.md and 0001-report.md"
    ```
    If push or `gh` is refused (common in Cloud Agents): STOP, and put the exact commands under Owner steps.
12. **PR and branch cleanup.** The owner approved this on 2026-10-06. Run the block below **twice**:
    - **Run A:** exactly as written (`APPLY=0`). It changes nothing and only prints a list. Copy the output into the report.
    - **Run B:** change `APPLY=0` to `APPLY=1` on the first line, then run it again. This closes the PRs and deletes the branches.
    ```bash
    REPO=jsfpechar-ops/jsfpecharoperations; APPLY=0
    for n in 233 235 236 $(seq 238 272) 274 276; do
      st=$(gh pr view "$n" -R "$REPO" --json state -q .state 2>/dev/null)
      [ "$st" = "OPEN" ] || continue
      echo "close PR #$n"
      [ "$APPLY" = 1 ] && gh pr close "$n" -R "$REPO" -c "Superseded by #277 (bundle) and #280."
    done
    keep=$(gh pr list -R "$REPO" --state open --json headRefName -q '.[].headRefName')
    for b in $(gh api "repos/$REPO/branches?per_page=100" --paginate -q '.[].name'); do
      [ "$b" = "main" ] && continue
      echo "$keep" | grep -qx "$b" && { echo "keep $b (open PR)"; continue; }
      echo "delete branch $b"
      [ "$APPLY" = 1 ] && gh api -X DELETE "repos/$REPO/git/refs/heads/$b" >/dev/null
    done
    ```
    If the dry run lists closing a PR **not** in the list above, or deleting `main`: STOP.
13. **Report:** write `docs/tasks/0001-report.md` (§9) and set `Status: review` at the top of this file. Commit both and push to the same branch.

## 5. Do not touch

- Everything under `App/`, except the comment rewrites the script makes.
- `docs/UbyHost_workplan/04_legal_positions.md`, `docs/UbyHost_workplan/03_when_triggered.md`, `docs/UbyHost_workplan/compliance/`, `docs/privacy/` content (the script may fix one path inside them; nothing else), and `deploy/` except the script's comment rewrite.
- The content of the orchestrator-written files, except for step 8 fixes.
- No new dependencies. No other CI change.

## 6. Commands

- `python3 scripts/context_lint.py` ends with `context lint: OK`.
- `.venv/bin/python -m pytest tests -q` (from `App/`) passes with the same count as `main`.
- `git diff --cached --name-only | grep -E '\.env$|\.db$|secret'` prints nothing.

## 7. Acceptance

- [ ] `docs/archive/` contains the 34 moved paths. `docs/UbyHost_workplan/series` no longer exists.
- [ ] `grep -rn "FOLLOWUPS.md" App deploy | grep -v archive` prints nothing.
- [ ] The lint passes locally, and the new CI job `context` is green on the PR.
- [ ] Pytest passes. All CI jobs are green.
- [ ] `.cursor/mcp.json` is deleted. `.gitignore` has `.codex/` and `.obsidian/`.
- [ ] The cleanup is done: `gh pr list -R jsfpechar-ops/jsfpecharoperations --state open` shows only this PR (plus any PR the owner opened after 2026-10-06), and only `main` plus open-PR branches remain.

## 8. Stop and ask

Stop, write the report, and don't improvise if:

- the upload commit's parent isn't `d72c870`, or `place_files_0001.py` prints `STOP`;
- the script prints `STOP`;
- the lint shows an error you can't fix by correcting a path;
- a test fails twice;
- a file outside §3 changes;
- push or `gh` is refused;
- the cleanup would touch a PR outside the list.

## 9. Report

Write `docs/tasks/0001-report.md` with:

1. `git diff --stat main` (last 5 lines).
2. The lint output.
3. The pytest summary line.
4. The cleanup dry-run output and the apply result (counts).
5. §7 ticked.
6. Deviations.
7. Questions.
8. Owner steps left.

## Risk list (for the reviewer)

- `.github/workflows/ci.yml`
- `App/app/mail_notify.py`, `App/app/retention.py` and `App/app/templates/reservation_detail.html` (only comment lines may differ)

## Owner steps

1. Upload `docs/plans/context-rollout/` on GitHub (done before this brief runs).
2. Start a Cursor agent with the prompt the orchestrator gave you.
3. When the agent finishes, open a **new** Cowork chat and paste the Review prompt from `docs/context/prompts.md`, with NNNN replaced by 0001.
4. After an approval, run this in Terminal: `scripts/merge-pr-on-green.sh <PR number> --squash`
