# 0795 report: old tests for the v2 Odeslání, Faktury, Domovní kniha pages

Status: blocked
Done: steps 1 and 2 for the failures that are in scope (assertion updates only, no template changed). Step 3: worktree removed. Left: 9 failures listed below.

## Step 1: pre-existing check

- origin/main worktree (`/tmp/wt0795`, now removed): the same 11 files give 20 failures, all `test_endtoend.py::test_04..test_28`. Those are pre-existing.
- This branch, `test_endtoend.py` alone: `28 passed in 3.78s`. The earlier endtoend failures were a cascade from the batch run, not from this branch.

## Step 2: fixed assertions (no template or CSS changed)

- test_design_reports.py::test_reports_and_housebook_have_the_v2_header_and_tabs: housebook joins submissions in the "no tab strip" branch.
- test_design_reports.py::test_the_house_book_keeps_its_filter_and_export_hooks: `class="filters ui-section host-filter-panel"` -> `... host-filter-panel card"`.
- test_design_reports.py::test_no_raw_style_or_legacy_control_in_the_three_templates: housebook exempt from the btn/pill check (v2 head buttons and pills).
- test_wp25_reported_bugs.py::test_housebook_truncates_the_property_with_a_tooltip: `table-cards housebook-table` -> `housebook-table`; `panel tight scroll-x housebook-scroll` -> `card stays-desk housebook-scroll`.
- test_shell_lane_browser.py PAGES: `/invoices` removed (v2 shell, covered by 0709/0710).
- test_host_wide_geometry_browser.py: `invoices` and `submissions` selectors -> `.stays-desk, .stays-phone, .ui-empty`; invoices, submissions, housebook added to the v2 "no alert stack" list.
- test_host_copy_corrections.py (housebook lane, about line 424): `main.wrap` -> `#main-content`.
- test_design_shell_browser.py::test_invoice_settings_tab_switch_does_not_move_the_page: `.ui-tabs a` -> `.stays-head-actions a` (head button).
- test_host_list_page_layout_browser.py: submissions, housebook, invoices removed from the tab-case list; invoices link regex -> `<a class="[^"]*" href="/entities"`; invoices skipped in the rhythm test (v2, 0532 rule); invoices row selector `.lc-invoices` -> `.stays-desk`.

Now passing: test_design_reports.py (all), test_wp25_reported_bugs.py, test_shell_lane_browser.py (4 params), test_host_copy_corrections.py, test_host_controls_browser.py assertions before the PDF-button check.

## Still failing (9 tests)

1. test_design_shell_browser.py::test_collapsed_rail_expands_again_with_the_same_button and ::test_collapsed_account_menu_is_whole_inside_the_viewport: v2 pages include `_shell_v2.html`, which has no `button[data-sidebar-collapse]` (only `_shell_sidebar.html` has it). Shell decision, not fixed.
2. test_host_filter_panels_browser.py (2 tests): `/invoices` month control is still the old markup (dashed border, trigger 73 px vs wrapper 216 px at 360 px). Needs template or CSS work. Not started.
3. test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls: housebook PDF dialog buttons are 78.5 px and 98.3 px wide, must be equal. Needs a rule in the 0792 block of app2.css. Not started.
4. test_host_wide_geometry_browser.py::test_host_wide_lanes_align (`fees-unset`), test_host_geometry.py::test_the_month_filter_shares_its_page_edges, and the `fees` entries of test_host_list_page_layout_browser.py (rhythm, tabs, rows): all on `/stay-fees`, which is 0794's page. Not touched.

## Not committed

Nothing committed or pushed (the owner's instruction for this run overrides the brief's per-step commits). No PR opened. `git status` also shows changes by other runs (stay_fees.html, app2.css, test_fee_setup_compatibility.py, v2_mockup.py); I did not touch them.

## Owner or orchestrator questions

- Should the v2 shell have the rail collapse button? Items 1 above depend on the answer.

## Owner steps left

None.
