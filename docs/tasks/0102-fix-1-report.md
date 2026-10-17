# 0102 correction: wizard actions and police deferral

Status: review

## Change
Owner authorized Codex implementation on 2026-10-14 in this chat.
Wizard Exit, Back, Skip and Check again reuse shared button styles. Header
and footer wrap on narrow screens. The police waiting form is next to Save
and continue, with the existing explanation below both actions.

Both completion blockers are corrected: waiting no longer makes
wizard_unresolved true, and current no longer selects police again after
all other steps are answered. Missing credentials without an explicit
waiting choice still block completion. Reporting readiness and the waiting
checklist status remain unchanged. Reopening an already answered wizard left
unfinished by the former gate now persists completion and shows Done.

## Verification
Local execution is unavailable: the managed workspace failed to start
with "managed network requirements require sandbox enforcement"; no shell
or browser execution tool is exposed. No local test pass is claimed.

PR CI must run:
- Full pytest/coverage and runtime lint in the existing test job.
- Existing guest/host geometry tests plus onboarding browser/survival
  tests in the browser job with UBYHOST_REQUIRE_BROWSER=1.
- Context lint and existing repository checks.

New regression cases cover manual/scheduled modes, locks available or
unavailable, missing credentials with/without acknowledgment, and other
unanswered required steps. Browser coverage walks EN/CS at 360, 390 and
1280 pixels with JavaScript disabled, checks action geometry and adjacency,
reloads Done, and follows Add police login. CI uploads screenshots as
onboarding-wizard-screenshots; new filenames start 18 through 21 in
docs/tasks/0102-evidence/.

CI results are pending at this commit. Do not infer green from earlier PR
runs. No merge or production deployment has been performed.

## Files
- App/app/property_setup.py
- App/app/routes/onboarding_wizard.py
- App/app/templates/setup_wizard/_layout.html
- App/app/templates/setup_wizard/calendar.html
- App/app/templates/setup_wizard/try_it.html
- App/app/templates/setup_wizard/stay_fee.html
- App/app/templates/setup_wizard/door_lock.html
- App/app/templates/setup_wizard/police.html
- App/app/static/host.css
- App/app/templates/base.html
- App/tests/test_onboarding_wizard_browser.py
- App/tests/test_onboarding_wizard_survival.py
- .github/workflows/ci.yml
- This report and context status/known-issues.

## Remaining
Review the CI results and screenshots before merge. PR #389 is still based
on claude/quirky-lamport-9svmd1. Production is owner-operated.
