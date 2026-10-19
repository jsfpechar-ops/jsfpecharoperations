# 0149-fix-2 report

Status: review

## Files changed
- App/app/validation.py: fmt_date_short (step 1)
- App/tests/test_validation.py: test_fmt_date_short_prints_the_year_only_when_it_is_not_the_current_one (step 1)
- App/app/templating.py: date_short filter (step 2)
- App/app/templates/reservations.html: date link uses date_short (step 2)
- App/tests/test_overhaul.py: _stay_dates reads aria-label (step 2)
- docs/tasks/0149-report.md

## Commands (last lines)
- Step 1, pytest tests/test_validation.py: "31 passed, 2 warnings in 0.50s"
- Step 2, pytest test_overhaul, test_design_stays, test_validation: "60 passed, 2 warnings in 2.74s"
- Step 2, design_lint.py: "design lint: OK"
- Step 3, browser run (5 files, -rs): "1 failed, 10 passed, 1 warning in 91.48s". The failure is test_host_list_page_layout_browser.py:155 (properties [40, 42]), the known local failure. 0 skipped.
- Step 3, capture share_compact_row_menu: "1 passed, 1 deselected, 1 warning in 21.36s"
- Step 3, md5 working copy stays-1280-cs.png: 8f830e13ec51b69e8a71657b174c73be; HEAD: 7e24d972ff235025582bdde5168013cf (differ)
- Step 3, docs/tasks/0079-evidence restored with git checkout; status clean
- Step 4, ruff --select E9,F63,F7,F82,F401,F841: All checks passed!

## By eye (screenshots in /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0149)
- stays-1280-cs.png: plain header row, no inner boxes, dates on one line in the form "20. 10. – 22. 10." with "2 noci" under; stay label and source each on one line; badge with deadline badge under it; Send (secondary) and ⋯ side by side at the right; rows about 54 px. Vinohrady Studio (demo) wraps to 2 lines in Stay and Property (expected for the 23-character demo row). Open and Copy are not in the row.
- stays-390-cs.png: one white card per stay; status badge at right; short dates with "2 noci"; property line with guests count; ⋯ top right; full-width "Odeslat tento pobyt" only on ready stays. Deviation: the source line sits under the stay label, not after it on the same line. Long names ("Scheduled Flat", "Vinohrady Studio (demo)") wrap.
- dashboard-1280-cs.png: table rows about 48 px, ⋯ (40 px) at the right. Matches.
- dashboard-390-cs.png: card line 1 dates with the task badge at right, line 2 property, line 3 guests, ⋯ top right. Deviation: the dates wrap to 2 lines in bold, and "do ..." sits on its own line.

## Deviations
- None to the commands. Step 3 browser run has the one allowed failure (page_layout:155).

## Questions
- None.

## Owner steps left
- None for this brief. Review and merge via scripts/merge-pr-on-green.sh.
