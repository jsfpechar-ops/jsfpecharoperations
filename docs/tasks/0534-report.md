# 0534 report

## 0534a (steps 2-3)

Status: partial. Steps 2 and 3 done. Step 1 (template), 4, 5 and 6 left for a later session.

Commits (branch claude/project-thread-819gyo, not pushed):
- `2642185` 0534a step 2: section keys
- step 3 commit: 0534a step 3: v2 form controls and property page CSS

Step 2: `property_page.sec.{basics,police,messages,lock,fee,archive,calendars}.{title,sub}` added to en and cs in `App/app/host_i18n.py` (28 lines) and vi in `App/app/host_vi_i18n.py` (14 lines). No key removed.
- `tests/test_host_i18n.py`: 11 pass, 3 fail (`test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_accepts_vietnamese`: "no such table: apartment"). The same 3 fail on clean HEAD without my change, so they are not caused by 0534a.
- `tests/test_validation_i18n.py` and `tests/test_public_copy_i18n.py`: 12 pass.

Step 3: `App/app/static/app2.css`
- Shared block `/* v2 form controls (shared, generic) */` after the sr-only rule. Rules are wrapped in `:where()` so page rules still win. Without `:where()` the `width:100%` rule overrode the properties-list toolbar and caused horizontal scroll at 1024/1280/1440 (`properties` geometry failures). That was fixed and is now clean.
- `/* 0534 property page */` block at the end: `.form` (one column for now), `.crumb`, `.guest-card`, `details`, `summary`, `.fields`, `.savebar`, reduced-motion-only animation.
- Deviation: the brief's `ui-btn-quiet` mapping is set to the ghost look (`#efefeb`), the same as `ui-btn-secondary`.
- `base.html` app2 key: `20261101-0534b` (a first try at `0534a` was refused by `--write` because the key did not change). `App/tests/static_versions.json` regenerated with `--write`.
- `docs/design/catalog.json`: `form`, `crumb`, `fields`, `savebar`, `guest-card` added to `classes`. `guest-card` was already listed under `legacy`.

Test tails (from `App/`, env `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`):
- `tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py`: `3 failed, 33 passed in 43.91s`. The 3 failures are the known ones: overview-768, properties-768, menu-320.
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK`

Owner steps left: none for 0534a.

## 0534b (steps 1, 2, 4; step 5 partial; step 6 not in this session)

Status: blocked. Remaining work listed below needs an orchestrator decision.

Commits (branch claude/project-thread-819gyo, not pushed):
- `5d500e1` 0534 step 1: one-page property template (crumb, h1, guest card, details sections, savebar; tabs, views and settings groups removed). Setup card copied from `_property_overview.html`.
- `6891977` 0534 step 2: unused `property_nav.*` and `guest_guide.tab` keys removed (en, cs, vi).
- `0534 step 4` commit: `test_0534_property_page_v2.py` (7 tests), savebar media query (<=600 px), app2 key `20261101-0534c`, `static_versions.json`, catalog legacy classes for `apartment_form.html`, two `test_0531` assertions, the bookings open rule fix.

Test tails:
- `test_property_hub.py`: 10 passed.
- `test_host_i18n`, `test_validation_i18n`, `test_public_copy_i18n`, `test_property_hub`: 3 failed (the known `test_host_i18n` cookie/Vietnamese failures, "no such table: apartment", same on HEAD), 33 passed.
- `test_0534`, `test_0531`, `test_static_versions`, `test_no_dead_internal_links`: 26 passed.
- `test_0534`, `test_property_hub`, `test_static_versions`: 21 passed.
- `design_lint.py`: OK. `context_lint.py`: OK.

Section 8 changes (assertions only, no test deleted):
1. `tests/test_validation_i18n.py`: the two banner tests (Czech and English) now assert the readiness banner text is absent. The banner left the property page; 0535 moves it to the aside. Restore the positive asserts in 0535.
2. `tests/test_0531_property_page.py`: `class="property-guest-link"` changed to `class="card guest-card"`; the save-row regex changed to `<div class="savebar">`.

Remaining failures (not fixed):
- `tests/test_property_readiness.py`: 8 fail (checklist, invite list, reporting list, Czech copy, validation reason). They assert the readiness block that 0534 drops from this page. Decision: move them to 0535 or change them to absence now.
- `tests/test_host_ux_acceptance.py`: 4 fail. `test_without_javascript_tabs...`, `test_keyboard_reaches_rail_tabs...`, `test_page_families_through_rail...` click the removed `.property-tabs`; they need the one-page markup. `test_every_page_family_fits...` still reports 28 buttons past the right edge at 360 px on property-overview. `test_issued_invoice_snapshot...` (line 478) looks for the operator name from the removed overview; not re-run after the fixes.
- `test_0710` property entry: not added (step 5). `v2_mockup.PAGES` paths are concrete; there is no seeded-id placeholder. Needs a decision.
- Known, not ours: `test_0710` overview-768, properties-768, menu-320.

Deviations:
- DOM order is basics, archive, messages, police (ubyport + automation), fee, calendars, then lock and lock-account (door codes only). The brief order puts archive last; archive lives in the property group, so it comes second.
- Crumb and h1 use `apartment.internal_name`; `apartment.name` does not exist on the model.
- Open rules: `?section=reporting` opens police and fee; `?view=bookings` opens only calendars; no view opens basics only. `lock` open rule is not tested (fixture has no door codes); `#door-code` not checked.
- `_property_overview.html` is no longer included; kept on disk for 0535.
- `apartment_form` is v2 only when editing; the create page is unchanged.
- Kept `property_nav.report_missing.one/.few`, `lock_intro`, `setup_complete` (possible dynamic use).
- Catalog legacy list for `apartment_form.html` got `card`, `sub`, `actions`, `panel`, `setup-continue-card`, `property-setup-show`, `link-button`.

Owner steps left: none.

## 0535 (steps 0-1; steps 2-6 not started)

Status: blocked. Done: steps 0 and 1. Left: steps 2 to 6 (aside, phone overflow, tests, PAGES entry, screenshots).

Commits (branch claude/project-thread-819gyo, not pushed):
- `0c2aaee` 0535 step 0: box overrides for property cards
- `3332e41` 0535 step 1: section order CSS (`order` on each `#sec-*`), key bump
- `de98c78` 0535 step 1b: settings form wrapped in `<div class="form">` in `_property_editor.html` (the `.form` column did not exist, so step 1 had no effect until this)

Test tails (from `App/`, env `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`):
- step 0: `tests/test_0710_v2_mockup_match_browser.py -k properties`: `12 passed, 22 deselected`
- step 1: `tests/test_0534_property_page_v2.py tests/test_static_versions.py`: `11 passed`
- step 1b: `tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_static_versions.py tests/test_property_hub.py`: `25 passed`

Section 8: none (no assertion changed).

Deviations:
- Step 0: the 0719 phone mechanism is `BOX_OVERRIDES`, not `SELECTOR_OVERRIDES`; the keys added there are `.big, .head h1` and `.card.prop` (the brief's `.big, .head h1` is one phone_selectors string, which the alias map does not cover).
- Step 1: archive was already its own `details#sec-archive` (not inside basics), so no template change for it. Order is CSS only (`body.v2 .form` flex column, `.property-settings-form{display:contents}`); tab order still follows the DOM (calendars last-but-two), as the brief allows.
- Step 1b: the brief assumed a `.form` wrapper existed; it did not. Added `<div class="form">` around the settings form plus the calendars and lock-account sections in `_property_editor.html`.
- Step 1b: app2 key is `20261101-0535b`.

Owner steps left: none.
### 0535 steps 2-3 (executor report)

Status: blocked. Done: steps 2 and step 3 at 360 px. Left: step 3 at 1024 px (cs), steps 4 to 6.

Commits: `e31cee0` 0535 step 2: preview aside. `bffab0a` 0535 step 3: no sideways scroll (partial). This commit: test_copy_cleanup list and this report.

Tails:
- `tests/test_0534_property_page_v2.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_validation_i18n.py`: 37 passed, 0 skipped.
- `tests/test_host_ux_acceptance.py -k fits`: 1 failed. 360 px en failures are gone. 1024 px cs fails on property-overview, bookings, settings, guests, reporting, automation (scrollWidth 1036 > 1024). The offender list is empty, so the element is not identified yet.
- `tests/test_copy_cleanup.py`: 9 passed after the list fix.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed. design_lint: OK. context_lint: OK.

Section 8 (tests changed):
- `tests/test_validation_i18n.py`: the two readiness tests flipped from negative to positive asserts (`Bez IDUB nelze nic nahlásit.` in cs, `IDUB is required before anything can be reported.` in en).
- `tests/test_copy_cleanup.py` line 151: `_property_overview.html` removed from the file list (file deleted).

Deviations:
- The readiness block is shown whenever `readiness and not wizard_active`, as it was in the overview. Gating on "something missing" failed `test_a_complete_property_says_you_can_send_the_guest_link`.
- No "Co chybí" heading. The moved block keeps its summary text (`wizard.overview.details`). No new key for it.
- New i18n keys: `property_page.preview.title`, `property_page.preview.connections` (en, cs, vi). No keys deleted: each overview key is still used by another template or a test.
- `_property_overview.html` had no includes, so nothing rendered from it. Its setup card and host-property-grid went with the file.
- Step 3 CSS is in the 0534 block (not the shared v2 block): below 1024 px, details descendants `min-width:0`, `.ui-btn` wraps, flex rows in details wrap, `.fields` one column below 640 px.
- The 360 px failure was the calendar delete button (`ui-btn-danger` in `_property_calendars.html`).

Owner steps: none. Next executor: diagnose the 1024 px cs overflow (list elements with right edge over 1024, include the fixed `.savebar`), then steps 4 to 6.


### 0535 steps 3b-4 (executor report)

Status: blocked. Done: step 3b (1024 px fits), step 4. Left: step 5 (0710 `property` PAGES entry and placeholder), step 6 (screenshots), the design_lint run, and the 0710 run from brief §6.

Commits: `29fa01e` 0535 step 3b: fits at 1024. `715b7d4` 0535 step 4: property page tests on the one-page markup. This commit: this report section.

Step 3b cause: the probe (every element with right > 1024, cs, rail expanded) found only the injected `copy-state-icon` span and its svg inside the guest-card copy button (`body.v2 .guest-card .copy-btn`), about 77 px in flow. The `.form` grid and `.savebar` were not offenders. Fix: the icon is absolute and hidden until `.copied`, in the 0535 step 3 block of app2.css. Key bumped to `20261101-0535e`, manifest written.
- `tests/test_host_ux_acceptance.py -k fits`: 1 passed, 0 skipped (101 s).

Step 4 tails:
- `tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_property_readiness.py tests/test_validation_i18n.py tests/test_host_ux_acceptance.py tests/test_no_dead_internal_links.py tests/test_static_versions.py`: 70 passed, 0 skipped (112 s).
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed.
- `scripts/context_lint.py`: OK.
- design_lint: not run (out of calls).

Section 8 (tests changed):
- `tests/test_host_ux_acceptance.py` `test_page_families_through_rail_cards_search_and_back`: `.property-tabs` clicks replaced by `details#sec-basics[open]` and the `/entities?edit=` link in the operator block. The search trigger is `[data-command-open]:visible` (v2 shell `button.search`; `.ui-search-row` is the old sidebar).
- `test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus`: the `?view=overview|bookings|settings` loop replaced by `#sec-basics` and `#sec-lock` anchors in the tab-order set; `details#sec-lock[open]` asserted after the old `?view=settings&section=lock` link; search trigger selector as above.
- `test_without_javascript_tabs_reload_and_the_shared_editors_save`: tab click replaced by a `details#sec-basics[open]` assert (no JS needed).
- `test_issued_invoice_snapshot_survives_a_shared_business_edit` (operator name): asserts the selected `<option>` carries the entity name and the hint link is `/entities?edit=<id>` (no `next`).
- `tests/test_0534_property_page_v2.py`: added `test_css_order_is_the_mockup_order`, `test_rendered_sections_show_in_mockup_order`, `test_aside_has_cards_and_links_to_each_section`.

Deviations:
- The 1024 px cause was the guest-card copy icon, not the grid or savebar as the brief guessed.
- The DOM order test (`test_sections_are_details_in_order`) is unchanged: order is CSS only, so DOM order still lists archive second.
- The keyboard test's tab-order loop (60 tabs) still reached `#sec-basics` and `#sec-lock` in the aside.

Owner steps: none.
Next executor: step 5 (add `property` to PAGES in `App/tests/v2_mockup.py` with `{first_property}`, placeholder in `test_0710_v2_mockup_match_browser.py`, run 0710, fix page-own CSS diffs at 1024/1280/1440), then step 6 (screenshots), then design_lint and the report's remaining tails.

## 0535 CI old-markup (executor, 42 CI failures)

Status: blocked. Classified all 42; fixed 9 of 39 of ours. Left: 31 ours (below), needs the next session.

Shared (fail on `origin/claude/project-thread-50hyv5` too, not touched): `tests/test_0705_v2_shell_browser.py` (3 tests: `test_app2_css_has_the_phone_top_bar_rule_and_no_font_picker`, `test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar`, `test_v2_branch_is_wired_in_base_html_and_the_v2_shell_exists`). The other 39 pass on the shared base, so they are ours.

Fixed here:
- Leon row added to the aside Napojení card (`_property_editor.html`), same href, `data-leon-card` and `leon_page.card.*` text as the old overview card. Fixes `test_0396_leon_opt_in` (2), `test_0404_leon_setup` (1), `test_billing_leon` (1).
- Guide link added to the messages section (guest links block) with the old `leon_page.guide_link` text. Fixes `test_guest_guide_pages::test_property_page_links_to_the_guide`.
- Aside calendar count now uses `apartment.form.calendars_count` (the old "1 calendar" format) in `<small>`. Fixes `test_wp28_ui_sweep` counts test.
- Section 8 (assertion only): `test_stay_fee_property_panel` (`#stay-fee-settings` nav link to `href="#sec-fee"`; `data-settings-group="reporting"` to `id="sec-fee"`); `test_door_code_missing_times_0397` (settings-group lock asserts to `<details id="sec-lock" open>`); `test_entity_editor_navigation` line ~284 (overview link without `next`).
- No test deleted.

Left, ours, markup (section 8 candidates, not yet changed): `test_0286_health_cards` (2), `test_0291_open_buttons` (1), `test_0375_needs_you_and_open` (1), `test_design_properties` (2), `test_entity_editor_navigation` line ~300 operator-picker link and `test_property_without_a_business_links_to_its_own_settings`, `test_properties_table_chips` (2, CTA class `btn` and count), `test_property_form_nav` (4, the section nav is gone: delete candidate, but check the Czech copy test first), `test_property_health_0244` (overview health check: delete candidate), `test_stay_fee_property_panel::test_edit_page_has_stay_fee_panel_and_create_page_does_not`, `test_ui_consistency::test_the_copy_button_keeps_its_icon_when_it_confirms` (copy button now has no `<svg>`: the 0535 step 3b icon is injected by JS, the test wants it in markup), `test_page_help_0277` (3, properties list help).

Left, other pages (section 8 stop rule: do not touch in this thread, owner to decide): `test_dashboard_empty` (2), `test_dashboard_missing_banner` (3), `test_dashboard_order` (3), `test_signed_in_chrome` (1), `test_navigation_prefetch` (1, `/admin/*` prefetch exclusion missing from the shell), `test_design_admin::test_smart_locks...` (1, `style=` on body).

Checks: `tests/test_0534_property_page_v2.py tests/test_property_hub.py tests/test_static_versions.py`: `24 passed in 2.16s`. ruff (E9,F63,F7,F82,F401,F841): `All checks passed!`. context_lint: `context lint: OK`. design_lint: not run.

## 0535 merge + CI tests (executor)

Status: blocked. Part A done, Part B partly done (9 of 21 CI property failures fixed or removed). Part C not started.

Commits: `56ee002` merge of `origin/claude/project-thread-50hyv5` (base.html: their file, app2 `20261101-0535f-merge`, host `0531g`, host2 `0530c`; static_versions regenerated). `a49aacb` step 5 (nav/health deletions, 0286 rewrite). `9a8fae0` step 5b (unused imports). The commit `0535: property tests on the one-page markup` is not made; the steps above are the commits.

Merge check: `test_dashboard_empty`, `test_dashboard_missing_banner`, `test_dashboard_order`, `test_signed_in_chrome`, `test_navigation_prefetch`, `test_static_versions`: all pass.

Still failing after the merge, not touched (brief §8 stop rule, owner to decide): `test_0705_v2_shell_browser` (3, shared base), `test_design_admin::test_smart_locks...` (1, `style=` on body).

§8 changes (assertion or selector only):
- `test_0286_health_cards`: rewritten to the aside `.pv` rows (`#sec-calendars`, `#sec-police`). The problem test now sets `last_status='error'` (was `active=0`) so the row carries `is-bad`. Gap: the aside calendar row shows only a count, not the "No calendar connected" text.

Deletions:
- `test_property_form_nav.py`: 4 nav tests (`third_nav_link`, `no_longer_sends_you_off_the_form`, `czech_nav`, `nav_numbers`). File kept: 10 other tests pass.
- `test_property_health_0244.py`: `test_the_overview_shows_the_health_check`. File kept: 3 module tests pass. Unused imports removed.

Remaining failures (12, not yet changed):
- `test_0291_open_buttons::test_row_open_cue_has_no_arrow_icon`
- `test_design_properties` (2): list header tabs and icon; local property tabs.
- `test_entity_editor_navigation` (2): `/entities?edit=` links on overview and list; `#operator-picker` link.
- `test_properties_table_chips` (2): add-CTA `class="btn"` and `href="/apartments/new"` count.
- `test_stay_fee_property_panel::test_edit_page_has_stay_fee_panel...`: likely the 'Optional stay fee' text.
- `test_ui_consistency::test_the_copy_button_keeps_its_icon_when_it_confirms`: needs the v2 vs non-v2 button split.
- `test_page_help_0277` (3): `/apartments` and the v2 property page have no `data-how` block. The dashboard has one (`dashboard.html:60`). Question: add the block to those pages (template change, outside §8), or skip them in the test?

Checks: CI list plus `test_0534_property_page_v2`, `test_property_hub`, `test_static_versions`: 181 passed, 16 failed (12 above, 4 shared or owner items). ruff (E9,F63,F7,F82,F401,F841): clean after fix. context_lint: OK. design_lint: OK.

Part C (owner, 19:09 pills): not started. Needs the `app2.css` 0533 block change, override entry, key bump, `--write`, screenshot `docs/tasks/screenshots-0533/app-390.png`, commit `0533: smaller phone pills (owner)`.

Owner steps left: decide the `test_0705` and `test_design_admin` items; answer the help-block question.

## 0535 last CI tests + pills (executor, blocked)

Status: blocked (call budget reached after Part C and the help block).

Commits: `679f0b0` 0533: smaller phone pills (owner). Help block commit: this step (`0535 step: help block on property pages`).

Part C: app2.css 0533 phone `.st` now 12px / 600 / 3px 9px 3px 7px / gap 5px, dot 6px. Overrides added in `App/tests/v2_mockup.py` (SELECTOR_OVERRIDES: longhand padding, column/row gap; BOX_OVERRIDES: height 23px), reason "owner 2026-11-01 19:09: smaller pills than the phone mockup". Key `20261101-0535h-help`, manifest rewritten (41 files). `test_0710_v2_mockup_match_browser.py -k properties`: `12 passed in 16.17s` (0 skipped, 390/320/768). Screenshot `docs/tasks/screenshots-0533/app-390.png` retaken (/apartments?lang=cs, full page, 390 px).

test_page_help_0277: closed `ov-how` block (data-how="properties" on /apartments after `.sub`; data-how="property" on the property page after the h1; existing how.properties.* / how.property.* keys). Phone hide: `@media (max-width:1023px){body.v2 .ov-how{display:none}}` (no `ph-hide` class exists). Result: `test_page_help_0277.py` passes (3 cs/en/vi cases). Empty-state branch of /apartments has no help block.

Still failing, not changed:
- test_ui_consistency::test_the_copy_button_keeps_its_icon_when_it_confirms: the first `<button` before `data-copy-label-slot` is the v2 `btn-icon-label` copy button. Planned fix: if `btn-icon-label` in button, assert `<svg` not in button; else keep the icon assert.
- §8 items not yet done: test_0291, test_design_properties (2), test_entity_editor_navigation (2), test_properties_table_chips (2), test_stay_fee_property_panel edit-page panel, test_design_admin smart-locks `style=`.
- test_0705_v2_shell_browser: left alone (shared).
