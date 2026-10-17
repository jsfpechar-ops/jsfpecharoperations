# 0102 follow-up: calendar, demo and setup cards

Status: review

## Changes
- The calendar platform name is visible only for Other, including without
  JavaScript. Named platforms retain the server's canonical name. Other
  validation errors remain visible with their draft selection.
- Try creates or reuses the demo stay and redirects its native POST into
  the guest form in a new tab. The wizard remains open and refreshes when
  focus returns; without JS, Check again is available. Host authorization,
  CSRF protection and demo exclusion rules remain in place.
- The stay-fee introduction shares the setup heading's typography.
- Setup summary uses the property overview's card design and icons.
  Completed steps have green Set up labels; skipped steps stay neutral;
  police credentials waiting stay amber with Add police login.
- The property overview says Connected calendars. Copy link sits alongside
  the guest-link text, and the card grid uses equal row heights.

All new labels are EN/CS. No dependency, database, filing, guest form,
fee arithmetic or deployment change.

## Verification
The managed execution workspace still fails to start with
"managed network requirements require sandbox enforcement"; no local
test or screenshot run is claimed. Changes are committed through the
connected GitHub tools, with an expected-head check on the feature ref.

CI verification is the [PR checks](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/389/checks).
The previous correction, ae7db6e, passed all seven jobs in
[run 38552768915](https://github.com/jsfpechar-ops/jsfpecharoperations/actions/runs/38552768915).
Those results do not stand in for this follow-up's checks.

Required checks: full pytest/coverage, runtime lint, context lint,
secret scan, shell checks, smoke, Docker, and the browser job.
Browser invocation includes onboarding browser/survival tests with
UBYHOST_REQUIRE_BROWSER=1.

New browser cases cover EN/CS at 360, 390 and 1280 pixels with JS enabled
and disabled: platform visibility and retry, canonical platform save,
one-click guest-form tab, fee font geometry, summary status colors and
card layout, clear overview label, copy action placement and equal heights.
A server regression checks the demo redirect, direct guest-form access,
stay reuse and unchanged step progress. Existing demo exclusion tests
are unchanged.

Screenshot evidence is uploaded by CI in onboarding-wizard-screenshots:
22-calendar-platform, 23-demo-new-tab, 24-fee-intro, 25-summary-cards,
and 26-overview-cards, each with language/width/JS suffix under
docs/tasks/0102-evidence/.

## Scope
App templates for calendar, try_it, stay_fee, done, property overview and
base asset versions; onboarding_wizard route; host CSS/JS; host_i18n;
onboarding browser/survival tests; this report and context status/known issues.

## Remaining
Owner visual review, then the governed merge/deploy path. PR #389 retains
its host UX base branch. No production deployment has been performed.
