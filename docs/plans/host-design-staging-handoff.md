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

Local combined validation is recorded in [0037](../tasks/0037-report.md).
GitHub CI, PR creation and Render deployment are distinct steps. The staging
service has not been updated in this session.

[PR #338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338) is now open for owner review; GitHub API access succeeded. Render access and deployment remain unverified after the earlier network block.
The saved environment draft adds `api.github.com`, `render.com`,
`api.render.com`, `ubyhost-staging.onrender.com` and the official Czech legal
sources while preserving package-manager domains. In environment settings,
review/save and publish that draft. Saving alone does not activate access.
Native Git reads and feature push authentication use the existing HTTPS proxy.
No duplicate GitHub token is needed. Check existing deployment secret metadata
once the API is reachable before requesting any additional credential.

Check PR #338's CI and owner review before deploying its exact feature commit
to Render. The PR is attached to this task.
Docker image/health and Docker-based gitleaks checks need CI because the cloud
workspace cannot access a Docker daemon. Do not bypass those checks or merge
to get a preview. Record the reviewed SHA and successful staging health before
claiming deployment.

## Render review, before any production merge

`render.yaml` configures `ubyhost-staging` with `autoDeploy: false`, application
root `App`, `UBYHOST_DEPLOYMENT=staging` and mock UbyPort. It is the documented
UI review service at https://ubyhost-staging.onrender.com. Git push alone does
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
