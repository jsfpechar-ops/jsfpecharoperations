# 0964 report

Status: review

## Files changed
- App/app/templates/reservation_detail.html: weekday wrapped in `<span class="wd">` (2 lines)
- App/app/static/app2.css: `@media (max-width:359px)` block (equal columns, 12 px cell padding, weekday visually hidden)
- App/app/templates/base.html: app2.css cache-buster `20261106-0964`
- App/tests/static_versions.json: regenerated (app2.css only)
- App/tests/v2_mockup.py: 320 px widths re-pinned 73.8906px -> 94px (2 lines), one comment line added
- docs/tasks/0964-stay-dates-narrow-wrap.md: Status line
- docs/tasks/screenshots-0964/: stay-320/390/768/1280.png

## Commands (last lines)
- `test_0710_v2_mockup_match_browser.py -k stay`: `42 passed, 141 deselected in 45.83s` (0 skipped)
- `test_layout_lint_browser.py`: `4 passed in 206.74s` (0 skipped)
- `test_host_stay_detail_layout_browser.py test_host_stay_actions_browser.py test_0766_phone_stays_browser.py`: `5 passed in 32.86s` (0 skipped)
- `test_static_versions.py test_overhaul.py`: `29 passed in 1.96s`
- `scripts/context_lint.py`: `context lint: OK` (WARN lines are informational)

## Measured (scratch test, deleted)
- 320 px: `.stay-dates b` 94x28, small 94x18, scrollW 320. W320 = 94 px.
- 390 px: b 113x28 (unchanged), scrollW 390.
- 768 px: b 302x28, scrollW 768.
- 1280 px: stay-dates card 0x0 (desktop layout hides the card).

## Screenshots (per width)
- 320: "7. 11." and "9. 11." each on one line, no weekday, no sideways scroll, text inside card.
- 390: "Sat 7. 11." and "Mon 9. 11." on one line each, as before.
- 768: two-column card, dates on one line, unchanged.
- 1280: desktop layout, stay-dates card not shown; unchanged.

## Design-system checklist (section 7)
- Ticked: test_0710 stay 0 skipped; layout lint green 0 skipped; stay detail tests green.

## Deviations
- Worst-case step: the scratch JS set the weekday span, but the CSS hides it at 320 px, so the "worst" run measures "28. 12." (65 px), not visible "Wed 28. 12.". Real-data 320 px result is unaffected; accepted residual cases (year shown, 360-389 px) not measured.
- Re-pin comment: added a new `# 0964:` comment line above the 320 px b override instead of editing the 0957 comment line.
- Scratch screenshots went to /tmp/shots0964 as the brief says.
- Base commit in brief is a2fa3a8; branch HEAD was abb33fc, which the diff stat uses.

## Questions
- None.

## Owner steps left
- Merge PR #791 with `scripts/merge-pr-on-green.sh` once CI is green.
