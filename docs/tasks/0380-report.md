# 0380 report

Status: review

## Files changed
- App/app/templates/reservation_detail.html: menu item removed; "Unlink this e-mail" button (data-release-claim) and help tip added in the Guests claim line; data-stay-claim on the claim line.
- App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/guide_i18n.py: copy per §2, plus stay.claim.release_help.
- App/tests/test_remove_legacy_actions.py: line 32 per §4 step 3.
- App/tests/test_flash_next_step.py: lines 229-230 only, approved addendum (new flash copy).
- App/tests/test_0380_unlink_email_browser.py: new.
- docs/tasks/screenshots-0380/: 15 PNGs (en/cs/vi x 390, 1280, 1280 collapsed, 2000, 2000 collapsed).

## Command and last lines
- §6 run: 39 passed in 64.27s (0 skipped)
- design_lint: OK

## Deviations
- Commit is a single commit (amended after the addendum). Not pushed.

## Questions
- None.

## Owner steps left
- Open the PR and merge with scripts/merge-pr-on-green.sh once CI is green.

## Addendum A
- Applied brief §10: "?" kept beside Unlink at 390 px (CSS for .stay-claim-line, base.html key 20261025-0380, static_versions.json regenerated). Screenshots re-shot; §6 39 passed, 0 skipped; design_lint OK.
