# 0157 report

Status: blocked (one pre-existing test failure, see Deviations)

Files: design_guard.js, test_design_guardrails_browser.py, host2.css, base.html, static_versions.json, reservations.html, _property_overview.html, guest_form_admin.html.

- Guard: 1 failed, only finding: `cleaning 390 open: button-heights-differ 'Property instructions & codes' 61 vs 'Share schedule' 44` (0143 owns it).
- static versions: 2 passed. design lint: OK.
- test_design_ui_macros + test_host_properties_navigation: 13 passed, 1 failed (test_properties_page_fits_every_width_and_both_languages: `len(fit["opens"]) == 3`, got 0 at 360 en). Fails identically with my changes stashed (pre-existing).
- test_host_wide_geometry_browser + test_host_list_cards_browser: 7 passed.
- test_stay_list_v2.py does not exist (skipped).

Deviations: the properties-navigation failure is unrelated to this brief (selector `.properties-table .row-actions > a.btn` finds no rows).
