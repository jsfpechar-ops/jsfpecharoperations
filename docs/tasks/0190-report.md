# 0190 report

Status: blocked

## Files changed

- App/app/routes/admin.py: `_smart_lock_panel_context`, `/smart-locks` GET 303 redirect, `_smart_locks_url` to `/apartments#anchor`, `RESERVATION_PAGE_SIZE = 5`
- App/app/templating.py: lock tab and `smart_locks` tab branch removed
- App/app/templates/apartments.html: lock section include (below the property list)
- App/app/templates/_smart_locks_panel.html: new, moved from smart_locks.html
- App/app/templates/smart_locks.html: deleted
- App/tests/test_design_admin.py, test_smart_locks_page.py, test_host_properties_navigation.py, test_host_list_page_layout_browser.py, test_lock_navigation_browser.py: assertions updated
- docs/tasks/0190-door-lock-and-stays-page.md, docs/tasks/0190-report.md

## Command

`pytest test_smart_locks_page test_design_admin test_host_properties_navigation test_lock_navigation_browser test_archive_stays_on_page test_design_shell_browser test_design_properties test_host_list_page_layout_browser test_property_hub -q -rfs`
Last lines: `3 failed, 58 passed`. No skips.

## Acceptance (§7)

- [x] Lock tab gone; `/smart-locks` 303 to `/apartments#...`
- [x] Panel shown only when TTLock enabled
- [x] Page size 5; stays pagination tests pass
- [ ] Browser tests green (3 failing, see Deviations)
- [x] Screenshots written: /mnt/project-files/design-reset/checkpoint-4-shell-fixes/properties-doorlock-390.png and -1280.png

## Deviations

- Ran with no `-x` so all failures show at once.
- Failing: `test_lock_setup_flow_keeps_its_place` (`#smart-locks-how` not found; the browser world has an account, so the setup section is not rendered), `test_share_section_without_javascript_and_foreign_returns` (drives `/smart-locks?return_to=/apartments/N#smart-locks-share`, which now redirects to the property page without the share section), `test_list_pages_share_order_edges_and_rhythm` (invoices and fees tab strips; not touched here, not verified on base).
- Did not change `test_host_ux_acceptance.py` or `test_host_wide_geometry_browser.py` (they still list `/smart-locks`; not in the test-map row).
- Other executor's files (host2.css, tokens.css, base.html, static_versions.json) left alone.

## Questions

- Should property-return flows (`/smart-locks?return_to=/apartments/N#...`) keep the lock section on the property page?

## Owner steps left

- Review the three failing browser tests; decide whether the property-return flow needs the share section on the property page.
