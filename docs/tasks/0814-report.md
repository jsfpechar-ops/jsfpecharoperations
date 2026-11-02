# 0814 report

Status: review (partial: remaining failures are stay fees, owned by 0796)

## Files changed
- `App/app/templates/housebook.html`: `housebook-scroll` div also gets `scroll-x` (the touch probe's documented scroll-container marker). Fixes the ipad1024 `/housebook` Open buttons reported as outside.
- `App/app/static/app2.css` (0792 and 0793 blocks only):
  - 0792: `body.v2 .invoices-page tbody tr .btn.sm.ghost:focus-visible{opacity:1;transition:none}` (Download PDF was opacity 0 on keyboard focus).
  - 0793: `body.v2 .housebook-page .housebook-scroll:focus-visible{outline:2px solid #d0452d;outline-offset:2px}`.
- No test files changed. No commit, no push.

## Commands (last lines)
- Full brief command, first run: 4 failed, 14 passed (touch, a11y, contrast, motion; dev_ui timed out once).
- Full brief command, final run: 3 failed, 15 passed, 0 skipped.
- a11y guard alone: 4 passed.
- touch sweep: only `/stay-fees` `noCue` entries remain.

## Still failing (all stay fees, not fixed here)
- `test_0252_touch_sweep_browser.py::test_every_host_page_on_phone_ipad_and_desktop`: `/stay-fees` noCue (Karlín Loft, Vinohrady Studio). Owner: 0796.
- `test_host_button_contrast_browser.py::test_small_primary_buttons_on_stay_fees_meet_contrast`: stay-fees/1280. Owner: 0796.
- `test_motion_browser.py::test_pages_without_javascript_stay_still` (line 139): `/stay-fees` has no `details.ui-how`. Not a records page. Owner: 0796.

## Brief items
1. Touch outside: fixed.
2. Focus ring: invoices Download PDF (opacity) and housebook scroll div fixed. `input#filter-month` and `.stays-desk` were not failing.
3. Empty-state centring: not failing in the final run; not touched.
4. `data-sub-tabs` test: passing; the failing case in the brief no longer exists; not touched.
5. dev_ui catalog: passed in 2 of 3 runs (one timeout, not reproduced); not touched.
6. Motion: fails on `/stay-fees`, not a records page; not fixed.

## Screenshots (390 px, full page)
- `/tmp/claude-0/scratch-0814/shots/housebook-phone390.png`
- `/tmp/claude-0/scratch-0814/shots/invoices-phone390.png`

## Owner steps left
None for this brief. 0796 must clear the three stay-fees failures before the CI run is green.
