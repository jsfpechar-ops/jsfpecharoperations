> The later calendar/cleaning follow-up supersedes these UI details and contains the final tested application SHA and CI evidence: [0123 calendar and cleaning correction](0123-calendar-cleaning-fix-report.md).

# 0123 implementation report

Status: review
Branch: feature/host-design0123-20261016 | PR: #397
Application SHA: cfe277c4c31d6694fa89142d8d90b65f7e66cd88
Base: 7835b528cec95a1d7a25798e0002d28c0255f346
Brief: docs/tasks/0123-host-design.md

## Delivered

The signed-in workspace now uses the approved flat-white work surfaces, real UbyHost mark and sidebar icons, warm rail, coral actions, centered lane, and compact count pills. Dashboard and Stays use safe stay labels and visible native actions; Stays shows the full date range and retains filing, filters, saved views, export, archive and restore. Compact View/Period selects preserve Auto/manual calendar behavior and month/week/year. Stay details keep guest facts open and retain reporting, receipt, invoice and door-code controls.

Properties settings and the Property wizard own the editable check-in/check-out pair. Door-lock setup and Cleaning show inherited property hours and a Properties link. Cleaning automatic turnover uses property hours while preserving legacy columns and explicit event adjustments. TTLock issuance and its buffers/timezone behavior remain unchanged.

## Verification

[CI run #1195](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38902687125) passed all eight jobs on the application SHA above. The required Chromium job passed 165 tests with 0 failures and 0 skips; calendar review passed 80 with 0 failures and 0 skips. The full test, smoke, Docker, context, secrets and shellcheck jobs also passed.

CI uploaded [dashboard and calendar review screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38902687125/artifacts/12047441670), [calendar feature screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38902687125/artifacts/12046922584), and [onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38902687125/artifacts/12047199318). The managed environment had no local browser or screenshot viewer, so I did not personally inspect the rendered pixels; owner visual review remains.
