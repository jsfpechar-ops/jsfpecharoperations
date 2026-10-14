# 0102: sharing, demo and guest-flow polish

PR: https://github.com/jsfpechar-ops/jsfpecharoperations/pull/389
Branch: cursor/onboarding-wizard-1045

## Changes

- Operator phone has an editable country-code pill. The existing contact_phone
  column stores the combined international number; unusual legacy formats and
  posts omitting the field remain supported. No schema or dependency change.
- Guest link and PIN use matching cards and equal copy controls. PIN security
  and message-customisation details use question-mark help. The full EN/CS
  guest message includes registration, example key collection/directions,
  quiet hours and the operator's first name. No private example addresses.
- Continue setup is a primary button. Demo wording replaces test wording;
  setup instructions use dark bold text and supplementary detail lives in ?.
  Door lock has one skip action when no lock can be selected.
- Demo walkthrough shows the created property, dates, progress and a full
  message bubble. Clicking its link opens a private practice PIN screen in a
  new tab, then the existing guest form. Wrong PIN retries retain destination.
  Demo access remains owner-only; real guest claims and filing exclusions stay.
- Host message is fully visible only on the arrival/date page. The closed
  Why explanation sits below the guest form with a ? indicator. Decorative
  text arrows are removed from active templates and host labels.
- The supplied c05 avatar-and-bars shimmer replaces host and guest navigation
  placeholders, using current light skeleton colors. Hidden-page pause,
  reduced motion, download/new-tab opt-outs and navigation cleanup remain.

## Verification

The managed workspace could not start (sandbox enforcement error); no local
command or rendered screenshot pass is claimed. Validation runs in GitHub CI
on the commit containing this report; use the PR checks for the exact run.
The preceding commit 3e6441139be83867ebfa9d2f364022d075a7abbc passed all seven
jobs in run 38557932146.

Added checks cover phone composition/edit/create/legacy posts; copy geometry
and clipboard; EN/CS at 360, 390 and 1280 pixels with JS on/off; demo preview
and PIN isolation/retry; guest host-message placement and question disclosure;
shimmer geometry, pause and reduced motion. Existing guest-group browser flow
still fills and signs each person. CI also runs download skeleton regressions.
Existing demo exclusion, claim, PIN, CSRF and filing tests remain in full pytest.

Screenshots are uploaded by guest-browser to onboarding-wizard-screenshots.
New evidence 27–35 covers phone, Continue, sharing, lock, automation, loader,
reduced motion, demo PIN and walkthrough. Earlier evidence 01–26 is retained.

## Release

No merge or deployment was performed. Owner may deploy the resulting branch
commit on Render for visual acceptance. Production remains owner-operated.
