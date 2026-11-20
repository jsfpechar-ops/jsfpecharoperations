# 1866: Enterprise CI/GitHub hardening (repo-side) + settings runbook

Status: todo
Depends on: 1865 (same workflow files) | Base commit: 481f5e28a348d6b28e837b6576de2cd081aa24d0 | Branch: task/1866-enterprise-ci-github
Executor: Haiku 5.5 | Fits one session: yes

## 1. Objective

Close the CI/GitHub gaps found in the owner's 2026-11-20 enterprise review:
deploy workflows lack job timeouts, gitleaks scans only the last 50 commits,
the PR template has no security/deploy checklist, and the GitHub *settings*
side (branch protection, environment reviewers, secrets hygiene) is only in
chat notes. This brief does the repo files; the settings are owner steps in
§Owner steps with exact commands.

## 2. Context

- `docs/context/decisions.md` 2026-11-13: "No GitHub branch protection or
  required checks (owner); merge via merge-pr-on-green.sh" — the known gap.
  Branch protection is a repo *setting*, fixed by the owner (§Owner steps);
  `scripts/merge-pr-on-green.sh` keeps working because it only merges PRs that
  are green and approved.
- `ci.yml`: top-level `permissions: contents: read`; every job has
  `timeout-minutes`; gitleaks job (~line 718) runs dockerized gitleaks on the
  last 50 commits only.
- `deploy-lightsail.yml`, `deploy-production.yml`, `deploy-staging.yml`: jobs
  have NO `timeout-minutes` (grep shows timeouts only in ci/security/scorecard).
- `security.yml`: actionlint + zizmor (min-severity high) on every PR +
  dependency-review (fail on high, deny AGPL-3.0/GPL-3.0). `scorecard.yml`:
  weekly OSSF Scorecard + CodeQL sarif upload. All actions SHA-pinned,
  `persist-credentials: false`.
- `.github/dependabot.yml`: weekly pip, github-actions, docker (/ and /go),
  gomod.
- `.github/CODEOWNERS`: `*` plus critical paths → @jsfpechar-ops.
- Environments (gh api, 2026-11-20): `production` has a branch_policy rule;
  `staging` exists since 2026-11-13 with no protection rules (secrets to be
  filled by owner); legacy `main - ubyhost-staging-01gh` still exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/deploy-lightsail.yml` | edit | `timeout-minutes: 20` on the lightsail job |
| `.github/workflows/deploy-production.yml` | edit | `timeout-minutes: 20` on each job (after 1865) |
| `.github/workflows/deploy-staging.yml` | edit | `timeout-minutes: 20` on the job (after 1865) |
| `.github/workflows/ci.yml` | edit | gitleaks: full history on push to main, last 50 on PRs |
| `.github/PULL_REQUEST_TEMPLATE.md` | edit | add Security & deploy checklist |
| `docs/context/workflow.md` | edit | add "GitHub settings runbook (owner)" section |

No other file may change.

## 4. Steps

1. Add `timeout-minutes: 20` right after `runs-on: ubuntu-latest` in every job
   of the three deploy workflows.
2. `ci.yml` gitleaks step: keep the current last-50-commits scan for
   `pull_request`; when `github.ref == 'refs/heads/main'` (push) run the full
   history instead (drop the `--max-count=50` log opt). Verify the exact
   current line first; if it differs from this description, STOP (§8).
3. Append to `.github/PULL_REQUEST_TEMPLATE.md`:

   ```markdown
   ## Security & deploy

   - [ ] No secrets, keys, guest data or operator identity in the diff (gitleaks + zizmor CI green)
   - [ ] Every new outbound request has its reason in the PR (rules.md #2)
   - [ ] Deploy impact named: staging auto-deploys on green main; production only via manual Deploy production (force_confirm=DEPLOY)
   - [ ] test-map row for the changed area run, output tail pasted in the PR
   - [ ] Docs updated — one explanation lives in one place
   ```

4. Append to `docs/context/workflow.md` a section `## GitHub settings runbook (owner)`
   listing: branch protection on `main` (required checks CI + Security, 1
   approving review, code-owner reviews, no force-push, no deletion, required
   conversation resolution); `production` environment = required reviewer
   (owner) + branch policy main-only; `staging` environment = LIGHTSAIL_*
   secrets + LIGHTSAIL_HEALTH_URL var, any branch; delete legacy environment
   `main - ubyhost-staging-01gh`; quarterly rotation of SSH deploy keys and any
   remaining RENDER_* hooks; 2FA on the account, monthly audit-log review,
   weekly OSSF Scorecard findings triaged. Include the exact `gh api` command
   for branch protection shown in §Owner steps.

## 5. Do not touch

`App/`, `go/`, `deploy/lightsail/`, `security.yml`, `scorecard.yml`,
`uptime.yml`, `dependabot.yml`, all secrets, every other ci.yml job. Hard
rules from AGENTS.md: never push to `main`; merge only via
`scripts/merge-pr-on-green.sh`.

## 6. Commands

- `python3 scripts/context_lint.py 2>&1 | tail -30` — must exit 0
- `git diff --stat 2>&1 | tail -10`
- actionlint runs in CI (`security.yml`); if docker is available locally,
  `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.9 -color`.

## 7. Acceptance

- [ ] `python3 scripts/context_lint.py` exits 0
- [ ] all three deploy workflows have `timeout-minutes` on every job
- [ ] ci.yml gitleaks scans full history on main pushes, last 50 on PRs
- [ ] PR template has the Security & deploy section
- [ ] workflow.md has the GitHub settings runbook
- [ ] `git diff --stat` lists only the 6 files in §3

## 8. Stop and ask

Per TEMPLATE.md §8, plus: if brief 1865 is not merged yet, STOP (this brief
touches the same two workflow files).

## 9. Report

Write `docs/tasks/1866-report.md` (≤600 tokens), set `Status: review`.

## Risk list (for the reviewer)

- `.github/workflows/ci.yml` gitleaks step — wrong log-opts would scan nothing.
- `deploy-*.yml` — timeout placement must be job-level, not step-level.

## Owner steps (GitHub settings — run with an admin token or in the UI)

1. Branch protection on `main` (the current integration gets 403 on this
   endpoint, so use your admin PAT / the UI):
   `gh api -X PUT repos/jsfpechar-ops/jsfpecharoperations/branches/main/protection --jq ...`
   with required_status_checks = CI + Security, required_pull_request_reviews
   = 1 review, dismiss stale, require code-owner reviews, allow_force_pushes
   false, allow_deletions false, required_conversation_resolution true,
   enforce_admins false (so merge-pr-on-green.sh can still merge green PRs).
2. Settings → Environments → `production`: add yourself as required reviewer;
   keep the branch policy and set it to `main` only.
3. Settings → Environments → `staging`: secrets `LIGHTSAIL_HOST=3.68.93.233`,
   `LIGHTSAIL_SSH_PRIVATE_KEY` (from `~/.ssh/lightsail_deploy` on
   Ubyhost-test-env), `LIGHTSAIL_KNOWN_HOSTS` (`ssh-keyscan -t ed25519,rsa
   3.68.93.233`); variable `LIGHTSAIL_HEALTH_URL=https://staging.ubyhost.com/healthz`.
4. Delete the legacy environment `main - ubyhost-staging-01gh` if unused.
5. Revoke the Cloudflare API token pasted into chat on 2026-11-20 (Cloudflare →
   My Profile → API Tokens → Revoke); remove `RENDER_*_DEPLOY_HOOK` secrets when
   Render staging is suspended; rotate SSH deploy keys quarterly.
6. Account hygiene: 2FA on, monthly audit-log review, triage the weekly
   Scorecard results under Security → Code scanning.
