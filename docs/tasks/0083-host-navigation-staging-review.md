# 0083: Deploy the reviewed candidate to staging and collect acceptance

Status: blocked — depends on reviewed 0082 and green CI for the complete integration candidate.
Depends on: 0082 done | Candidate: exact published integration SHA recorded at release
Patch status: ready — owner-operated deployment steps, no application patch
Executor: Cursor collects evidence; owner performs Render/configuration/deployment actions

## 1. Objective

Test the implemented design on staging before any main merge or production deployment. Tie acceptance to an actual deployed revision rather than generated mockups or local screenshots.

## 2. Context

Read AGENTS.md, the execution protocol, 0082 report/acceptance, `docs/DEPLOYMENT.md` promotion section, `render.yaml` staging section and `docs/plans/host-design-staging-handoff.md` Render instructions. The Render service is ubyhost-staging with manual deployment and mock UbyPort. The prior service URL is documented, not guaranteed current. GitHub Deploy staging targets a different Lightsail instance.

Exact current staging anchors in `render.yaml`:

```yaml
    name: ubyhost-staging
```

```yaml
    autoDeploy: false
```

No main merge is needed to preview. Main CI can deploy production automatically, so all delivery PRs remain off main until explicit promotion approval.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/host-navigation-staging-acceptance.md` | create | Actual candidate/service/health/walkthrough/defect record |
| `docs/tasks/0083-report.md` | create | Required short report |
| `docs/tasks/0083-host-navigation-staging-review.md` | edit | Status only |
| `docs/tasks/0083-evidence/` | create | Synthetic staging screenshots and sanitized measurements |

No application/workflow/server config/secret/data edits. Owner provider actions are permitted only for the documented staging service and existing mock configuration; a need to change configuration requires an explicit scoped owner action, not an automatic Blueprint reset.

## 4. Steps

1. Verify 0082 done, capture candidate full SHA C, integration branch and main base P, green CI/run URL, previous staging branch/deploy/SHA and rollback route. Freeze the candidate during deployment; if head moves, repin/recheck instead of deploying an unknown moving tip.
2. Owner: open Render -> ubyhost-staging -> Settings -> Build & Deploy. Confirm integration branch selection, staging tier, mock UbyPort, console mail and synthetic data. Do not print secrets, copy production data, switch provider flags or enable production filing/lock behavior.
3. Owner: Manual Deploy -> Deploy latest commit. Confirm deployment metadata names C, wait for Live and record deploy ID/time. If the service cannot deploy/pin C without selecting a different branch, stop for a safe owner correction. Do not merge to main for a preview.
4. Verify actual current service URL and /healthz; verify deployed SHA via Render metadata as well. Health/version alone does not identify code. Sign in using the existing staging method; do not expose credentials in reports/screenshots.
5. Walk every task in the checklist below on synthetic records, EN/CS at desktop/mobile. Review the actual screens against all five boards, preserving complete fields and existing behavior over abbreviated sample image content. Record pass/fail/evidence for each.
6. If defects appear, do not promote. Issue a correction brief, retest/redeploy its complete candidate and reset acceptance to the new SHA. Redeploy the recorded known-good staging release if the candidate breaks the service; data is synthetic and this is a code rollback, not a production database operation.
7. Write acceptance/report and set review. A staging pass is not production approval. Owner explicitly approves staged C and the proposed promotion head F only after reviewing this record, including the protocol proof for any evidence-only commits; record that separately for 0084.

## 5. Do not touch

Production/main, provider secrets/real guests, live SOAP/mail/TTLock actions, fee payment/filing, real invoice issuance, schema/dependencies, test baselines or unrelated Render services. No auto-merge or production workflow dispatch.

## 6. Commands and observations

Use actual Render release metadata for C, HTTPS health and authenticated UI. A failed/blocked health request is recorded as unverified, never guessed. Local application tests already have 0082 evidence; rerun only affected checks for a new fix. Root context lint/diff checks validate report edits. Do not run a production deploy command from this task.

Staging walkthrough, with evidence:

1. Properties: Open correct property; one/many/no-property paths; setup/read-only summary/shared entity/lock-account links.
2. Property Overview/cards: every card opens the exact tab/section; no copied editor; setup truthful.
3. Settings: edit two sections; navigate sections without loss; Save persists both; Discard restores; leaving offers Save/Discard/Stay; invalid inactive field is revealed; Enter saves; Back and reload warnings sane.
4. Calendars: existing states, opened connect form, invalid URL feedback, detail/remove confirmation with synthetic feeds; scope of sync correct.
5. Guest links: Copy/Preview/message and valid/expired behavior; keep actual regeneration effects/confirmation and use fixtures only.
6. Reporting/automation/lock settings: all real fields present and unchanged by unrelated saves; test-only fixture checks, no live provider operation.
7. Business/invoice configuration: correct shared entity, two properties reflect changes; existing invoice snapshot unchanged; ARES/account errors/drafts/return context.
8. Dashboard/Stays: correct counts/window/row cap/default filters; actions aligned; reports/register available; saved guest facts visible; extra empty-slot guard.
9. Invoices: correct eligible stay/builder, Preview/422 data, settings roundtrip and existing PDF with fictional invoices; no real issuance/email.
10. Fees: period/report scope, optional/off/incomplete/finalized states, downloads/protected data, Fix settings return to same month; no payment/filing claim.
11. Account: current email/language/security roles/archive/privacy/technical/help, ordinary user admin restrictions, environment/impersonation warnings and native fallback.
12. Geometry/accessibility: EN/CS long text, widths 360/390/760/1024/1280/1440/1680/1920/2048, collapsed/expanded rail, keyboard/focus, mobile field keyboard and normal-flow Save.

## 7. Acceptance

- [ ] Correct staging service/tier/mock configuration and complete published C verified.
- [ ] Deploy Live + actual HTTPS health + authenticated pages verified; deploy/time/URL/previous release recorded.
- [ ] All twelve walkthrough groups pass with synthetic EN/CS/mobile/desktop evidence and no unresolved defects.
- [ ] Code/runtime/configuration fix invalidates earlier acceptance and is redeployed/rechecked; evidence-only commits are proven and explicitly approved under the protocol rule.
- [ ] Main remains unmerged; production approval is still a separate owner decision.

## 8. Stop and ask

Stop/report on wrong tier/service, unverified SHA, unavailable access, production/shared credentials/data, failed checks, required configuration change or a main/deploy-production action. Give the owner concrete corrective steps; do not bypass a failing CI/deploy gate or infer approval.

## 9. Report

Write `docs/tasks/0083-report.md` (<=1500 tokens): full C/P, Render service/URL/deploy/time, health/CI, walkthrough evidence, defects/resolution/rollback readiness and production-approval status. Link the full staging acceptance document. Set review; no production deployment claim.

## Risk list (for the reviewer)

Check candidate provenance, actual provider metadata, full staging matrix, synthetic screenshots and unchanged-field evidence. Compare code/data semantics with the ownership inventory, not just image similarity.

## Owner steps

1. Deploy exactly C to the staging service and complete the walkthrough.
2. Review defects/evidence; request corrections or explicitly approve C for production.
3. Have the orchestrator record that exact approval and release 0084; until then no main merge or production action.
