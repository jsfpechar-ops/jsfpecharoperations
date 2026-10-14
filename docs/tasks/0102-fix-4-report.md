# 0102: quiet list actions, consistent hover and setup polish

PR: https://github.com/jsfpechar-ops/jsfpecharoperations/pull/389
Branch: cursor/onboarding-wizard-1045

## Result

- Phone calling code is a plain numeric text field, maximum three digits,
  with a fixed + prefix. No datalist or spinner; pill uses current host tokens.
  Existing international numbers and legacy POSTs stay supported, with no schema change.
- Sharing and demo messages render the property's current name. The demo has
  a visible example label and explains that actual message content and timing
  depend on the host's booking-platform setup; no platform integration is claimed.
- Property overview uses eight static setup status tiles on a tinted dashed
  panel, separate from navigation cards. Accurate readiness details and field
  links are retained behind a question-mark disclosure. Police waiting remains amber.
- Stays hover/focus paints the whole row instead of individual cells. This
  removes isolated stripes, gaps and the early highlight on empty-count marks.
  Stay context and local jump navigation use centered horizontal margins.
- Removed duplicate Open buttons from Stays, Properties and Dashboard, and
  redundant detail/open controls in report/fee lists. Open and copy remain
  in three-dot menus; native date/name links and row keyboard/click navigation
  remain. Send, downloads, configuration and archive/restore protections stay.
- Removed booking portal shortcuts and large repeated guest-link buttons on
  stay detail. Copy remains in its main menu, including for incomplete stays.
- Collapsed account control centers the avatar and removes the detached arrow;
  native disclosure, accessible account name, Escape and focus return remain.

## Verification

The desktop workspace has no callable execution tools; validation runs in the
existing GitHub CI workflow on this commit. This report does not claim local
commands or a human visual screenshot review. Check the PR's exact-head CI run.
The preceding commit b669f0ce6e53338e06ae2a06065655a1ed3e0259 passed all seven
jobs in run 38586471807.

Updated existing phone/message, row-action and missing-guest regressions.
Added browser checks for uniform hover and stable geometry, row click and Enter,
menu Open, JS-off native links, centered stay navigation, collapsed account
alignment and keyboard operation, current property name, visible demo labeling,
static overview status and police deferral. Widths: 360, 390, 1280, 1440,
1920 and 2048; EN/CS. Existing filing/claim/CSRF tests stay in full pytest.

CI guest-browser also runs the existing mixed-status stay-actions and saved
stay-detail layout suites. Screenshot artifact onboarding-wizard-screenshots
includes evidence 36 uniform hover, 37 stay alignment, 38 account alignment,
39 labeled demo message and 40 overview status, plus earlier wizard evidence.

## Release

No merge or deployment. Owner can deploy the resulting branch commit to Render.
