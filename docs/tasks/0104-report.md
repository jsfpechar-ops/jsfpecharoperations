# 0104 implementation report

Branch: feature/cleaning-management-staging.
Base: e9fe5487ee31276aedf0d141c46ca3cbe584085c.
Review: [PR #396](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/396).
The exact reviewed revision is the PR head associated with its required CI run.

## Delivered
Broom sidebar navigation, shared calendar/Gantt with a cleaning lane, complete
large-type chronological list, host CRUD, persisted automatic checkout events
with durable overrides/dismissals, static instructions, manual codes, permanent
TTLock queue with timeout adoption/revocation, and scoped external views.
Migration 0010; no new dependencies or reservation/filing writes.
Manual takeover of the same TTLock PIN (including the keypad #) keeps that
physical code valid; a different replacement explains and confirms revocation.
Property/lock mapping is checked before provider creation and before activation;
changed mappings cannot publish a code for the old lock. Codes from a replaced
binding are hidden and queued for revocation. Provider logs contain error kinds
and numeric codes, not potentially secret response text.

## Validation
Required CI is the execution path:
- Feature: python -m pytest tests/test_cleaning.py tests/test_cleaning_browser.py
  tests/test_dashboard_calendar.py tests/test_dashboard_calendar_browser.py -q -rs
- Full suite: python -m pytest tests -q --cov=app --cov-fail-under=86
- Required guest/host/geometry Chromium checks; zero skips.
- Ruff, dependency audit, smoke, Docker, shellcheck, secrets and context lint.
- EN/CS captures at 360, 390, 1024 and 1280px; external view with/without JS.
- Browser checks exercise filtering, late-loading scripts, drag rescheduling,
  create/edit/delete and unchanged reservations. Tokens are tested for property
  isolation, bounds, expiry, revocation and no write authority.
Validation at 5b24aac56807fcf35dada74e00d1027a472a009a:
77 focused checks passed, 0 failed, 0 skipped. Full application tests with
coverage, Docker, smoke, context, secrets and shellcheck also passed.
The final PR revision adds the staging no-login secret guard and reruns all
required checks; current results are linked below.
Both JavaScript files also parsed with the available V8 runtime.
[Current results and artifacts](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/396/checks)
are tied to the exact PR revision; use the calendar-feature-review artifact for
synthetic cleaning screenshots. Initial CI found a markup compatibility anchor,
documentation caps, a missing next-arrival fixture and CSP-sensitive test waits;
those were corrected without weakening application policy.

No local shell/Python: workspace startup fails with
"managed network requirements require sandbox enforcement".

## Implementation choices
Reconciliation runs on schedule reads and the existing minute worker, picking up
imports and date/cancellation changes without altering canonical reservation or
filing mutation paths. Generation is eventual in the worker and immediate when
the schedule is read. Cleaning defaults to a 30-day Gantt; Month/Week/Year remain
available. List and calendar consume the same authorized snapshot. A delayed list
script can recover the in-memory calendar snapshot; nothing is persisted in
browser storage except display preferences.

## Staging and physical acceptance
No production or staging deployment has been performed in this chat.
1. Verify green required CI for the exact feature revision.
2. Deploy that revision to Render staging with mock UbyPort and verify its SHA.
3. Disable staging no-login before door-code setup or new company links. Both
   manual/API writes and plaintext cleaning-code display are blocked in that mode.
4. On a designated test lock, create a permanent cleaning PIN and test it; replace
   or remove it, verify the old PIN stops opening, and check offline recovery.
5. Review the external link on a phone, revoke it, and verify access is denied.
The repository service configuration alone does not prove current server settings.
