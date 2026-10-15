# 0103: Dashboard calendar implementation report

Status: review
Branch: feature/dashboard-interactive-calendar-20261015
Base: 2662f404a40dc29dac3dcb888e83cf8e5b636f9d

## Result
Replaced the routine dashboard list with Month/Week/Year calendar and property
Gantt beneath the urgent queue. Drag nights to prefill a manual stay; save uses
the canonical protected POST /reservations. Checkout is exclusive. Overlaps
stack and require explicit confirmation. Booking details link to the full stay.
Auto uses Month for 1–2 visible properties and Gantt for 3+; manual choices and
display preferences persist. Waiting for guests was removed from the summary.
The calendar uses existing warm tokens, a bounded owner-scoped endpoint and no
new application dependency or schema. Long manual stays remain valid across years.
Only view/display preferences enter the declared functional browser storage.

## Verification
- JavaScript syntax, date/layout checks and DOM render probes passed.
- [Focused Chromium/API run](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38771202882):
  **39 passed, 0 failed, 0 skipped**, on 92c5265ab04cec0980bf1133004d129b347106e2.
- Covers tenant boundaries, archives/cancellations, checkout/date limits, real
  manual creation/CSRF, overlap confirmation, long stays, Auto/manual preference,
  pointer/keyboard selection, forward and reverse dragging, save/details, retry,
  EN/CS and widths 360/390/760/1024/1280/1440/1680/1920/2048 with collapsed rail.
- [Synthetic screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38771202882/artifacts/11990614482).
- Final keyboard/mouse guard has an additional assertion inside the existing
  interaction test: toolbar clicks cannot submit a keyboard-selected range.
- Final gate: every required [PR check](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/395/checks)
  must be green on the exact candidate SHA. Required browser jobs enforce zero skips.
- Full Python/coverage, lint/type/audit, context, secrets, shell, smoke and Docker
  passed on the earlier candidate. Final-head CI remains the promotion authority.
- Local Python, browser and context commands were unavailable: this chat exposes
  no shell/browser runner. CI executed those checks.

## Staging
Not deployed: Render access is not exposed by the connected tools.

1. Review the exact green PR head and its screenshots. Keep the PR off main.
2. Render → ubyhost-staging → Settings → Build & Deploy → Branch:
   feature/dashboard-interactive-calendar-20261015.
3. Keep staging/mock UbyPort and console mail; use synthetic data.
4. Manual Deploy → Deploy latest commit. Verify the deployed full SHA equals
   the reviewed green head and the service is Live.
5. Verify sign-in, Auto at 2/3 properties, filtering/manual override, dragging,
   exclusive checkout, overlap confirmation, saved stay/details, EN/CS and mobile.
6. Record the Render deployment ID/URL/SHA and keep the previous release for rollback.

The separate Lightsail Deploy staging workflow is not a Render deployment.
No main merge or production deployment was performed.
