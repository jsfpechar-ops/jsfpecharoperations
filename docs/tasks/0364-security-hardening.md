# 0364: Security hardening: workflow lint, dependency review, Scorecard, CODEOWNERS, SECURITY.md

Status: review
Depends on: 0361 and 0362 must merge first (they remove the 30 high zizmor findings) | Base commit: main | Branch: task/0364-security-hardening
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The repo is public and launches soon. Add the checks a top engineering team runs on every PR: workflow security lint (actionlint and zizmor), a dependency review that blocks known-vulnerable or badly licensed new packages, a weekly OpenSSF Scorecard, a CODEOWNERS file and a vulnerability-reporting policy.

## 2. Context

- Action SHAs resolved 2026-10-24 with `git ls-remote` (pin form `uses: owner/repo@SHA # vX`):
  `actions/checkout` v7 = `3d3c42e5aac5ba805825da76410c181273ba90b1`,
  `actions/dependency-review-action` v4.9.0 = `2031cfc080254a8a887f58cffee85186f0e49e48`,
  `ossf/scorecard-action` v2.5.0 = `fa7117db83c52d787ae5a89f350999701505d78e`,
  `github/codeql-action` (upload-sarif) v4.39.1 = `9b3254085494b55a0f7c4c2b3d2d52cc712ce370`,
  `zizmorcore/zizmor-action` v0.8.0 = `53290badfa369cb0bf7ad16342cb62c2fa47ac7b`.
- Owner GitHub login: `jsfpechar-ops`. Security notes already live in `docs/SECURITY.md` (do not edit it; link to it).
- Hard rule 3: public repo, never commit secrets, e-mail addresses of the operator, or server names.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/security.yml` | create | `workflow-lint` and `dependency-review` jobs |
| `.github/workflows/scorecard.yml` | create | Weekly OpenSSF Scorecard, results to the Security tab |
| `.github/CODEOWNERS` | create | Owner reviews everything, named sensitive paths |
| `SECURITY.md` | create | How to report a vulnerability privately |
| `.github/workflows/*.yml` (existing) | edit | Only to fix zizmor findings of high severity, see step 5 |
| `docs/tasks/0364-report.md` | create | Report |

No other file may change.

## 4. Steps

1. Create `.github/workflows/security.yml`:
   ```yaml
   name: Security

   # Supply-chain checks on every PR: workflow files are linted for
   # mistakes and injection risks, and new dependencies are checked for
   # known vulnerabilities and licences before they reach main.
   on:
     pull_request:
     push:
       branches: [main]

   permissions:
     contents: read

   concurrency:
     group: security-${{ github.ref }}
     cancel-in-progress: true

   jobs:
     workflow-lint:
       runs-on: ubuntu-latest
       timeout-minutes: 5
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
           with:
             persist-credentials: false
         - name: actionlint
           run: docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.9 -color
         - name: zizmor (high severity fails)
           uses: zizmorcore/zizmor-action@53290badfa369cb0bf7ad16342cb62c2fa47ac7b # v0.8.0
           with:
             min-severity: high
             advanced-security: false

     dependency-review:
       if: github.event_name == 'pull_request'
       runs-on: ubuntu-latest
       timeout-minutes: 5
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
           with:
             persist-credentials: false
         - uses: actions/dependency-review-action@2031cfc080254a8a887f58cffee85186f0e49e48 # v4.9.0
           with:
             fail-on-severity: high
             deny-licenses: AGPL-3.0, GPL-3.0
             comment-summary-in-pr: never
   ```
   Commit `0364 step 1`.
2. Create `.github/workflows/scorecard.yml`:
   ```yaml
   name: Scorecard

   # OpenSSF Scorecard: a weekly score of this repo's security practices
   # (branch protection, pinned actions, token permissions, ...). Results
   # appear under Security > Code scanning.
   on:
     schedule:
       - cron: "17 4 * * 1"
     push:
       branches: [main]
     workflow_dispatch:

   permissions: read-all

   jobs:
     analysis:
       runs-on: ubuntu-latest
       timeout-minutes: 10
       permissions:
         security-events: write
         id-token: write
       steps:
         - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
           with:
             persist-credentials: false
         - uses: ossf/scorecard-action@fa7117db83c52d787ae5a89f350999701505d78e # v2.5.0
           with:
             results_file: results.sarif
             results_format: sarif
             publish_results: true
         - uses: github/codeql-action/upload-sarif@9b3254085494b55a0f7c4c2b3d2d52cc712ce370 # v4.39.1
           with:
             sarif_file: results.sarif
   ```
   Commit `0364 step 2`.
3. Create `.github/CODEOWNERS`:
   ```
   # Every change needs the owner's review. The lines below name the paths
   # where a mistake reaches guests, the police filing or the servers.
   *                                   @jsfpechar-ops
   /.github/                           @jsfpechar-ops
   /deploy/                            @jsfpechar-ops
   /scripts/                           @jsfpechar-ops
   /App/app/migrations/                @jsfpechar-ops
   /App/app/auth.py                    @jsfpechar-ops
   /App/app/ubyport*                   @jsfpechar-ops
   /Dockerfile                         @jsfpechar-ops
   ```
   Commit `0364 step 3`.
4. Create `SECURITY.md`:
   ```markdown
   # Security policy

   UbyHost handles guest registration data for the Czech foreign police, so we
   take vulnerability reports seriously.

   ## Reporting a vulnerability

   Please do not open a public issue. Use GitHub's private reporting instead:
   **Security** tab, **Report a vulnerability**. We reply within 3 working days
   and keep you updated until it is fixed.

   Please include the affected URL or file, the steps to reproduce, and what an
   attacker could do. Do not access other people's data, run denial-of-service
   tests, or use automated scanners against production.

   ## Supported versions

   Only the version running at ubyhost.com (the `main` branch) gets fixes.

   ## How we work

   Our security practices are described in [docs/SECURITY.md](docs/SECURITY.md).
   ```
   Commit `0364 step 4`.
5. Run zizmor locally on the existing workflows: `python3 -m venv /tmp/zz && /tmp/zz/bin/pip install -q zizmor 2>&1 | tail -2 && /tmp/zz/bin/zizmor --min-severity=high .github/workflows 2>&1 | tail -30` (a throwaway venv outside the repo; this is a CI tool, not a project dependency). For each **high** finding, apply the fix zizmor names in the smallest way (usually: move a `${{ ... }}` from a `run:` block into `env:` and use `"$VAR"`). Do not touch medium or low findings; list them in the report. If a fix would change what a deploy does, do not apply it: list it. Re-run until 0 high findings. Commit `0364 step 5`.
6. Run §6 and write the report.

## 5. Do not touch

`App/`, `docs/SECURITY.md`, `scripts/merge-pr-on-green.sh`, job names in `ci.yml`, deploy behaviour. Never push, merge or use secrets.

## 6. Commands

(a) `App/.venv/bin/python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('ok')" .github/workflows/*.yml 2>&1 | tail -5` prints `ok`.

(b) `/tmp/zz/bin/zizmor --min-severity=high .github/workflows 2>&1 | tail -10` reports no high findings.

(c) `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.

## 7. Acceptance

- [ ] The four new files exist with the content above.
- [ ] §6 (a) to (c) as expected; the report lists the medium and low zizmor findings left.

## 8. Stop and ask

Stop, and write the report, if: zizmor cannot be installed; a high finding needs a deploy-behaviour change; you reach 25 tool calls or about 50k tokens; a step is unclear; you would need push, merge or secrets.

## 9. Report

Write `docs/tasks/0364-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

`.github/workflows/security.yml`, `.github/workflows/scorecard.yml`, any edited existing workflow.

## Owner steps

1. Merge when CI is green.
2. Settings, Security, "Private vulnerability reporting": Enable (SECURITY.md points to it).
