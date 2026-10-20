# 0165 report

Status: review

## Changed
- `App/app/templating.py`: Properties shows the lock tab whenever `ttlock.enabled()`; Invoices tabs add Stay fees between Invoices and Invoice settings; `/stay-fees` marks that tab current.
- `App/app/templates/stay_fees.html`: section tabs added; stale "no sub-page tabs" comment removed.
- `App/app/templates/_shell_sidebar.html`: six links; Invoices active on `invoices` or `stay_fees`.
- `App/app/templates/_shell_tabbar.html`: More sheet loses Stay fees and Smart locks.
- Tests (old-navigation assertions only): `test_design_shell.py`, `test_host_ux_acceptance.py` (one rail set entry), `test_stay_fee_list.py` (sidebar test), `test_host_list_page_layout_browser.py` (/stay-fees now has tabs).

## Results
- Template compile: all compiled. Design lint: OK.
- Browser step 7: 26 passed, 4 failed, 0 skipped. Failures: `test_list_pages_share_order_edges_and_rhythm` (known on main), `test_three_views_four_groups_one_editor_and_unique_ids` and `test_create_offers_the_calendar_first_and_works_without_js` (fail on base too), and `test_tabs_are_links_that_mark_the_open_page` (now passes).
- `test_page_families_through_rail_cards_search_and_back` and `test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus` fail on base too.
- 0102-evidence cleanup ran; no-op (tree clean).

## Owner steps left
- Nothing for deploy. Merge via `scripts/merge-pr-on-green.sh` when the owner decides on the pre-existing failures.
