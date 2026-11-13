# 1413: CI skips the heavy jobs when a change only touches briefs and plans

Status: todo
Depends on: none (runs first of 1413, 1414, 1415: all three edit `.github/workflows/ci.yml`) | Base commit: 531e8359 | Branch: task/1413-ci-skip-heavy-jobs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a first CI job `changes` that outputs `code=true|false` from a plain `git diff --name-only`, and make the heavy jobs wait for it and skip when `code=false`. About half of recent PRs touch only briefs or docs and still burn 22 to 33 minutes of CI, then run all of it again on `main` after the merge.

## 2. Context

Owner decision (2026-11-13): no GitHub branch protection and no required checks. The protection is `scripts/merge-pr-on-green.sh` plus the deploy gate in `.github/workflows/deploy-lightsail.yml`. CI must get faster and stay reliable. Hard rule 4: no new third-party GitHub Action (use `git diff` in a `run` step, `actions/checkout` is already used).

Facts (verify by grep, do not trust):
- `ci.yml` jobs (13): `test`, `test-postgres`, `test-postgres-full`, `go`, `smoke`, `browser-shard` (matrix 4), `browser` (aggregate, ~line 510), `shellcheck`, `docker`, `caddy`, `context` (~598), `secrets` (~614). Triggers: `push` to main, `pull_request`, `workflow_dispatch`.
- The deploy gate (`deploy-lightsail.yml`, ~line 100) needs check runs `test, smoke, browser, shellcheck, docker, secrets, caddy` all with conclusion `success`. A skipped job has conclusion `skipped`, so the gate must be taught, safely.
- `scripts/merge-pr-on-green.sh` reads `gh pr checks` lines `name<TAB>state<TAB>...`; its comment says state is one of pass, fail, pending, skipping, cancel. It counts only `pending` as waiting and `fail` or `cancel` as failed, so `skipping` is expected to be harmless. Confirm and say so in the report; change the script only if a skipped check would block or count as a failure.
- The `browser` job comment says "the main ruleset require[s]" the name; the owner now uses no ruleset. Keep the job name `browser`. Fix that comment to say "the deploy gate requires".

Allowlist, to be checked in step 1: `docs/tasks/`, `docs/plans/`, `docs/archive/`, `docs/reports/`. A directory stays on the list only if no test, script or image build reads it. Brief writer's grep found 22 test files and `scripts/context_lint.py` mentioning these paths; `context_lint.py` reads `docs/tasks/*.md` and `docs/archive/README.md` and its job `context` always runs, so that is fine. Tests are what matter.

Fail open: anything unexpected outputs `code=true`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/ci.yml` | edit | new job `changes`; `needs` and `if` on heavy jobs; aggregate `browser` rule |
| `.github/workflows/deploy-lightsail.yml` | edit | gate accepts `skipped` only with a successful `changes` check run |
| `scripts/merge-pr-on-green.sh` | edit only if step 6 says so | skipped check handling |
| `docs/tasks/1413-report.md` | create | the report |

No other file may change.

## 4. Steps

1. Allowlist check. From the repo root, for each of `docs/tasks`, `docs/plans`, `docs/archive`, `docs/reports` run: `grep -rln "<dir>" App/tests scripts Dockerfile go/Dockerfile .dockerignore deploy 2>/dev/null | head -20`. Then for each hit open only the matching lines (`grep -n`) and decide: does the test or script READ files in that directory at run time (open, glob, Path.read_text, git grep, COPY)? A mention in a comment or a string in a test about a doc's wording does not count. Remove from the allowlist every directory that is read. Record the result per directory in the report. If all four are removed, STOP (section 8).
2. `ci.yml`: insert a job `changes` directly under `jobs:` (before `test:`). Use this body, with the allowlist from step 1 in the `case` pattern (shown with all four):
   ```yaml
     changes:
       # Cheap first job. code=false only when EVERY changed file is on the allowlist.
       # Fails open: any doubt prints code=true.
       runs-on: ubuntu-latest
       timeout-minutes: 5
       outputs:
         code: ${{ steps.diff.outputs.code }}
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
           with:
             fetch-depth: 0
             persist-credentials: false
         - name: Decide whether code changed
           id: diff
           env:
             EVENT: ${{ github.event_name }}
             BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}
             HEAD_SHA: ${{ github.sha }}
           run: |
             code=true
             if [ "${EVENT}" = "pull_request" ] || [ "${EVENT}" = "push" ]; then
               if [ -n "${BASE_SHA}" ] && git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null \
                  && files="$(git diff --name-only "${BASE_SHA}" "${HEAD_SHA}")" && [ -n "${files}" ]; then
                 code=false
                 while IFS= read -r f; do
                   case "${f}" in
                     docs/tasks/*|docs/plans/*|docs/archive/*|docs/reports/*) ;;
                     *) code=true ;;
                   esac
                 done <<< "${files}"
               fi
             fi
             echo "event=${EVENT} base=${BASE_SHA:-none} code=${code}"
             echo "code=${code}" >> "$GITHUB_OUTPUT"
   ```
   Notes for the reviewer: on `pull_request`, `github.sha` is the merge commit and `base.sha` the target tip, so the diff is exactly what the PR adds. On `push` to main, `github.event.before` is the previous main tip (all zeros on a new branch: `cat-file` fails, so `code=true`). `workflow_dispatch` never enters the `if`, so `code=true`. Renames show the new path only; a rename OUT of an allowlisted directory is a deletion there plus an add elsewhere, and `git diff --name-only` lists both paths, so it counts as code.
3. Heavy jobs: add to each of `test`, `test-postgres`, `test-postgres-full`, `go`, `smoke`, `browser-shard`, `shellcheck`, `docker`, `caddy` the two lines (directly after `runs-on:` / `name:` lines, one place per job):
   ```yaml
       needs: changes
       if: needs.changes.outputs.code == 'true'
   ```
   `context` and `secrets` get nothing. If a job already has `needs:`, change it to a list that includes `changes`. Check afterwards: `grep -n "needs:\|^  [a-z-]*:$" .github/workflows/ci.yml | head -50`.
4. Aggregate `browser` job (~line 510): replace `needs: browser-shard` by `needs: [changes, browser-shard]`, and the step by:
   ```yaml
         - name: All browser shards passed, or were skipped because only briefs changed
           env:
             CODE: ${{ needs.changes.outputs.code }}
             SHARDS: ${{ needs.browser-shard.result }}
           run: |
             if [ "${SHARDS}" = "success" ]; then exit 0; fi
             if [ "${SHARDS}" = "skipped" ] && [ "${CODE}" = "false" ]; then exit 0; fi
             echo "browser shards: ${SHARDS} (code=${CODE})" >&2
             exit 1
   ```
   `if: always()` stays. Also change the comment on the line above `if: always()` as in section 2.
5. `deploy-lightsail.yml` (~line 100): the gate is one `python3 -c '...'` one-liner. Replace it with the same logic plus: a job in `need` that has conclusion `skipped` is accepted only if the run named `changes` exists and its conclusion is `success`. Exact replacement of the Python program (keep the shell around it):
   ```python
   import json,sys
   runs={r["name"]:r for r in json.load(sys.stdin)["check_runs"]}
   need=["test","smoke","browser","shellcheck","docker","secrets","caddy"]
   ch=runs.get("changes",{}).get("conclusion")
   ok=lambda n: n in runs and (runs[n]["conclusion"]=="success" or (runs[n]["conclusion"]=="skipped" and ch=="success"))
   print(" ".join(n for n in need if not ok(n)))
   ```
   Keep it a single-quoted one-liner with `;` separators if the surrounding shell needs it (the current line is `python3 -c '...'`), or switch to a `python3 - <<'PY'` heredoc fed by the same curl pipe; either is fine if `bash -n` passes on the extracted run block. Note `browser` itself never concludes `skipped` (it is `if: always()`), so it always has a real verdict; `secrets` never skips.
6. `merge-pr-on-green.sh`: read lines 25 to 60 only. Decide from the code whether state `skipping` is treated as pass: expected yes (only `pending`, `fail`, `cancel` matter). If yes, do not edit the script. If no, make the smallest edit that treats `skipping` as not failing and not pending.
7. Parse check, one call: `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/ci.yml','.github/workflows/deploy-lightsail.yml')]; print('yaml ok')" 2>&1 | tail -5`. If PyYAML is missing, use `ruby -ryaml -e 'ARGV.each{|f| YAML.load_file(f)}' .github/workflows/ci.yml .github/workflows/deploy-lightsail.yml` or state "not parsed" in the report. Also run `git diff -U0 .github | grep -c '^+.*uses:'` and confirm every `uses:` line you added is an `actions/checkout` pin copied from this file (no new action).
8. Dry-run the `changes` logic locally on three diffs and put the output in the report: `for f in docs/tasks/x.md; do case "$f" in docs/tasks/*|docs/plans/*|docs/archive/*|docs/reports/*) echo allow;; *) echo code;; esac; done` for `docs/tasks/x.md`, `App/app/db.py`, `docs/context/status.md` (expected: allow, code, code).
9. Write `docs/tasks/1413-report.md`, set Status: review, commit `1413 step k` per step, push the branch (the executor may push its own task branch; never `main`).

## 5. Do not touch

`App/`, `go/`, Dockerfiles, `deploy-production.yml`, any job other than those named. Hard rules 3, 4, 8 apply. Do not add branch protection or required checks.

## 6. Commands

Steps 1, 3, 7, 8 above. Context lint: `python3 scripts/context_lint.py 2>&1 | tail -30`. No pytest.

## 7. Acceptance

- [ ] Allowlist result per directory is in the report, with the grep evidence for each removed one.
- [ ] YAML parses (or the way it was checked is stated).
- [ ] Report explains, with the evaluated expressions, what runs for: (a) only `docs/tasks/x.md` changed: `changes` ok, `code=false`; heavy jobs `skipped`; `browser` passes via the skipped and code=false branch; `context` and `secrets` run; deploy gate: not reached (PR) or accepts `skipped` because `changes` is `success` (main push); (b) a change under `App/`: `code=true`, everything runs, `browser` needs `success`; (c) mixed `docs/tasks/x.md` plus `App/a.py`: loop sets `code=true`, same as (b); (d) `workflow_dispatch`: `if` not entered, `code=true`, everything runs.
- [ ] Report states how `merge-pr-on-green.sh` treats a skipped check, with the line numbers read.
- [ ] No `uses:` line other than the existing `actions/checkout` pin was added.
- [ ] Context lint has no new error.

## 8. Stop and ask

Stop and write the report if: an anchor is not found verbatim; all four directories are read by tests; a test would be needed; the deploy gate one-liner has changed shape so that step 5 does not fit; you reach 25 tool calls or about 50k tokens; a file outside section 3 needs a change.

## 9. Report

`docs/tasks/1413-report.md` (600 tokens at most), `Status: review`: files changed, the allowlist table, the four scenarios, the merge-script finding, each command with its last 5 lines, deviations, questions, owner steps.

## Risk list (for the reviewer)

`.github/workflows/ci.yml` (the `changes` job and the `browser` aggregate) and the gate edit in `deploy-lightsail.yml`: this is the only place a skipped job could let an unverified commit deploy. Watch for a path in the allowlist that a test reads.

## Owner steps

1. Open the PR and wait for the green check (it runs the full CI once, because it changes `.github/`).
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
3. Afterwards open a docs-only PR and check in the Actions tab that the heavy jobs show "skipped" and the PR still merges.
