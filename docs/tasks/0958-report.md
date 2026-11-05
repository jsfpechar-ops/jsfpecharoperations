# 0958 report (continuation: 0958-cont-1)

Status: blocked. Blocking defect at 768-1023 px (approved patch regression); host group has 5 pre-existing failures.
Branch: codex/0958-calendar-type-state | Base: 7b0355c | Head: see git log (steps 1-3 + report)
Environment: Python 3.12.3, requirements.lock + requirements-dev.txt, playwright 1.63.0 (CI pin).

## Escape decision: test was wrong
Probe (temporary, deleted): before Escape the create dialog is open; after Escape it is closed; `cancel` fires with defaultPrevented=false, then `close`. The app is correct. The test checked `is_hidden()` immediately after the keypress, before the close was processed. Fix (test only, step 3): `dialog.wait_for(state="hidden")`.

## Commands (last lines, pass/fail/skip)
- 0958 regression (`-k 0958`): 12 passed, 0 failed, 0 skipped.
- Calendar group, `--deselect tests/test_feed_dns_pinning.py`: 206 passed, 0 failed, 0 skipped (9 deselected, see below).
- test_feed_dns_pinning.py alone: 8 passed, 1 failed (IPv6 unsupported in sandbox; base-independent).
- test_host_fee_navigation.py::test_frozen_report_order_and_forms: FAILED on base and branch ("Your records" missing). Pre-existing.
- Host + design-guardrails + layout-lint + 0710 group (no -x): 5 failed, 419 passed, 0 skipped. Failures: fee-navigation (above) and 4 in test_host_ux_acceptance.py (door_codes editor; help-tip past right edge at 390; two focus-ring checks). The same 4 fail on base. Layout lint passed (no findings reported by the test).
- context_lint.py: OK (existing warnings only).
- git diff --check: clean.

## Acceptance
- Met: 12 0958 cases pass, 0 skipped; Escape cancels; only allowlisted files changed (App CSS, template, two tests, manifest, docs/tasks).
- Not met: host group has 5 failures (pre-existing on base; not caused by 0958); status therefore blocked.

## Screenshots (own reading, thumbnail scale; no contrast claim)
- 390: Dashboard and Cleaning, Stay and Cleaning states, EN and CS. The selected type shows a coral outline; the inactive type is plain. Layout is intact.
- 1280: Stay selected for Dashboard and Cleaning. Selected pill outlined in coral; inactive Cleaning plain.
- 768: Stay selected with a pale pink fill and faint label at this scale; needs a full-resolution check before approval.
- Layout-lint 390/768/1280 Dashboard and Cleaning: no visible overflow at thumbnail scale.
- Screenshots (not in repo): /tmp/ubyhost-0958/calendar-0958-*.png, sheet-0958-{390,768,1280}.png, sheet-lint-{390,768,1280}.png.

## Deviations
- Calendar group deselect removed all 9 feed-DNS tests, not only the IPv6 one; the file was then rerun alone (8 passed).
- Screenshot matrix covers Stay at 768/1280 only; Cleaning type is saved at 390 only (test design).

## Done / Left
- Done: steps 1-3 and this report.
- Left: 768 full-resolution check; separate brief for the 5 pre-existing host failures. G01, C04, C05, C06 and the rest of B02 remain queued. No claim that the UX plan is complete.

## Owner actions
- Decide whether the 5 pre-existing host failures are a separate fix or a rebaseline.
- Push when accepted: `git push origin codex/0958-calendar-type-state` (already pushed up to step 2; push new commits).

## Blocking defect: labels invisible at 768 px (measured)
Probe (temporary, deleted), dashboard Stay at 768 px:
- Inactive Cleaning: color rgb(255,255,255) on background rgb(255,255,255). Label invisible.
- Selected Stay: color rgb(255,255,255) on rgb(249,233,231). Contrast about 1.1:1.
- Cause: `body.v2 .btn:not(.line):not(.soft):not(.ghost)` (max-width 1023px, specificity about 0,5,1) sets white text. The approved `.cal-create-types .btn[aria-pressed]` rules are 0,3,0, so they lose.
- On base the inactive pill was a coral button with white text (readable). The approved patch made it white-on-white at this width.
- The selected-state colour loss also exists on base, but the approved patch has made the inactive state worse.
- 390 px (phone rule wins) and 1280 px (v2 rule does not apply) are not affected by this cause.

Proposed fix, NOT applied (needs owner approval as a second patch):
  `body.v2 .cal-create-types .btn:not(.line):not(.soft):not(.ghost)[aria-pressed="false"] { color:var(--ink); }`
  plus the matching `[aria-pressed="true"]` line, then re-run the 12 regression cases and add a 768 and 1024 colour assertion.
Alternative: add class `line` to the two type buttons in the template (touches markup; not in the brief).

## Owner decision needed
- Approve the second CSS rule (or the template class alternative). Then the rest of the brief can be finished in one pass.
