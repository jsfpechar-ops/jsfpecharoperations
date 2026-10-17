# 0086: Owner-approved production promotion and smoke report

Status: blocked — explicit owner approval of the accepted staging candidate is required.
Depends on: 0085 done plus exact staging-candidate production approval | Operator: owner only
Patch status: ready — gated owner runbook; no application patch

## 1. Objective

Promote only the explicitly approved staging candidate and record the actual production revision/smoke result. Preserve data and existing filing/lock/invoice/fee behavior; never confuse design approval or green CI with production approval.

## 2. Context

Read AGENTS.md, execution protocol §§2/8/9, 0085 report/staging acceptance, `docs/DEPLOYMENT.md` promotion section, `docs/LIGHTSAIL.md` current release/rollback section and `scripts/merge-pr-on-green.sh`. Current successful main CI can automatically trigger Deploy production, so merging the final PR is itself a production-release action.

The executor/orchestrator may prepare the final reviewable candidate/PR and evidence. Only the owner performs main merge, production workflow, server/secrets or rollback operations. No action is permitted by this blocked file until its explicit approval record exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/host-navigation-production-approval.md` | create | Exact owner instruction, candidate and staging evidence; never prefilled |
| `docs/plans/host-navigation-production-release.md` | create | Actual release/health/smoke/rollback record |
| `docs/tasks/0086-report.md` | create | Required final report |
| `docs/tasks/0086-host-navigation-production-promotion.md` | edit | Actual lifecycle status only |
| `docs/context/status.md` | edit | At most five lines, actual deployed revision/outcome |

No application/workflow/schema/dependency changes and no production database mutation. Owner release operations follow the existing guard/runbooks, not a scripted executor workaround.

## 4. Steps

1. Record the owner's explicit production approval verbatim with time, full staged candidate C and proposed promotion head F, permitted evidence-only diff proof, staging service/deploy ID/URL, main base P and acceptance/CI links. If approval omits the candidate or it changed afterward, clarify that specific missing release identity; do not reuse the earlier design approval.
2. Reconfirm final PR head is approved F, its non-evidence tree matches accepted C, and all required checks are green. Follow the narrow protocol evidence allowlist; any other C-to-F change requires new staging/approval. Reconfirm current main is P or demonstrate/retest a newly integrated main base. Any materially different candidate needs new staging evidence and approval. No auto-merge before this gate.
3. Owner: inspect the final PR base is main and the approved exact head/tree, then merge only with `scripts/merge-pr-on-green.sh` using that actual PR number. Do not force push/reset/bypass or merge intermediate planning/task PRs separately. Planning ancestry is contained in the final integration release.
4. Record resulting main revision M and its code-tree relationship to staged C and approved F. Watch main CI and the existing automatic Deploy production run. If the automatic run succeeded, do not dispatch a redundant manual deploy. A manual fallback uses the existing Deploy production workflow with force_confirm=DEPLOY only after the same approval and green-current-main checks.
5. Verify actual source revision via deployment/provider/server metadata, public HTTPS health and authenticated tier/provider labels. Production health may omit a SHA/tier; a version string is insufficient. Record deployment URL/run/time and expected backup/integrity/row-count guard results from the established deploy process.
6. Owner performs read-only production smoke: Dashboard/Stays/Properties, one configuration visit, canonical business/legacy links, existing invoice PDF, fee report/month return and account navigation. No live filing, guest mutation, real invoice creation/email, PIN/lock change or fee payment/filing action as visual smoke. Record failures accurately.
7. If a regression exists, use the recorded known-good code revision and established owner rollback runbook. Do not replace/restore the production database for a presentation regression. Recheck health/revision/smoke and record the rollback result.
8. Write release/report/status. Set done only after owner review of actual successful deployment/smoke or an explicitly documented rollback outcome. A merged PR alone does not complete the task.

## 5. Do not touch

Provider credentials/targets, schema, database volume, live filing/lock lifecycle, invoice snapshots/fee finalized data, guest data, policies or deployments unrelated to this approved candidate. No executor main merge/SSH/workflow dispatch, guessed approval, hidden failed deployment or misleading health-based SHA claim.

## 6. Commands and evidence

Before any production action, owner has the complete candidate/approval record and final PR. Use the existing merge guard and current deployment workflow/runbook with the actual PR/revision; no hardcoded fictitious PR/SHA. Context lint/diff checks validate documentation afterward. CI, deployment and smoke each have distinct evidence and timestamps. No application test runs against production.

## 7. Acceptance

- [ ] Exact staged C, approved F, any evidence-only proof, staging evidence, P and owner instruction recorded before promotion.
- [ ] Final PR/current-main checks pass and delivered tree matches the approved candidate.
- [ ] Owner guarded merge only after approval; actual M/CI/deploy run recorded.
- [ ] Actual production source revision, health/tier/provider and read-only smoke verified.
- [ ] Existing data/backup guards intact; rollback revision/action/outcome documented if needed.
- [ ] Production status/report truthful; no unsupported provider or data mutation.

## 8. Stop and ask

Keep blocked without explicit candidate approval. Stop/report on changed candidate/base, pending/failing CI, wrong environment, unavailable proof of revision, failed smoke, database/credential operation, or proposed bypass. Give the owner exact corrective context; do not silently promote or redeploy.

## 9. Report

Write `docs/tasks/0086-report.md` (<=1500 tokens): approval/C/P/M, final PR and CI/deployment links, source/health/smoke evidence, data/rollback guard results, unresolved issues, status updates and owner verdict. Link full approval/release records; redact operational secrets and personal data.

## Risk list (for the reviewer)

Approval provenance, candidate/tree matching, actual final-main/deployed revision, automatic deployment consequence, read-only smoke scope, backup/rollback evidence and truthful final status.

## Owner steps

1. Approve the exact staging candidate for production after reviewing 0085.
2. Guardedly merge its final promotion PR; watch main CI/production deployment.
3. Verify revision/health/read-only smoke; approve completion or execute the established rollback.
