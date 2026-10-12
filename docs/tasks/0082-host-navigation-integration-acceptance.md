# 0082: Verify the integrated host navigation candidate

Status: blocked — depends on reviewed 0081 and every preceding implementation report.
Depends on: 0069–0081 done | Branch: task/0082-host-navigation-integration-acceptance | PR base: task/host-navigation-integration
Patch status: ready — verification/report only; no application patch
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Establish a green, reproducible integration candidate before staging. Verify the actual implementation, route ownership, form state, both locales and desktop/mobile geometry across the approved page families.

## 2. Context

Read AGENTS.md, the execution protocol and reports 0069–0081. All designs are approved; this task verifies behavior rather than redesigning it. Read only changed source paths and tests recorded by those reports, the ownership inventory, approved plan/boards and the named deployment/CI configuration.

Current source deployment warning:

```yaml
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]
```

`.github/workflows/deploy-production.yml` is read-only. Main CI can deploy automatically; do not merge/dispatch main to run acceptance.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/plans/host-navigation-integration-acceptance.md` | create | Full route/behavior/locale/width checklist and actual results |
| `docs/tasks/0082-report.md` | create | Required short report |
| `docs/tasks/0082-host-navigation-integration-acceptance.md` | edit | Status only |
| `docs/tasks/0082-evidence/` | create | Synthetic screenshots, sanitized logs/measurements only |

No application/test/workflow/secret/schema change. If any defect requires a fix, issue a scoped correction brief and rerun affected acceptance against the corrected candidate; do not patch inside this verification task.

## 4. Steps

1. Confirm all predecessors done and integrated sequentially, capture full integration SHA C and current main SHA P. Confirm no unrelated changes, unresolved conflicts, missing source patches or skipped requirements. Record every report and current CI reference.
2. Reconcile the ownership inventory with the final source: one editor per property setting, one shared entity editor, one fee field/save owner, no copied global guest-link/automation editor, no desktop/mobile cloned forms. Count real rendered IDs/controls, not conditional template source branches.
3. Use synthetic fixtures to execute the entire execution-protocol behavior matrix: one/many/no/archived properties; dirty Save/Discard/Stay; hidden invalid controls; legacy hashes/GET/POST adapters; report month/context returns; shared entity and immutable invoice; rate/IBAN/omitted values; valid/unavailable invitation links; expected-slot safeguards; role-aware account and shared-lock navigation. Link each fact to a focused test or measured/manual evidence.
4. Verify all page families through normal links/Search/Back; actual report/register/privacy/archive routes remain available. Do not exercise real provider mutations. Cover EN/CS, JS-enabled and required native fallbacks, keyboard/focus, copy/save/error feedback, long names and expanded/collapsed rail.
5. Run §6 with the supported browser environment, capture actual implementation screenshots at 360/390/1280 and measured widths 760/1024/1440/1680/1920/2048 as well. Put the full test/route matrix in the integration acceptance document, short summary in the report. Generated mockups are never test screenshots.
6. CI on the final feature candidate must be green including all required jobs. If GitHub checks are unavailable, mark CI unverified and do not call candidate accepted. If main advanced materially since the inspected base, reconcile through a new scoped update and rerun tests before staging approval.
7. Set review and stop. The owner/orchestrator must review evidence before marking done and releasing staging 0083. Do not merge to main or deploy from this task.

## 5. Do not touch

All application/test/deploy/business code and data; no skipped tests, relaxed assertions, live filing, real mail, real lock mutation, mass archive, database rollback, main merge or provider credential access. Only the named report artifacts change.

## 6. Commands

Use all exact full-suite/ruff/context commands from the execution protocol; REQUIRE_BROWSER=1, deployment=staging, UbyPort=mock, scheduler off, coverage >=86. Add focused tests introduced by 0071–0081, then the full regression suite. Record actual command results and CI check URLs for current candidate C. Required browser/geometry 0 skips; unknown/pending/failing CI blocks acceptance.

For source revision evidence:

```bash
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/main
python3 scripts/context_lint.py
git diff --check
```

Do not compare only version strings. Final report/evidence commits must receive their own CI before deployment; C in staging is the published complete candidate, not an earlier code-only commit with stale reports.

## 7. Acceptance

- [ ] Every previous task done, scoped diff reviewed and integrated; actual C/P recorded.
- [ ] One canonical editor and preserved domain contracts demonstrated by the ownership/behavior matrix.
- [ ] Full suite and coverage pass; required browser/geometry 0 skips; actual current-head CI green.
- [ ] EN/CS, all required widths, rail states, long content, keyboard and focus measured.
- [ ] Synthetic screenshots/feedback and no real data leakage; complete checklist and limitations linked.
- [ ] No outstanding acceptance/regression defect; staging handoff identifies exact published candidate.

## 8. Stop and ask

Stop/report if any predecessor is unreviewed, checks fail/skip, CI/source SHA is unverified, main drift requires reconciliation, a feature/domain guard was removed, or a fix needs application changes. The orchestrator writes a correction brief; do not proceed to staging with hidden defects.

## 9. Report

Write `docs/tasks/0082-report.md` (<=1500 tokens): candidate/base, report/diff scope, full/focused/CI results, §7, links to acceptance/screenshots/measurements, limitations and owner staging steps. Set review; no deployment claim.

## Risk list (for the reviewer)

Review the complete acceptance matrix against the integrated source changes and test outputs. Verify artifacts/CI refer to C and that all named route/data invariants actually survived the phased refactor.

## Owner steps

1. Review acceptance, current CI and unresolved defects.
2. Mark 0082 done only when evidence is complete; select candidate C for staging.
3. Release 0083 and follow its Render staging instructions; stay off main.
