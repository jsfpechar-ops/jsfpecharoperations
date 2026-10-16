# 0123 Calendar and cleaning correction

Status: review  
Branch: `feature/host-design0123-20261016` · PR #397  
Tested application SHA: `807e88183e3294f9368ce5443f21cf367ec43222`

## Changes

Restored native property/month/year selectors, icon-and-label Calendar/Gantt segments, and Month/Week/Year segments. Existing Auto mode, property-count threshold, Settings checkbox, URL/storage preferences, filters, and keyboard controls remain authoritative. Control groups align at 36px desktop and 46px mobile, with 44px segment buttons.

Booking display endpoints use property check-in/out hours as fractional positions while reservation dates, overlap checks, and creation remain date-only. A stay departing on the 17th reaches its checkout time on the 17th. Week and month clipping retain continuation edges.

Automatic cleaning is displayed on the checkout date between property checkout and check-in hours; a later arrival remains contextual information. Cleaning uses a separate visible lane and cleaning-specific overflow summaries, including a mobile day summary that opens the existing dialog. Its compact chronology uses 17px date headings and readable 14–16px facts; the normal editor has no duplicate time inputs, with Properties owning the window. Legacy explicit event times remain supported; omitted form fields do not clear them. Missing or invalid hours show a timing warning and a visual-only fallback, never a persisted or confirmed time. A non-increasing property window is reported as unavailable; genuine reservation conflicts remain separately visible. Demo reservation exclusions, sharing boundaries, optional code permissions, and existing actions remain intact. Empty code and instruction sections are omitted.

## Verification

[CI run 38920124400](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38920124400) passed all eight jobs on the tested application SHA. The full test job, smoke, Docker, context, secrets, and shellcheck passed. Calendar review passed **89 tests, 0 failures, 0 skips**; the required browser job passed **169 tests, 0 failures, 0 skips**.

CI uploaded [calendar feature screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38920124400/artifacts/12053864908), [dashboard and calendar review screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38920124400/artifacts/12054434274), and [onboarding screenshots](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38920124400/artifacts/12055291824). The managed environment had no local browser or screenshot viewer, so I did not inspect rendered pixels; owner visual review remains.

## Later follow-ups

For the current Render staging hand-off, use [calendar creation report](0123-calendar-create-popup-report.md) and tested commit `a8a3de98db922c3ec1192e9f2d7e2927eec7cb29`. The 807e881 evidence above covers the earlier correction.
