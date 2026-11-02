# 0894 report (Haiku executor)

Status: blocked
Base: 41e86bd3 (branch claude/project-thread-56y70c). Nothing committed or staged, per orchestrator (executor.md's per-step commit rule was not followed on purpose).

## Files
- `App/app/static/admin2-system.css`: created. Brief block, plus: heading `summary h2` (title with badge absolutely placed so the "?" sits on the title's last line), `p.ui-sub` 12 px top margin, `ul.admin-status` without bullets.
- `App/app/templates/admin_billing.html`: v2, both CSS links, page title "?", month/statement/movement sections under "?", `ui-sub` labels to `admin-label`. Deviation: the account counts line (`data-billing-admin-accounts`) is now a `ul.admin-status` with `li` items (same text, no "·" separators), because it was over 60 chars and read as fine print.
- `App/app/templates/admin_operations.html`: v2, both CSS links, page title "?", seven summary sections (filings, feeds, jobs, mail, ttlock, alerts, havel) and incidents review/draft under "?". Help `<p>` lines removed.
- `App/tests/test_0894_admin_airbnb_billing_ops_browser.py`: created (2 pages x 6 widths). Imports `GEOMETRY_JS`, `fine_print_and_gap_findings` and the fixtures from the 0893 test. Its own `shoot` writes `docs/tasks/screenshots-0894/0894-<page>-<width>.png`.
- `App/tests/static_versions.json`: regenerated (45 files).
- `docs/tasks/screenshots-0894/`: 4 files (billing and operations, 390 and 1280).

## Commands (last lines)
1. `test_0894_admin_airbnb_billing_ops_browser.py`: `12 passed`, 0 skipped.
2. `test_admin_operations.py tests/test_billing_admin.py ...` (with -x):
```
assert "Hlášení vyžadující pozornost" in czech
1 failed, 2 passed
FAILED tests/test_admin_operations.py::test_admin_sees_every_section_and_no_guest_identity
```
   Not run (stopped by -x): test_billing_admin, test_admin_funnel, test_admin_section_tabs, test_design_admin, test_static_versions.
   `test_0419_admin_billing_browser.py`: passed. `test_funnel_ads_geometry_browser.py::test_funnel_ads_export_geometry`: `buttons must be 40px tall like every ui-btn, got 37` (1 failed, 2 passed in that run).
3. screenshots: `4` files written (the -k run reported 1 failure which is the same funnel test set, see above).
4. `python3 scripts/context_lint.py`: `context lint: OK`.

## Acceptance (§7)
- [x] Command 1: passed at six widths, 0 skipped.
- [ ] Command 2: not passed (see above).
- [ ] Form/table/section counts before and after: NOT done.
- [x] 390 and 1280 screenshots in `docs/tasks/screenshots-0894/`. Not reviewed by eye (budget).
- [ ] Taps for "mark an invoice paid" and "export the month": NOT measured.

## Deviations
- Heading layout: the title `h2` is `display:block; position:relative`, and the badge is absolute at top right. Flex and inline layouts were tried first and put the badge on its own line, so the "?" was not on the last line.
- Account counts line changed to a list (see Files).

## Questions
- The Czech operations assertion (test_admin_operations.py line 103) probably breaks because the section title now goes through `tip_label`. Not verified.
- Funnel ads export button is 37 px, not 40 px. Cause not found: admin2.css and admin2-system.css do not style buttons. Check which rule changes the button line height on admin_billing.

## Owner steps left
1. Fix the two failures above (the executor stopped at its budget), then run the commands in §6 for 0894 and the rest of command 2.
2. Look at the four 0894 screenshots.
3. Taps: mark an invoice paid, export the month (measure on staging).
4. Commit and open the PR only after the above; nothing is committed now.
