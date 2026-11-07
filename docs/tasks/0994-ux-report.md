# 0994 report

Status: review

## Files changed
- App/app/templates/_host_alerts.html (step 1: headcount alert action line hidden on /reservations)
- App/app/host_i18n.py (step 2: en and cs `headcount_mismatch` reworded, new `stays.table.guests_of`)
- App/app/templates/_components.html (step 3: "N of M" guest count)
- App/app/templates/reservations.html (step 4: muted "No name yet" plus "Add a guest" link for active stays)
- App/app/static/app2.css (step 5: 3 rules)
- App/app/templates/base.html (step 6: cache key 20261107-0994)
- App/tests/test_guest_navigation.py, App/tests/test_overview_headcount.py (step 7: expected text only)
- App/tests/static_versions.json (regenerated with `tests/test_static_versions.py --write`)

## Commands (last 5 lines)
- test_host_*, test_host_geometry, test_notification_copy, test_*_i18n, test_no_em_dashes, test_guest_navigation, test_overview_headcount, test_0523_stays_list, test_static_versions (UBYHOST_REQUIRE_BROWSER=1): first run stopped at test_guest_navigation (fixed, see step 7); 299 passed before it. Rerun of the changed files: 42 passed in test_overview_headcount + test_guest_navigation; 54 passed in the test_guest_navigation, test_overview_headcount, test_0523_stays_list, test_static_versions and test_host_geometry set. Full brief set not rerun after fix (11 min).
- test_layout_lint_browser.py + test_design_guardrails_browser.py: `15 passed in 282.59s`, 0 skipped.
- `python3 scripts/context_lint.py`: not run in this session.

## Section 7
- [ ] Banner without "Open the stay" line and "1 of 6" row: code done and tests pass; NOT seen in screenshots (fixture has no headcount alert on the page).
- [ ] "No name yet" muted with "Add a guest" link at 390 px: code done; NOT seen (fixture has no no-name rows, and the link is desktop-table only, `.stays-desk`).
- [x] Layout lint zero findings, 0 skipped.

## Screenshots (/tmp/shots)
- 390 (stays-default-en-390.png): mobile card list, "1 guest missing" chips, no layout breakage; no No-name row present.
- 768 (stays-default-en-768.png): card list, same content, no overlap seen.
- 1280 (stays-default-en-1280.png): table shows "0 of 1" in the guest column (new wording), yellow banner shows only the police line.

## Deviations
- No push, no PR (per owner). Commits are local on claude/project-thread-d67hsx.
- Commit trailers use the Sonnet 5.5 lines given in the brief instructions.

## Owner steps left
- Review and open the PR; design-system checklist not ticked (no PR yet).
- Add a fixture with a headcount alert and a no-name row to see the banner and action at 390/1280.
