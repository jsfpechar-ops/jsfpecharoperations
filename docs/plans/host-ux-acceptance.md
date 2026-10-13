# Host UX acceptance matrix (task 0084)

Candidate C = `cc4e8d9a8f667bc6b60d3a108dd93dce4bd3c330` (branch `claude/quirky-lamport-9svmd1`, combined lane 0087–0095 + 0075–0083), plus the 0084 commit on top. Main P = `ab0a2f1e43d3162b425cdd23402925536aa59548`. Report: [0084-report](../tasks/0084-report.md). Brief: [0084](../tasks/0084-host-navigation-integration-acceptance.md).

Environment for every row: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0`, pinned Chromium 1194, synthetic data, no live provider (UbyPort mock, feed sync not called, TTLock not called, console mail). "New" = `App/tests/test_host_ux_acceptance.py`. Result column = this run on C + 0084.

## 1. Ownership (counted on rendered pages, not template branches)

The ownership tests render all 26 page families in §3 for one host with 3 properties (one archived), 2 businesses, a feed, a lock account, a stay with a guest, an issued invoice and a report.

| Fact | Test | Result |
|---|---|---|
| No duplicate `id`, no nested form, no two POST editor forms with the same action and field set (desktop/mobile clone) on any page, EN and CS | New `test_every_host_page_has_unique_ids_no_nested_and_no_cloned_editor_forms[en,cs]` | pass |
| Each of the 43 editable property settings has exactly one control in the property document (all three views and four groups are in it); none is editable on any other page (create page may ask name/city/operator/address only) | New `test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host`; also `test_property_navigation_browser::test_three_views_four_groups_one_editor_and_unique_ids` (exact 47-name set of the one form) | pass |
| Guest-link, automation and fee fields: no copied editor (Properties summary read-only; fee list only links to Settings → Reporting & fees) | New `test_guest_link_automation_and_fee_have_no_copied_editor`; `test_host_properties_navigation::test_summary_is_visible_read_only_and_links_to_each_editor`; `test_fee_setup_compatibility::test_fee_editor_is_the_only_one_and_shows_the_council_block` | pass |
| One shared entity editor: one Business form, one Invoice-details form; each field once; no entity field editable elsewhere; issued invoice has no editor | New `test_one_shared_entity_editor_owns_business_and_invoice_fields`; `test_entity_editor_fields::test_each_shared_field_has_one_template_definition` | pass (invoice-details IČO is the lookup-only input from 0076 decision 1, still an owner decision) |
| One fee normaliser for both save paths | `test_fee_setup_compatibility::test_property_save_and_legacy_post_store_identical_fee_values` | pass |

## 2. Behaviour matrix (execution protocol §6)

| Row | Test(s) | Result |
|---|---|---|
| One / many / no properties: `/guest-links`, `/automation`, Search | `test_property_hub::test_guest_links_redirects_to_communication_with_one_property`, `…_to_apartments_with_two`, `test_automation_redirects_*`; `test_host_properties_navigation::test_hub_redirects_for_none_one_and_many`; new `test_one_many_no_and_archived_properties_on_hubs_and_search` | pass |
| Archived property: excluded from hubs, Search and summary; listed with Restore; its page still opens | New `test_one_many_no_and_archived_properties_on_hubs_and_search`; `test_property_operator_defaults::test_saving_an_archived_property_keeps_it_inactive_and_archive_restore_work`; `test_host_properties_navigation::test_no_business_and_no_property_states_stay_distinct` | pass |
| Dirty settings: drafts survive Settings group switches and Back/Forward; a tab or link out of Settings asks Save / Discard / Stay (Stay keeps the draft) | `test_property_navigation_browser::test_tabs_hashes_drafts_history_and_validation_in_browser`; `test_entity_editor_navigation::test_unsaved_business_draft_asks_before_saving_invoice_details`; `test_host_unsaved_changes_browser` | pass: in-app Save / Discard / Stay dialog and save-bar Discard (O1 fixed); native prompt kept for close/reload/external |
| Save includes earlier-section changes; unrelated save keeps every stored value | `test_property_navigation_browser::test_unrelated_save_keeps_every_stored_value`, `…test_tabs_hashes_drafts_history_and_validation_in_browser` | pass |
| Hidden invalid control is revealed and focused before browser validation; server refusals keep the draft in its view | `test_tabs_hashes_drafts_history_and_validation_in_browser` (PIN in hidden group); `test_property_navigation_browser::test_refused_save_and_refused_calendar_render_their_own_view`; `test_calendar_platform_required::test_an_unsafe_link_is_refused_with_the_draft_kept` | pass |
| Old `#hashes` (10 anchors) reveal their view/group, JS and no-JS | `test_tabs_hashes_drafts_history_and_validation_in_browser`; new `test_without_javascript_tabs_reload_and_the_shared_editors_save` (`#ubyport` no-JS) | pass |
| Legacy GET adapters: `/guest-links`, `/automation`, `/invoices/settings[?entity]`, `/stay-fees/{id}/setup[?month]`, `/setup*` | New `test_legacy_adapters_land_on_the_canonical_homes`; `test_entity_editor_navigation::test_legacy_get_*`; `test_fee_setup_compatibility::test_legacy_setup_url_lands_on_the_one_fee_editor_with_the_way_back`, `…test_legacy_setup_keeps_its_guards`; `test_setup_wizard::test_legacy_setup_pages_redirect_to_their_canonical_home` | pass |
| Legacy POST adapters run the canonical save/rerender (no value-dropping redirect) | New `test_legacy_adapters_land_on_the_canonical_homes` (422/400 rerender with typed values, nothing written); `test_entity_editor_navigation::test_legacy_post_saves_through_the_same_implementation`, `…test_legacy_post_refuses_a_foreign_entity_without_saving`; `test_fee_setup_compatibility::test_legacy_post_is_fee_only_and_leaves_every_other_field`; `test_setup_wizard::test_legacy_bookings_post_returns_to_the_property_calendars` | pass |
| Report month / context returns; unsafe returns dropped | `test_fee_setup_compatibility::test_save_returns_to_the_exact_report_period`, `…test_rate_zero_returns_to_the_list_of_the_same_month`, `…test_unsafe_or_foreign_return_is_dropped`, `…test_report_fix_links_open_the_fee_editor_and_payer_editor`; `test_entity_editor_navigation::test_editor_keeps_a_safe_return_path_only`, `…test_business_save_returns_to_the_opening_context`; `test_smart_locks_page::test_found_locks_return_to_the_hosts_own_property_lock_section` | pass |
| Shared entity + immutable issued invoice | `test_entity_editor_navigation::test_shared_business_change_reaches_both_properties_but_not_issued_invoices`; `test_entity_editor_fields::test_saving_details_never_changes_an_issued_invoice`; new `test_issued_invoice_snapshot_survives_a_shared_business_edit` | pass |
| Rate / IBAN-only / omitted / blank / invalid values | `test_fee_setup_compatibility::test_iban_only_account_survives_an_unrelated_fee_save_on_both_paths`, `…test_blank_account_clears_on_both_paths`, `…test_invalid_account_saves_nothing_and_keeps_what_was_typed`; `test_entity_editor_fields::test_absent_fields_keep_and_blank_fields_clear`, `…test_empty_account_parts_keep_an_iban_only_account`, `…test_an_invalid_account_keeps_the_stored_value_and_every_typed_value`; `test_stay_fee_property_panel` (file) | pass |
| Valid / unavailable invitation (guest) links | `test_guest_slugs::test_the_current_slug_opens_the_same_picker`, `…test_an_archived_property_is_not_found_by_slug_either`, `…test_a_wrong_code_is_not_found`, `…test_a_new_link_retires_every_slug`; `test_overhaul::test_guest_unavailable_states_are_distinct`; `test_guest_unavailable_actions` (file); host invitations: `test_account_emails::test_the_invitation_secret_is_never_shown_redirected_or_stored_in_clear` | pass |
| Expected-slot safeguards | `test_host_redesign::test_remove_empty_slot_only_changes_expected_count_and_rejects_replay`, `…test_remove_slot_rejects_actual_guest_and_inactive_stays`, `…test_remove_slot_requires_login_and_csrf`, `…test_remove_slot_refuses_another_owner_and_newly_registered_guest`; `test_overhaul::test_stay_settings_preserve_expected_guests_edited_above`; `test_guest_navigation::test_an_unexpected_extra_guest_can_still_register` | pass |
| Role-aware account navigation | `test_host_account_navigation::test_ordinary_user_sees_no_admin_controls`, `…test_admin_sees_team_and_incidents_in_account_group`, `…test_search_reaches_settings_groups_and_help` | pass |
| Shared-lock navigation (account vs property assignment) | `test_host_properties_navigation::test_lock_account_link_only_when_connected`; new `test_one_many_no_and_archived_properties_on_hubs_and_search` (Search lock entry only when connected); `test_smart_locks_page::test_each_host_has_their_own_name_and_never_sees_anothers_locks`, `…test_an_admin_key_shows_the_lock_as_connected`, `…test_a_plain_key_is_called_out_not_ignored`; `test_lock_navigation_browser::test_lock_setup_flow_keeps_its_place` | pass |
| Operator required, zero/one/many operators | `test_property_operator_defaults` (file), `test_property_create_browser` (file) | pass |
| Calendar platform + URL required | `test_calendar_platform_required` (file) | pass |

## 3. Page families, navigation, locales, input modes

Families (26): Dashboard, Stays, Stay detail, Properties, Property Overview / Bookings & calendars / Settings → Property information / Guest experience / Reporting & fees / Automation, archived property, Add property, Businesses list, Business editor, Invoices, Invoice builder, Invoice detail, Stay fees, Fee report, Reports, Report detail, House book (register), Account settings, Archive, Door lock account, Guide.

| Check | Test | Result |
|---|---|---|
| Every family renders 200 in EN and CS | New ownership tests (`_pages`) and geometry sweep | pass |
| Normal links: rail → Properties → Open → tabs → business card → entity editor → Back; Search → Stay fees → report → Back; rail → Invoices → invoice → its stay → Back; Settings, Archive, Guide, House book, Reports reachable; EN and CS | New `test_page_families_through_rail_cards_search_and_back` | pass |
| Keyboard: skip link first; rail, local tabs, section nav, `?` tips, fields and Save reachable by Tab, each with a visible focus ring and in view; Search opens with Enter, Escape returns focus | New `test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus` (CS); `test_host_help_browser` (file) | pass |
| JavaScript off: tab links reload with `?view=`, old hash shows its group, property save, Business details save, Invoice details save, login form posts with its own CSRF field | New `test_without_javascript_tabs_reload_and_the_shared_editors_save`; `test_property_navigation_browser::test_create_offers_the_calendar_first_and_works_without_js`; `test_property_create_browser::test_create_page_works_without_javascript`; `test_auth_forms_no_js` (file); `test_lock_navigation_browser::test_share_section_without_javascript_and_foreign_returns` | pass after fix D1 |
| Copy / save / error feedback | `test_host_feedback_browser`, `test_fee_setup_compatibility::test_invalid_account_saves_nothing_and_keeps_what_was_typed`, `test_entity_editor_navigation::test_canonical_post_rerenders_422_with_typed_values_on_the_editor` | pass |
| Long names (property 78 chars with diacritics, business 62 chars) | Fixture of every new browser test | pass |

## 4. Width × rail × locale geometry sweep

New `test_every_page_family_fits_every_width_language_and_rail_state`: 26 families × EN/CS × widths 360/390/760/1024/1280/1440/1680/1920/2048 with the rail expanded (drawer below 961 px), plus collapsed rail at 1024–2048. 780 page renders, 25,951 visible controls checked. Assertions: `scrollWidth <= viewport`; every visible link/button/field/summary/switch inside the viewport and not cut by an `overflow:hidden/clip` ancestor; controls inside an intentional sideways scroller are counted separately. Measurements: `docs/tasks/0084-evidence/measurements.json`.

| Result | Detail |
|---|---|
| Before fixes | 3 failures: Guide at 360 EN/CS (`scrollWidth` 380: the UbyPort URL in the manual-filing step), Stay fees at 760 CS (773: sr-only actions header escaping the scrolling panel) |
| After D2/D3 | 0 failures, 0 skipped |
| Controls inside an in-panel sideways table scroll | House book at 760/1024 (intentional register). Properties, Businesses, Invoices, Stay fees and Reports no longer scroll: cards under a per-list 800-950 px panel, tables at 1280+ (O2 fixed, `test_host_list_cards_browser.py`) |

Existing width suites that also pass on this head: `test_host_wide_geometry_browser`, `test_host_fit_browser`, `test_host_list_layouts_browser`, `test_property_navigation_browser::test_property_views_fit_every_width_and_sidebar`, `test_entity_editor_navigation::test_editor_fits_every_width_and_both_languages`, `test_host_properties_navigation::test_properties_page_fits_every_width_and_both_languages`, `test_host_fee_navigation::test_fee_pages_fit_and_keep_one_lane`, `test_host_account_navigation::test_settings_geometry_and_help_at_widths`.

## 5. Screenshots

`UBYHOST_CAPTURE_0084=1` → `docs/tasks/0084-evidence/<family>-<360|390|1280>-<en|cs>.jpg` for 16 families (dashboard, stays, stay-detail, properties, property-overview, property-bookings, property-guests, property-reporting, property-new, business-editor, invoices, invoice-detail, fees, fee-report, settings, smart-locks), full page, rail expanded, synthetic data only. Full-page captures show the fixed rail only for the first viewport height; the live page is unaffected.

## 6. Defects

| Id | Defect | Status |
|---|---|---|
| D1 | Business details and Add business forms on `/entities` had no `_csrf` field: without JavaScript the canonical business save returned "This form expired" (the sibling Invoice details form had one) | fixed: hidden `_csrf` in both forms (`entities.html`); test `test_without_javascript_tabs_reload_and_the_shared_editors_save` |
| D2 | Guide page wider than the viewport at 360 px (long URL) | fixed: `overflow-wrap:anywhere` on guide steps (`host.css` 0084 block); sweep test |
| D3 | Stay fees list widened the page at 760 px CS (sr-only header outside its scroll panel) | fixed: `.panel.fee-periods { position: relative }` (same pattern as the house book); sweep test |
| — | `host.css` cache key bumped to `20261013-0084` in `base.html` so staging browsers fetch the fixes | done |
| O1 | No Save / Discard / Stay dialog for dirty property settings and no Discard control; only the browser's Leave/Stay prompt (plan maintainability §5) | fixed: native `<dialog>` (Stay/Esc keeps edits and focus, Discard resets and follows the link, Save submits to return_to) for `data-unsaved-guard` forms, save-bar "Discard changes"; Settings sub-nav and links into Settings keep the draft without asking; also stops skeleton.js blanking the page after an in-page property tab click. Test `test_host_unsaved_changes_browser.py`, evidence `docs/tasks/0084-evidence/o1-*.png` |
| O2 | List tables (Properties, Businesses, Invoices, Fees, Reports) scroll sideways inside their panel at 760–1024 px instead of wrapping actions or becoming cards (combined plan §4 rule 9 names Stays only) | fixed: container-query cards under a per-list 800-950 px panel, no inner scroll; `tests/test_host_list_cards_browser.py` |
| O3 | Host POST forms outside property/calendar/create/entity/invoice-details/auth still rely on `csrf.js` (account settings, archive/restore row menus, smart-lock forms): not usable with JavaScript off. Pre-existing, outside rule 6 (auth forms only) | open: note only |
