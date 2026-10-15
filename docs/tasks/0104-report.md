# 0104 implementation report

Status: implementation prepared; CI execution pending.
Branch: feature/cleaning-management-staging.
Base: e9fe5487ee31276aedf0d141c46ca3cbe584085c.

## Delivered
Broom sidebar navigation, shared calendar/Gantt with cleaning lane, complete
large-type chronological list, host CRUD, persisted automatic checkout events
with durable overrides/dismissals, static instructions, manual codes, permanent
TTLock queue with timeout adoption/revocation, and token-scoped external views.
New migration 0010; no new dependencies or reservation/filing writes.

## Validation
Both JavaScript files parsed with the available V8 runtime before commit.
Focused service/API/provider and real Chromium browser tests added.
Full CI and required screenshot artifacts: pending first feature commit.
No local shell or Python runtime: workspace startup fails with
"managed network requirements require sandbox enforcement".

## Deviations
Reconciliation runs idempotently on schedule reads and the existing minute
worker. This also picks up imports and date/cancellation changes without changing
the canonical reservation/filing mutation paths. Automatic creation is eventual
in background and immediate when the schedule is read.
Cleaning defaults to a 30-day Gantt; Month/Week/Year remain available.
No production or staging deployment has been performed.

## Remaining acceptance
Required CI/browser checks and synthetic captures; exact-SHA Render review;
permanent-code physical lock creation and revocation. Real codes/team links
are disabled while staging no-login mode is active.
