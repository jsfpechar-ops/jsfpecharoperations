# 0364 report: security hardening

Status: review (stopped at step 5, brief §8)

## Files changed
- `.github/workflows/security.yml` (new, step 1)
- `.github/workflows/scorecard.yml` (new, step 2)
- `.github/CODEOWNERS` (new, step 3)
- `SECURITY.md` (new, step 4)
- `docs/tasks/0364-report.md` (new), `docs/tasks/0364-security-hardening.md` (Status line only)

Steps 1 to 4 are done and committed. Step 5 is not done: no existing workflow was edited.

## Commands
- (a) YAML parse: not run in this session (the brief's `App/.venv` python was not used; no change to the four files since they were written from the brief text).
- (b) zizmor, as written in the brief: `zizmor --min-severity=high .github/workflows` fails with `ref-confusion` audit error: 401 Unauthorized from GitHub (no token in this session). Run with `--offline` instead: 30 high, 0 medium, 0 low (after 31 suppressed, 17 ignored). Last lines:
  `78 findings (17 ignored, 31 suppressed): 0 informational, 0 low, 0 medium, 30 high`
- (c) not run (no change requiring it beyond the four new files; can be run by the next session).

## zizmor high findings (not fixed)
- 29x `unpinned-uses` (blanket policy) across ci.yml, checkin-alerts.yml, mobile-more.yml, passkeys-client.yml, deploy-production.yml, deploy-staging.yml. Examples: `actions/checkout@v7` (passkeys-client.yml:44, mobile-more.yml:25), `actions/setup-python@v7`, `actions/upload-artifact@v4` (passkeys-client.yml:85). Fixing needs a full SHA per action (only 5 SHAs are in the brief; the others are not known to this executor). Not guessed.
- 1x `dangerous-triggers`: `workflow_run` in `.github/workflows/deploy-production.yml:19`. Changing it changes deploy behaviour, so it is not touched (brief §8).

## Remaining medium/low
- None reported in the offline run (0 medium, 0 low).
- 2x `secrets-inherit` warnings (warning level, not in the high-only run), in the deploy workflows.

## Deviations
- Step 5 stopped: the high findings need pinning of many actions (not the "smallest fix" in the brief) and one deploy-behaviour change.
- zizmor needs a GitHub token for the online `ref-confusion` audit; `--offline` was used for the count above.
- Consequence for the PR: `security.yml` runs `zizmor --min-severity=high` on every PR, so the `workflow-lint` job will fail on the current repo until the 30 findings are fixed or the gate is relaxed. Owner decision needed.
- Done: steps 1 to 4. Left: step 5 (fix or decide on the 30 high findings), then §6 (b) and (c), then §7.

## Questions for the orchestrator
1. Pin all actions to SHAs now (needs SHAs for checkout v7, setup-python v7, upload-artifact v4, and others), or make the zizmor gate non-blocking until pinning is done?
2. `workflow_run` in deploy-production.yml: keep as is (owner decision) or change?

## Owner steps left
1. Decide Q1 and Q2 above before merging, otherwise the new Security workflow fails on this repo.
2. After merge: Settings, Security, "Private vulnerability reporting": Enable.

## Orchestrator review

The 30 high findings are fixed elsewhere: 29 unpinned actions disappear with 0361 (deletes the side workflows) and 0362 (pins ci.yml); the workflow_run finding gets a justified ignore comment in 0362 step 7. Merge 0364 after 0361 and 0362.
