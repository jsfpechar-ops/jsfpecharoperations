# Approved host navigation: execution protocol

> **2026-10-13:** superseded for branching and patch release by the [combined staging lane](host-ux-combined-staging.md): one branch, one draft PR to main, staging only.

Current entry: [production UX correction prompt](production-host-ux-cursor-prompt.md). Run 0087–0094 first; 0071–0074 are replaced. Then release refreshed 0075–0083 and use 0084–0086 acceptance/staging/promotion. The current requirements override older source anchors and disclosure suggestions; never execute a replaced/blocked task.

Approved by owner in chat: 2026-10-12. Code base inspected: `c4c8f979319e53341833065b2a8790c30159581f`.
Scope: the five approved boards and [whole plan](host-navigation-maintainability.md). Cursor implements; Codex orchestrates/reviews. Staging first. Production only after explicit approval of the implemented staging candidate.

## 1. Approval and hard limits

Design and implementation direction are already approved. Do not ask to approve the same layouts again. Proceed through released briefs and the existing report/review workflow. A missing source anchor, unexpected data contract, changed scope or failing check requires an evidence-based correction brief, not guessed implementation.

No amount of detail can guarantee error-free delivery. The safeguards are exact patch release, narrow file ownership, automated behavior checks, real browser evidence, review of the changed revision, staging acceptance and an explicit production approval record.

This document adds a scoped branch protocol for this delivery. Existing privacy, UbyPort, invoice, fee, lock, retention and authentication requirements remain in force. Do not revive the paused #338 work or another session's implementation authority. The current request authorizes this plan/PR and the Cursor implementation process, with owner-operated staging and promotion steps.

## 2. Production trigger: treat main as a release action

Verified current `.github/workflows/deploy-production.yml` has both manual `workflow_dispatch` and automatic `workflow_run` on successful **CI** for **main**. `docs/DEPLOYMENT.md` confirms automatic promotion. Older manual-only lines in AGENTS/rules/Lightsail docs must not be used to claim a main merge is harmless.

Therefore:

- No implementation or planning PR from this delivery is merged to main before staging acceptance and production approval. A docs-only merge can also run main CI and redeploy the current app.
- No auto-merge, queue-to-main, CI run on main to trigger deployment, Deploy production dispatch or production SSH operation before approval.
- Keep the workflow unchanged in this UI delivery. Staging-first safety comes from isolated integration branches plus the explicit owner promotion gate. Do not disable checks or rewrite deployment logic to obtain a preview.
- The owner may approve final main promotion after staging. That approval acknowledges the existing automatic production deploy following green main CI; a second manual deployment is unnecessary when the automatic run succeeds.

## 3. Branch topology and PR ownership

Planning branch: `task/host-navigation-plan`. Integration branch: `task/production-host-ux-integration`. Task branches use their brief names. The planning PR is reviewable and held off main; Cursor can check out its branch directly without merging it first.

```text
main (c4c8f97... inspected base)
  └─ task/host-navigation-plan         planning PR → main, do not merge yet
       └─ task/production-host-ux-integration
            ├─ task/0071-...          report PR → integration
            ├─ task/0072-...          scoped extraction PR → integration
            └─ subsequent tasks      one reviewed PR at a time → integration

approved integration SHA → staging → explicit owner approval
                         → final reviewed promotion PR → main → CI → production
```

Owner initialization, after reviewing the planning PR:

```bash
git fetch origin task/host-navigation-plan
git switch -c task/production-host-ux-integration origin/task/host-navigation-plan
git push -u origin task/production-host-ux-integration
```

If the integration branch already exists, fetch and switch to it; do not recreate, reset or force-push it. Preserve dirty working trees and unrelated work; use an isolated worktree when necessary. Record the integration SHA before each task.

Each task starts from the latest reviewed integration tip, not from stale main or an earlier task. Its PR base must be `task/production-host-ux-integration`. Owner merge uses `scripts/merge-pr-on-green.sh` after the orchestrator verifies the PR base, current head CI, scope and report. The script checks CI but does not enforce a staging approval/base-branch gate; inspect the base before calling it.

The final integration PR to main remains draft/unmerged until production approval. If the planning PR is separate, do not merge it independently and do not duplicate its changes across releases; final promotion already contains the planning ancestry.

## 4. Brief release lifecycle

0071 is **todo**. 0072 includes an exact deterministic extraction command but depends on reviewed 0071. The later task files are complete implementation/acceptance contracts, explicitly **blocked** until their predecessors are reviewed and the orchestrator attaches an exact patch against that current revision. They are not runnable instructions to improvise.

This is a source-verification gate, not repeated design permission. Every future code patch must reflect the predecessor's actual implementation; a prewritten guessed diff would defeat the repo's anchor rule. The owner has authorized progression within scope. After each report, the orchestrator:

1. Verifies current SHA, CI, file allowlist and actual browser evidence.
2. Records the reviewed integration tip and marks the completed task done when its review/merge is complete.
3. Pastes exact code/diffs into the next blocked brief, using its named files and anchors. Removes obsolete anchors and validates the replacement ones. Records `Patch status: ready` and the exact base SHA.
4. Sets only that next brief todo. The status change and patch release go in a planning update PR to integration, with no main/production action.
5. Gives the next brief to a fresh Cursor executor chat. No simultaneous tasks editing the same files.

If a contract must change, issue a numbered correction brief. Do not silently broaden scope, set every future task todo, skip a failed baseline or treat a generated screenshot as executable UI logic. A task with `Patch status: pending` stays blocked.

## 5. Executor start and completion protocol

Start:

1. Read AGENTS.md, the master prompt, this protocol and the one released task. Read only sources named by that task. Never read all of `host_i18n.py` or a large route module.
2. Record branch, HEAD, working tree and reviewed integration parent. Validate Depends on, Status, Patch status and exact source anchors before editing.
3. Distinguish source/rendering changes from existing business logic. Keep all existing field names, successful-control payloads, CSRF/access checks and feature guards unless the released patch explicitly changes them with tests.
4. Execute the exact patch once. Use focused reads to diagnose a failure; no broad redesign, force push, database reset, schema changes or unrequested dependency.

Completion:

1. Run relevant regression/browser checks and required full checks in the exact environment below.
2. Capture real screenshots and measured geometry for modified pages with synthetic fixtures and masked secrets. Put only the brief's named evidence in the repo; never real guest/operator data.
3. Check the diff path list against §3. An extra file is a scope failure, even if convenient.
4. Write the task report, tick acceptance with evidence and set task review. Publish a task PR to integration only if executor policy/access permits; otherwise provide exact owner publication commands.
5. Stop at review. Do not merge, advance to a blocked task or deploy from the executor chat.

## 6. Form and data invariants

Property: one canonical form, one copy of each DOM ID/field and existing full-property save semantics initially. Switching sections keeps drafts. Inactive visual sections must not lose successful controls. Reveal invalid controls before browser validation feedback. Save includes earlier section changes; Discard restores persisted values. Native link/JavaScript-disabled fallback remains usable without a second template implementation.

Dirty navigation: Save/Discard/Stay applies to transitions out of the settings draft, including cards, tabs, entity links, sidebar and explicit Back links. Browser unload gets the native warning, not attempted asynchronous saving. No password/PIN/guest data in browser storage. Preserve drafts on field/server errors; do not report persistence success before it happens.

Existing property Enter-default hidden submit and test-connection save-first behavior remain intact. Test/refresh/regenerate actions keep their current handlers/effects/confirmation; they must not accidentally submit to a general save or initiate a live provider operation during tests.

Entity: one record shared by properties/future invoices. Preserve create/edit field differences, ARES behavior, signatures and VAT/account defaults. Contact/identity edits must never rewrite issued invoice snapshots. Do not render a second invoice-specific editor with copied common fields; adapter routes invoke the same canonical implementation.

Fees: shared fields already exist; preserve parser behavior for omitted/blank/invalid/IBAN-only values before consolidating savers. No change to calculations, report grouping/finalization, protected-register data, guest exemptions or manually recorded sent/paid facts.

URLs: `/guest-links` and `/automation` retain 303 property-hub compatibility; one/many/no-property behavior is explicit. Old anchors reveal the correct section. Return paths use current safe-local guards. POST compatibility delegates the same validation/save and rerender path; it is never a redirect that drops submitted values.

## 7. Test commands and evidence

Use Python 3.12 and the repo's pinned requirements/dev/browser version, preferably the existing verified virtualenv. No requirements edits. Current CI pins Playwright 1.63.0; if absent, use the same existing CI setup, not a new version:

```bash
cd App
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install playwright==1.63.0
.venv/bin/python -m playwright install chromium
```

OS/browser prerequisites may require the supported environment setup. If unavailable, report the blocker; do not set REQUIRE_BROWSER off or claim skipped checks passed. Do not edit lockfiles, install a new application dependency or run provider calls.

Required application check, from App:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 \
  .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841
```

From repository root:

```bash
python3 scripts/context_lint.py
git diff --check
git diff --name-only
```

Every task names focused tests, executed before the full check. Browser/geometry acceptance requires 0 skips, both locales, widths 360/390/760/1024/1280/1440/1680/1920/2048 and collapsed/expanded sidebar. Use `UBYHOST_SHOTS_DIR` or the actual existing module's capture flag/path; do not invent an evidence environment variable. Source inventory must confirm the capture destinations, then copy only synthetic screenshots into the task evidence directory.

Record failed counts, skips and causes accurately. Historical 0066 failures are not current results. Fix diagnosed failures through a scoped correction brief; don't weaken assertions, skip failing tests, normalize clipped layouts or blindly repeat the entire suite. CI must be green on the actual current PR head, including smoke/guest-browser/shellcheck/Docker/secrets/context jobs.

## 8. Staging gate — task 0085

Owner operates **Render → ubyhost-staging**, which has manual deploy and mock UbyPort. Actual previously documented URL is `https://ubyhost-staging-01gh.onrender.com`; verify the service's current URL before recording it. GitHub Deploy staging targets a separate Lightsail service and is not a substitute for a Render deployment claim.

1. Final integrated candidate C is reviewed, current CI green and tested against the latest relevant main base P. Record previous staging branch/release for rollback.
2. Verify staging tier, mock UbyPort and console mail in the service configuration without printing secrets. Never use production guests. Do not flip live lock/provider flags or treat mock reporting as a police filing.
3. Select the integration branch on Render and **Manual Deploy → Deploy latest commit**. Check deployed commit is C and status Live; if Render cannot pin the checked SHA, do not deploy a moving tip.
4. Verify health and actual signed-in pages. Production health does not necessarily expose a commit or tier: verify SHA via provider release metadata as well as health, not a guessed health field.
5. Execute the detailed 0085 walkthrough in EN/CS and desktop/mobile. Capture before/after values for unchanged settings using fixtures, not sensitive screenshots. Verify old links and return navigation. Record every failure.
6. If a code/runtime/configuration fix changes C, rerun affected checks, redeploy and obtain approval for the new candidate. Previous approval does not carry to unreviewed new code. Evidence-only commits use the narrow rule below.

Required staging report: service/URL, branch, deployed full SHA C, compared main base P, deploy ID/time in Prague, health result, CI run URL for C, test matrix, screenshot links, discovered defects/resolution, rollout/rollback readiness. Status cannot be passed from local screenshots alone.

### Evidence commits after staging

Staging has a concrete deployed SHA C. Writing acceptance/status reports necessarily creates later commits. Do not create an endless redeploy/report loop or silently call a later SHA the staged SHA.

Record the tested code SHA C and proposed promotion head F separately. F may differ from C only in these evidence paths: `docs/tasks/0084-report.md`, `0085-report.md`, `0086-report.md`, their respective `0084-evidence/`, `0085-evidence/`, `0086-evidence/` directories, status-only edits to those three briefs, `docs/plans/host-navigation-integration-acceptance.md`, `host-navigation-staging-acceptance.md`, `host-navigation-production-approval.md`, `host-navigation-production-release.md`, and `docs/context/status.md`. The unprefixed task/plan names here are relative to their stated docs directories.

The orchestrator must prove the complete C-to-F path diff is confined to that allowlist and that App, tests, workflows, scripts, deployment/configuration/dependency files and every other non-evidence path are identical. Record C/F and that proof in the approval record. The owner approval must explicitly cover F or the tested C content plus these evidence-only commits. Do not infer this allowance from design approval. If any other path changes, F is a new candidate requiring re-tests, staging and approval. Current-head CI must still be green for F.

## 9. Production approval and promotion — task 0086

0086 is owner-operated and blocked until 0085 has evidence and the owner explicitly approves production for candidate C. Put that approval in `docs/plans/host-navigation-production-approval.md`: full C and promotion head F, C-to-F evidence-only proof if applicable, staging deploy ID/URL, main base P, date/time, exact approving owner instruction, test-report links, known limitations and allowed promotion. Never prefill approval, infer it from design approval, or mark it approved because CI is green.

Before promotion, verify main is still P (or that a re-integrated candidate has been re-tested and re-approved). The final PR head must be approved F, with all non-evidence paths identical to staged C under the explicit rule above. If unrelated main changes would alter the delivered tree, integrate them and repeat staging acceptance. The owner reviews the final PR diff and base before invoking `scripts/merge-pr-on-green.sh`.

After owner merge to main, main CI can launch Deploy production automatically. Record the final main merge SHA M and its relationship to approved C; confirm the deployed non-evidence tree matches approved F and tested C, with the inspected base preserved. Review CI/deploy logs and provider/server revision; do not equate app version 1.1.0 or a healthy endpoint with a verified source commit.

Production smoke: authenticated Dashboard/Stays/Properties, one settings read-only visit, invoice PDF, fee report, legacy links, tier/provider labels, no unexpected exceptions. Use existing production data read-only for smoke; avoid filings, email, lock changes, mutation of real guests or arbitrary fee/invoice operations. Record actual app health, release revision and owner verdict.

Rollback: owner redeploys the previously recorded known-good code revision using the established deployment runbook. UI work has no schema migration or data rewrite; do not roll back/replace the database for a visual defect. Destructive server checkout/reset commands remain owner-operated with explicit approval, not executor automation.

## 10. Ordered task files

0071 readiness → 0072 property extraction → 0073 property navigation → 0074 calendars → 0075 shared entity fields → 0076 entity navigation → 0077 fee setup compatibility → 0078 Properties → 0079 Dashboard/Stays list → 0080 stay detail → 0081 invoices → 0082 fee reports → 0083 account → 0084 integration acceptance → 0085 staging → 0086 owner promotion.

See the plan's linked task list and [Cursor master prompt](host-navigation-cursor-prompt.md). Resume from the first released todo task whose prerequisites are done; never infer that blocked tasks are optional.
