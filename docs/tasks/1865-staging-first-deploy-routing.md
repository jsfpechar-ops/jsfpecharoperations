# 1865: Green-main deploys go to Lightsail staging; production manual-only

Status: todo
Depends on: none | Base commit: 481f5e28a348d6b28e837b6576de2cd081aa24d0 | Branch: task/1865-staging-first-deploy
Executor: Haiku 5.5 | Fits one session: yes (4 files, no tests beyond lint)

## 1. Objective

Route deploys staging-first: when CI on `main` finishes green, the change is
automatically deployed to the staging Lightsail server (GitHub environment
`staging`, instance `Ubyhost-test-env` 3.68.93.233, https://staging.ubyhost.com,
`UBYHOST_DEPLOYMENT=staging`) instead of production. Production (environment
`production`, ubyhost.com) is deployed only on explicit owner approval:
Actions → **Deploy production** → `force_confirm=DEPLOY`, after clicking the
change through on staging. Reason (owner, 2026-11-20): the prod-shaped Lightsail
staging box now exists, so nothing should reach production unreviewed there.

## 2. Context

Current wiring, verbatim excerpts.

`.github/workflows/deploy-production.yml` lines 12-22:

```yaml
on:
  workflow_dispatch:
    inputs:
      force_confirm:
        description: "Type DEPLOY to deploy the current main revision to production"
        required: true
        type: string
  workflow_run: # zizmor: ignore[dangerous-triggers] runs only for CI on main pushes; the job checks event != pull_request and head_branch == main, and checks out nothing from the triggering run
    workflows: [CI]
    types: [completed]
    branches: [main]
```

Both jobs in that file use the same `if:` (lines 47-52 and 62-67):

```yaml
    if: >-
      (github.event_name == 'workflow_dispatch' && github.event.inputs.force_confirm == 'DEPLOY')
      || (github.event_name == 'workflow_run'
      && github.event.workflow_run.conclusion == 'success'
      && github.event.workflow_run.head_branch == 'main'
      && github.event.workflow_run.event != 'pull_request')
```

`.github/workflows/deploy-staging.yml` lines 20-42 hold only `workflow_dispatch`
(inputs `branch`, `ubyport_env`, `skip_ci_check`); its single job (lines 53-65):

```yaml
jobs:
  lightsail:
    # 0422: deploy-lightsail.yml pushes the image to GHCR. Granted here, not
    # at workflow level, so the other job keeps read-only permissions.
    permissions:
      contents: read
      checks: read
      packages: write
    uses: ./.github/workflows/deploy-lightsail.yml
    with:
      environment: staging
      ref: ${{ inputs.branch || github.ref_name }}
      require_green_ci: ${{ !inputs.skip_ci_check }}
      ubyport_env: ${{ inputs.ubyport_env || 'mock' }}
    secrets: inherit
```

The reusable `.github/workflows/deploy-lightsail.yml` already refuses a run whose
server `.env` does not match the target environment, so an auto staging run can
never touch the production server.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/deploy-production.yml` | edit | drop `workflow_run` trigger + conditions; drop `render-staging` job; header comment |
| `.github/workflows/deploy-staging.yml` | edit | add `workflow_run` trigger (CI green on main); extend job `if:`/`ref:`/`require_green_ci:`; header comment |
| `docs/DEPLOYMENT.md` | edit | architecture + promotion text: staging auto on green main, production manual-only; Render suspended |
| `README.md` | edit | line ~15 staging bullet → Lightsail staging |

No other file may change.

## 4. Steps

1. `deploy-production.yml`: remove the `workflow_run:` block (lines 19-22).
   Change both jobs' `if:` to exactly:
   `if: github.event_name == 'workflow_dispatch' && github.event.inputs.force_confirm == 'DEPLOY'`
   Delete the entire `render-staging:` job (Render `ubyhost-staging` is suspended
   in favour of the Lightsail staging box; its `RENDER_*_DEPLOY_HOOK` secrets are
   then unreferenced). Rewrite the header comment to say: production deploys ONLY
   manually with force_confirm=DEPLOY after the owner approves the change on
   staging; green CI on main auto-deploys to staging via deploy-staging.yml.
2. `deploy-staging.yml`: add after the `workflow_dispatch` inputs:

   ```yaml
     workflow_run: # zizmor: ignore[dangerous-triggers] runs only for CI on main pushes; the job checks conclusion == success, head_branch == main, event != pull_request, and deploys that run's head_sha
       workflows: [CI]
       types: [completed]
       branches: [main]
   ```

   Give the `lightsail` job this `if:` and these `with:` values:

   ```yaml
     if: >-
       github.event_name == 'workflow_dispatch'
       || (github.event_name == 'workflow_run'
       && github.event.workflow_run.conclusion == 'success'
       && github.event.workflow_run.head_branch == 'main'
       && github.event.workflow_run.event != 'pull_request')
     uses: ./.github/workflows/deploy-lightsail.yml
     with:
       environment: staging
       ref: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || inputs.branch || github.ref_name }}
       require_green_ci: ${{ github.event_name == 'workflow_run' || !inputs.skip_ci_check }}
       ubyport_env: ${{ inputs.ubyport_env || 'mock' }}
   ```

   Update the header comment: manual runs deploy any branch (ubyport_env mock or
   test); on green CI for main the workflow auto-deploys that head commit with
   ubyport_env=mock.
3. `docs/DEPLOYMENT.md`: replace the architecture block (lines ~47-60) and the
   promotion paragraph (~59-63) with: CI on every PR and on main; green main →
   automatic **Deploy staging** (Lightsail `staging` environment,
   staging.ubyhost.com, mock UbyPort); manual branch deploys via Actions →
   Deploy staging; production (ubyhost.com) ONLY via Actions → Deploy
   production with force_confirm=DEPLOY after clicking the change through on
   staging. Mark Render `ubyhost-staging` as suspended/optional UI smoke test.
4. `README.md` line ~15: staging bullet → "Lightsail `Ubyhost-test-env`
   (staging.ubyhost.com), mock/test UbyPort, auto-deployed on green main;
   manual per branch via Actions → Deploy staging".

## 5. Do not touch

`App/`, `go/`, `deploy/lightsail/`, `.github/workflows/ci.yml`,
`deploy-lightsail.yml`, `deploy-preflight.yml`, secrets, any `.env`. Hard rules
from AGENTS.md: never push to `main`; merge only with
`scripts/merge-pr-on-green.sh`. Do not add the GitHub environment `staging` —
that is an owner step (secrets), not a repo change.

## 6. Commands

From the repo root:

- `python3 scripts/context_lint.py 2>&1 | tail -30` — must exit 0.
- `git diff --stat 2>&1 | tail -10`
- CI `security.yml` (zizmor) must accept the new `workflow_run` trigger through
  the ignore comment — copy the exact comment style of deploy-production.yml
  line 19. Do not weaken zizmor config.

## 7. Acceptance

- [ ] `python3 scripts/context_lint.py` exits 0
- [ ] `deploy-production.yml` contains no `workflow_run:` and both `if:`s are the manual-only expression
- [ ] `deploy-staging.yml` has both triggers; the job `if:` covers dispatch and workflow_run; `ref:` uses `workflow_run.head_sha` on auto runs
- [ ] `docs/DEPLOYMENT.md` + `README.md` describe staging-first routing
- [ ] `git diff --stat` lists only the 4 files in §3

## 8. Stop and ask

Per TEMPLATE.md §8, plus: if any quoted excerpt is not found verbatim, STOP;
if zizmor/security CI rejects the new trigger, STOP and report — do not edit
`.github/workflows/security.yml`.

## 9. Report

Write `docs/tasks/1865-report.md` (≤600 tokens), set `Status: review`.

## Risk list (for the reviewer)

- `.github/workflows/deploy-production.yml` — a leftover `workflow_run` condition
  would still auto-deploy production; read the full diff of the `if:` lines.
- `.github/workflows/deploy-staging.yml` — trigger/job condition mistakes could
  auto-deploy the wrong ref; check `ref:` and `if:` carefully.

## Owner steps

1. Create GitHub environment `staging`: secrets `LIGHTSAIL_HOST=3.68.93.233`,
   `LIGHTSAIL_SSH_PRIVATE_KEY` (contents of `~/.ssh/lightsail_deploy` on
   Ubyhost-test-env), `LIGHTSAIL_KNOWN_HOSTS` (`ssh-keyscan -t ed25519,rsa
   3.68.93.233`); variable `LIGHTSAIL_HEALTH_URL=https://staging.ubyhost.com/healthz`.
2. Merge this PR with `scripts/merge-pr-on-green.sh`; the merge itself then
   auto-deploys to staging under the new routing — verify
   https://staging.ubyhost.com/healthz still shows `deployment=staging`.
3. Suspend Render `ubyhost-staging`; delete `RENDER_*_DEPLOY_HOOK` secrets if unused.
4. Revoke the Cloudflare API token that was pasted into a chat on 2026-11-20
   (Cloudflare → My Profile → API Tokens → Revoke); treat it as exposed.
5. Optional: move staging to its own domain/zone (e.g. app.ubyhost-test.com) so
   the production zone's WAF challenge rules do not apply to staging `/login`
   (see K-STG-WAF in docs/context/known-issues.md).
