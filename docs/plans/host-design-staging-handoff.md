# Approved host design: staging handoff

2026-10-10. Owner request: “can you push it to staging for now, so i can check
the new design”. Staging review is authorized; production promotion is not.

## Implementation and access

The approved application design is implemented on `task/host-design-staging`
by the owner-authorized Luna executors, with Codex reviewing. The final
[application review](host-design-application-review.md) lists every page and
links the reports. The older standalone prototype is historical evidence;
application browser checks and screenshots establish the current result.

The scoped [workflow exception](../context/workflow.md#owner-authorized-host-design-execution)
permits feature-branch push/PR and staging deployment for this task. Main push,
production merge and production deployment remain outside its scope.

The original combined validation is recorded in [0037](../tasks/0037-host-validation-report.md).
The owner's deployed screenshots reopened acceptance; the subsequent wide,
mobile and interaction audit is tracked in [0040](../tasks/0040-host-wide-geometry-audit.md).
GitHub CI, PR creation and Render deployment are distinct steps. The staging
service must be redeployed to the corrected feature commit after review.

[PR #338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338) is open for owner review; native Git/GitHub access works. The owner already deployed the first design to staging and supplied screenshots. The displayed Render service is https://ubyhost-staging-01gh.onrender.com. A read-only health request from this workspace failed with a TLS connection error; local Chromium evidence does not establish that the corrected commit is deployed there. The owner will perform the next Render deployment.

Check PR #338's CI and owner review before deploying its exact feature commit
to Render. The PR is attached to this task.
Docker image/health and Docker-based gitleaks checks need CI because the cloud
workspace cannot access a Docker daemon. Do not bypass those checks or merge
to get a preview. Record the reviewed SHA and successful staging health before
claiming deployment.

## Render review, before any production merge

`render.yaml` configures `ubyhost-staging` with `autoDeploy: false`, application
root `App`, `UBYHOST_DEPLOYMENT=staging` and mock UbyPort. It is the documented
UI review service; the owner's actual URL is https://ubyhost-staging-01gh.onrender.com. Git push alone does
not deploy it, and adding this prototype under docs does not replace its app.

Once the application feature branch passes its checks:

1. Open Render → **ubyhost-staging**. Use the implemented feature branch for
   this review (Settings → Build & Deploy → Branch if branch selection is
   required); record the previous staging branch/commit for rollback.
2. Choose **Manual Deploy → Deploy latest commit**. Confirm the deployment
   identifies the exact reviewed commit; wait for **Live**.
3. Open the staging URL and verify `/healthz` succeeds. Keep the existing
   staging/mock configuration and synthetic data. Do not use production guest
   data or reapply the Blueprint/change secrets for this UI review.
4. Check Dashboard, Stays, Invoices, Stay fees/detail, Guest register, Operators,
   invoice generator and Properties/address in EN/CS on desktop and mobile.
   Check alignment, actual copy feedback, Filters Apply/Cancel/reset, date
   selection, and the five-stay/30-day dashboard policy. Record failures and
   the deployed commit with screenshots before any production promotion.
5. If the review build fails, redeploy the recorded previous staging commit.

Follow [the Render instructions](../archive/UbyHost_workplan/STAGING_ON_RENDER_STEP_BY_STEP.md#part-3--deploy-a-new-version-after-github-changes).
The GitHub **Deploy staging** workflow instead targets a separate Lightsail
staging server; it does not update Render. Do not invoke **Deploy production**
or merge to main to get this preview: production deployment can follow green
main CI automatically. No staging deploy has been executed in this session.
