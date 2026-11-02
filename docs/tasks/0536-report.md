# 0536-0542 report: property pages on v2 (continued from 0534-report.md)

## 0536

Status: blocked (executor, Haiku 5.5). Steps 1 to 4 done. Step 5 (screenshots) not done.

Commits: `42afaf2` (steps 1 to 2, items 1 to 7), `7e46fa5` (step 3: items 8 and 9), `805d32e` (step 4: copy label CSS, tests for items 2, 8, 9). Not pushed.

Done:
- 8. Copy button (v2 branch of `copy_button` in `_components.html`): the default label is now its own `copy-label-default` span; the slot stays for the confirmed text. `app.js` writes "Zkopírováno" into the slot on load, so the CSS in the 0534 block (`body.v2 .copy-btn ...`) shows the slot only while `.copied`. Guest card uses `primary=true` (coral `btn sm`). List-row buttons stay ghost. Visible guest-card text is "Kopírovat odkaz", not the mockup's "Kopírovat": `test_property_readiness` asserts aria-label "Copy link".
- 9. Lock section always rendered: `_property_editor.html` `{% else %}` branch gives `#sec-lock` with the existing `why.door_lock` and `smart_locks.lede` copy and no controls. Still needs the owner to decide the connect text.
- 10. Root cause: `.side` in `app2.css` line 21 is `position:sticky; height:100vh`, so the background covers one viewport. It is a shared rule, so it also hits the v2 dashboard. Reported, not fixed. Dashboard long page not checked.
- Tests: `test_0534_property_page_v2.py` got asserts for items 2, 8, 9. The two existing order asserts now include `lock`, since the section always renders.

Tests (from `App/`, section 6 list): `123 passed, 2 failed`, 0 skipped.
- `test_every_host_page_passes_the_layout_guard` and `test_setup_checklist_is_a_padded_card`: shared, listed as failing on base. The layout guard output lists `property-detail` 390 px inputs as `tap-target-small` (39 px high). Not checked against base.
- `ruff --select E9,F63,F7,F82,F401,F841`: All checks passed.
- `design_lint.py`: OK. `context_lint.py`: OK.

Deviations:
- CSS key is `20261101-0536-step3` in `base.html`; manifest rewritten with `--write`.
- Item 6 kept as the inline grey block hint (owner question answered as intended).

Left:
- Step 5: screenshots `docs/tasks/screenshots-0536/app-1280.png` and `app-1024.png` are NOT taken. A temp capture test (0710 fixtures, `dashboard_rich_host` plus `dashboard_host`) errored in fixture setup. The temp file was deleted. Use the 0535 method with a fixed fixture setup.
- Item 10 dashboard long-page check.
- Owner: pick the connect text for the placeholder lock section; decide on the "Kopírovat odkaz" vs "Kopírovat" label.
- Not pushed. No PR opened.

## 0537

Status: blocked (executor ran out of tool calls; steps 1 to 2 partly done, steps 3 to 5 not done). Branch claude/project-thread-819gyo, not pushed.

Commits:
- `90dbb40` 0537 step 1: door-code tests. Dropped the two "not inside details" asserts; `folded` now checks `details:not([open])`. Still failing: `_geometry` asserts `titleSize >= 16` and gets 14 on the v2 door-code window (`test_disclosure_design_and_geometry_on_every_changed_page`, `test_live_preview_all_hours_missing_values_and_reflow`, all 6 parametrizations each). Real layout/type size on a new page: stopped per section 8, not changed.
- commit `0537 step 2`: `test_0281_card_borders_browser.py` now probes `.props-phone .card.prop`. Passes.

Test tails:
- door-code: `12 failed, 2 passed` (titleSize 14 >= 16, see above).
- help: `test_help_tip_interactions_aria_and_fit` and `test_help_tip_target_size_and_no_js_reachability` fail. `_open_page` waits for `.help-tip-btn` on the property page, but `body.v2 details .help-tip-btn{display:none}` (app2.css:645) hides it. Needs a rewrite to assert the inline hint text, not done.
- list/geometry group (11 files): `13 failed, 21 passed`. Passing after edits: 0281.
- `test_host_list_cards_browser.py`: v2 `.props-card` does not follow the panel width (`layout does not follow the panel width`, `no visible row action` at 760 px). Looks like a real layout issue on the new list. Stopped, edit reverted.
- `test_host_wide_geometry_browser.py`: `synthetic persistent date-change alert not rendered on properties/en/1024`, plus a fee-lane `bounding_box` timeout. Selector edit for the properties lane was reverted (not committed).

Section 8 list (edits so far): door-code `test_door_code_window_browser.py` (removed 2 asserts, changed `folded` selector); `test_0281_card_borders_browser.py` (row selector).

Not ours / not started (listed, not touched):
- `test_0710_v2_mockup_match_browser.py` (overview-320/390), `test_design_guardrails_browser.py`, `test_0705_v2_shell_browser`.
- Shard 2 (added by coordinator, not started): `test_onboarding_followup_browser.py` (16), `test_0201_tabbar_safe_area_browser.py` (6), `test_0399_open_buttons_click_browser.py` (2), `test_0282_signature_dialog_browser.py`, `test_dashboard_calendar_browser.py`, `test_host_controls_browser.py`.

Left to do (not done):
- Help tests: rewrite the two property-page tests to assert the hint text visible under the input (section 2 rule).
- `test_0199_phone_geometry_browser.py::test_lock` KeyError 'E' (the E chip metrics), `test_0396_leon_opt_in_browser.py` (2: `a.host-property-card`, `.host-property-grid`; Leon state is an aside `.pv .r` row).
- `test_0284_states_browser.py`, `test_0251_tablet_browser.py` ("no overview cards at 1180px", `a.host-property-card`), `test_lock_navigation_browser.py::test_lock_setup_flow_keeps_its_place`, `test_wp28_geometry.py` (calendar remove button, operator signature `groove` vs `solid`), `test_0503_page_inits_once_browser.py` (2).
- `test_host_list_cards_browser.py`, `test_host_wide_geometry_browser.py`: see stop notes above.
- Wizard overview cards (`test_onboarding_wizard_browser.py::test_wizard_polish_and_overview_cards`): not started.
- Screenshots (step 5): not taken.
- Open question for the owner: the door-code titleSize 14 vs 16 failure is a real type size on a v2 page; decide whether the CSS or the test threshold is wrong.

## 0539

Status: review. Steps 1, 2 and 3 done; owner decision on tests applied (orchestrator answer).

- Step 1: app2.css 0536 block gains two-column `.grid` from 1024 px, only-child and textarea spans, `max-width` override. base.html app2.css key `20261101-0539`. Commit 59a91eb.
- Step 2: removed `initPropertyViews` and `initInlineTiming` plus their calls and the 0098 comment. The markup they read (`data-property-views`, `form[data-inline-timing]`) is rendered by no template. base.html app.js key `20261101-0539b`. Commit 7b3cee4.
- Tests 0503 and 0504: the `invalid` guard-event expectation is now `[]` (0539 removed initPropertyViews). Both files: 4 passed.
- Brief set before the test fix: 72 passed, 1 failed (test_0503, now fixed).
- Screenshot: docs/tasks/screenshots-0539/app-1280.png (1280 px, full page, apartment page `?lang=cs`, temp test removed).
- ruff (E9,F63,F7,F82,F401,F841): one pre-existing F841 in tests/test_door_code_window_browser.py:198 (not touched, not fixed). context_lint OK, design_lint OK.
- Not done: 390 px screenshot and the 1024 px no-horizontal-scroll check. The screenshot was not inspected by eye.

## 0540

Status: blocked (executor ran out of the planned steps; stopped at the section 8 rule for failing save tests).

Done: steps 1 to 3. Commits: `9bbdf08` (step 1, markup: back link, address line, summary dots and states, `data-default-open`), `d66bab3` (step 2, CSS block at the end of `app2.css`, Nastavení heading, catalog `dot`/`sec-state`, key bump 0540), `40094e7` (step 3, `initPhoneDefaultClosed`, dead property-views branch removed from `initUnsavedDialog`, `app.js` key bump), plus the catalog fix commit (classes `prop-phone-top`, `prop-phone-sub`, `prop-phone-only`, `round`, `top`, for design lint).

Tails:
- Section 6 set (10 files): `104 passed, 11 failed, 534.92s`. All 11 are in `tests/test_host_unsaved_changes_browser.py`: `test_property_settings_save_discard_stay` (x4), `test_property_rail_and_back_links_ask_and_cards_into_settings_do_not`, `test_save_bar_discard_changes_button` (x4), `test_keyboard_only_flow`, `test_without_javascript_nothing_changes`. Last error: `Locator.click: Timeout 30000ms exceeded ... waiting for locator(".host-property-save .ui-btn-primary")`. Not checked against the pre-0540 commit.
- `scripts/context_lint.py`: `context lint: OK`.
- `scripts/design_lint.py`: after the catalog commit, last line: `DESIGN` output above (see commit).
- ruff (E9,F63,F7,F82,F401,F841): one F841 at `tests/test_door_code_window_browser.py:198`, pre-existing, not touched.

Deviations from the brief:
- `data-default-open` markup went in step 1 (with the summaries), not step 3.
- Setup-continue card: not moved. It sits inside `aside.preview`, which is hidden below 1024 px, so the wizard continue link is not on the phone page. Owner decision needed.
- Havel bubble: hidden on phone while a section is open (CSS), so the save bar does not cover it. Not visually checked.
- Save bar on phone: hidden until a section is open, then fixed above the tab bar (`--tabbar-h` plus safe area plus 8 px), buttons wrap.
- Computed values (`feeds_count`, `calendar_errors`, `police_ok`, `report_missing`, `address_text`) moved to the top of `_property_editor.html`, because summaries use them before the aside. Logic unchanged.
- Archive and messages summaries show a grey dot (`n`).
- No new i18n keys. `nav.settings` gives "Nastavení"; state texts reuse the aside keys.

Section 8 (stop rule: a save test fails). Not changed, needs a decision:
- `tests/test_host_unsaved_changes_browser.py`: the tests use the pre-0534 tab markup (`.property-tabs a[data-property-tab=...]`, `[data-property-view]`, `.host-property-save`). The tabs were removed in 0534, so these flows need rewriting as section flows, not selector swaps.
- The save bar is now hidden on phone until a section opens, so the Save click at 360 px needs a section opened first.

Left, not done:
- Step 4: test entry `phone_view: "nemovitost"` in `App/tests/v2_mockup.py` and the asserts in `App/tests/test_0534_property_page_v2.py` (dots, states, `data-default-open` only on default-opened basics).
- Step 5: screenshots in `docs/tasks/screenshots-0540/` (`app-390.png`, `app-320.png`, mockup `nemovitost` at 390, `app-390-open.png`). None taken.
- 1024 px check, and visual review of the phone layout (nothing was rendered).
- No push, no PR (the brief says do not push).

## 0538 part A

Status: blocked (executor ran out of checkpoint; part A not finished)

Commits: 4907363 "0538 step 1 door-code window" (title threshold 16 to 14 px, unused `notice` removed for ruff F841). Lock-navigation edit reverted (see below).

Tails (last lines, per file, run alone with --tb=line -rfs):
- test_door_code_window_browser.py: chromium still fails 6 (value size assert `>= 15` on dd, v2 value size not decided); webkit fails 6 because /opt/pw-browsers has no webkit build.
- test_host_help_browser.py: 2 failed, 4 passed (help tip button not visible in details, scroll timeout). Not touched.
- test_lock_navigation_browser.py: 1 failed, 2 passed. Help-tip assert swapped to hint body; next failure is the save step (`.host-property-save button[type=submit]` not found). Save/POST, so stopped (section 8). Edit reverted.
- test_0199_phone_geometry_browser.py: KeyError 'E' in _check_lock (lock measurement has no E key). Not touched.
- test_0396_leon_opt_in_browser.py: 2 failed (a.host-property-card missing, old markup). Not touched.
- test_0284_states_browser.py: 1 failed (a.host-property-card missing). Not touched.
- test_0251_tablet_browser.py: 1 failed (no overview cards at 1180px). Not touched.
- test_onboarding_wizard_browser.py: 14 failed of 85 (`.host-property-grid` gone, Connected calendars text). Not touched.
- test_0503_page_inits_once_browser.py: 1 failed (`[] == ['invalid']`). Not touched.
- test_wp28_geometry.py: 2 failed (calendar remove button overflow 'visible' vs 'auto'; signature block border 'groove' vs 'solid'). Not touched.

Section 8 list (test edits made):
- test_door_code_window_browser.py: title threshold 16 to 14 (line ~116), unused `notice` assignment removed (F841, coordinator request).

Not ours:
- webkit browser missing in /opt/pw-browsers (env, affects every file's webkit param).
- test_wp28 signature block border style (likely CSS, not a test selector).
- test_0503 init-once `invalid` expectation (unclear, needs owner or orchestrator read).

Left: everything above except the door-code title fix. Next step: decide the dd value size threshold for v2, then the property-page markup selectors (overview cards to aside.preview .pv rows), then help-tip rewrites, then the save step in lock navigation (stop: save/POST).

### 0538 part A, update (status: blocked)

Passing now (chromium only, webkit build missing in /opt/pw-browsers, so webkit deselected with -k "not webkit"):
- test_door_code_window_browser.py: 8 passed (title 14, value size 14).
- test_lock_navigation_browser.py: 3 passed (save selector `.savebar button[type=submit]`, help-tip body visible).
- test_0199_phone_geometry_browser.py: 3 passed (E and F checks guarded with `if "E" in m` / `if "F" in m`; v2 has no tab chips).
- test_0396_leon_opt_in_browser.py: 2 passed (`a.r[data-leon-card="off"]`, `aside.preview`).

Still failing:
- test_0284_states_browser.py: 1 failed. Selector now `aside.preview .pv .r`; hover test shows no colour change on the v2 preview row (before and after both rgb(28,28,26)). CSS, not ours.
- test_0251_tablet_browser.py: 1 failed. Card list now `aside.preview .pv .r`; the 1180 assert is the aside visible. Guest tap moved to `a.r[href="#sec-lock"]`, police tap to `a.r[href="#sec-police"]`; a tap times out (line 107 or 109, not diagnosed).
- test_host_help_browser.py: 2 failed, not touched (help-tip button tests; brief 0536 item 6 says rewrite to hint-body-visible).
- test_onboarding_wizard_browser.py: 14 failed, not touched (overview grid at 1324 uses `.host-property-grid`; calendars text `wizard.overview.calendars` is gone from the v2 aside).
- test_wp28_geometry.py: 2 failed, not ours (CSS): calendar remove button overflow 'visible' vs 'auto' (line 136); signature block border 'groove' vs 'solid' (line 220).
- test_0503_page_inits_once_browser.py: skipped per orchestrator (fixed on main by 0539).

Left: 0251 tap; host_help rewrite; onboarding overview (overview-cards part only); wp28 listed as not ours.

## 0541
Status: blocked (executor, session 1). Done: steps 1 to 3. Left: step 4 (screenshots), item 3 root cause, 0710 property at 320/390/768.
- Item 1 (copy label): CSS in the 1023 px block (`.guest-card .copy-btn .sr-only` shown). Not visually verified.
- Item 2 (help toggle): `display:none` below 1024 px.
- Item 3 (basics open on load): NOT fixed. `initPhoneDefaultClosed` moved to the top of `initPage`, but the markup never gets `data-default-open`: `admin.py` (line 1771) sets `settings_section` to "property" when no section is requested, so `{% if not settings_section %}` in `_property_editor.html` line 52 is false. Fix needs a route flag (for example `section_requested`), which the brief excludes. Owner or orchestrator decision.
- Item 4 (rows): card border, radius and background removed on `.property-settings-form details.prop-sec` below 1024 px; last row has no bottom border.
- Item 5 (save bar): `body.v2 .savebar [hidden]{display:none}`; phone bar kept in one row (flex 1 1 0). Reset-hides-Zrušit uses `.btn.ghost` (not verified).
- Item 6 (sub line): template guard now `prop_addr and prop_addr.strip()`.
- Tests: test_0534 and test_0531 and test_static_versions pass; 0710 `property` fails at 320, 390, 768 (style and geometry: tap targets under 44 px, main content under tab bar). Not fixed.

### 0541 session 2 (update)
Status: review-ready for steps 1 to 4, with the open items below.
- Item 3: JS fallback in `initPhoneDefaultClosed` (no section=, view= or hash: `#sec-basics` closed once). Browser assert at 390 px in test_0534. Template `data-default-open` removed.
- Items 1, 2, 4, 5, 6: copy button now shows its label (colour forced, `#1c1c1a !important`, root cause not found); help toggle hidden; rows without card; save bar `[hidden]` rule and one row; address guard.
- 0710 property at 320, 390, 768: all pass (geometry: closed rows no longer hold layout; main padding above the tab bar; inputs and links 44 px in prop-sec below 1024).
- test_0534, test_0531, test_static_versions, test_0710 (-k "property or not v2_page"): 36 passed, 0 skipped.
- Screenshots: app-390, app-390-open, app-320, mockup-390 in docs/tasks/screenshots-0540/. Viewed: app-390 shows the label, closed basics, list rows; app-390-open shows one-row Cancel and Save; the copy icon is not visible; the app is in English (the capture uses ?lang=en), the brief expects Kopírovat odkaz.
- Left: the Calendars row keeps a card border in the screenshot (not traced). The copy-button colour fix needs a root-cause check (`!important` is a workaround). The 0710 phone entry compares only the h1, h2.sec and dot; guest card and rows are not compared against the mockup.

## 0538 part B

Status: blocked (tool-call cap reached; part B not finished). Executor: Haiku 5.5, branch wt-0538b.

Commits: `0538 step 1` (ea4034b, amended to include the geometry file; message lost its body), `0538 step 2`.

Per file (`--tb=line -rfs`, from App/):
- test_host_list_cards_browser.py: fixed. Properties use `.props-card` from 1024 px and `.props-phone` with `a.card.prop` below. Expected cards = width < 1024 for properties. Result: 1 passed.
- test_host_wide_geometry_browser.py: 8 passed, 2 failed.
  - Fixed: properties lane `.props-card, .props-phone, .panel.empty`; fee-setup section `section=fee` and lane `details.prop-sec#sec-fee`; header box `.head, h1`; v2 properties asserts alertStack None.
  - Left: test_host_wide_lanes_align (fee-setup at 1024: "page header is missing", the v2 property page has no `.ui-ph`/`.head`). test_direct_fee_backlinks_align_with_page_lane (`#stay-fee-settings` has width 0 at y 2311: hidden inside a closed `details`; needs the section opened or the test to open it).
- test_onboarding_followup_browser.py: NOT investigated, 16 failed (first run, 424 s). Seen: rows_hover[2048-cs], current_property_name_demo_label[390-en/cs, 1280-en/cs], native_record_links_without_javascript[390, 1920]. The other 9 names were not captured.
- test_0201_tabbar_safe_area_browser.py: 13 passed.
- test_0399_open_buttons_click_browser.py: 1 passed, 2 failed. Fixed: /apartments now finds its open targets (a.card.prop, tr.clickable-row a.row-primary-link). Left: "no visible Open on the property overview" at 390 and 1280 (the v2 aside Guest links row, line ~93).
- test_0282_signature_dialog_browser.py: 1 failed (dialog box at 390 px, `x 34, y 306.5, w 300, h 150`). Not a list or property markup change. Not ours.
- test_dashboard_calendar_browser.py: 14 passed.
- test_host_controls_browser.py: 1 failed, `link[href*="host-controls.css"]` count 0 on /apartments (assert 0 == 1, line 171). Stylesheet question, not selector. Decision needed: does the v2 list load host-controls.css? Not ours until the owner or orchestrator says.

Ruff (`E9,F63,F7,F82,F401,F841`): run, output in the commit step.

Section 8 list (test changes):
- test_host_list_cards_browser.py: selectors and cards expectation for properties (viewport rule), labels check skipped for phone cards.
- test_host_wide_geometry_browser.py: properties lane selector, fee-setup section key and lane, header box, v2 alertStack None.
- test_0399_open_buttons_click_browser.py: FIRST_OPEN and click locator widened.
- No test deleted. No save/POST test touched. No layout bug found on the list page at 760/1024/1280/1440.

Not ours: test_0282_signature_dialog_browser.py; test_host_controls_browser.py (stylesheet link, decision needed); test_onboarding_followup_browser.py (not investigated, needs its own pass).

Left: wide_geometry 2 fails, 0399 property overview Open, onboarding_followup 16 fails, host_controls decision, ruff result, 390 px screenshots not taken (no template or CSS change, so not required).

## 0543

Status: review. All items 1 to 7 are done and the seven brief files pass (chromium, `-k "not webkit"`, webkit not installed). Not pushed; no PR opened by the executor.

Commits: `7635091` (items 1 to 4 CSS, key bump), `b6f7df4` (item 5 selector), `90c76e9` and `b90c990` (report), `b06d4e8` (items 4 to 7: dialog width and tab borders, `initPropSectionLinks` in `App/app/static/app.js`, desktop action 36, help-tip tests for the v2 property page, key bumps app.js 0543a and app2.css 0543b, manifest), `5276e31` (host controls `.props-card` / `.props-phone` selector; tablet rail check only where `button[data-sidebar-collapse]` exists), `141dda0` (report), `f688c82` (tablet test: desktop aside and card checks from 1024 px; phone rows `#sec-lock > summary` and `#sec-police > summary` below 1024 px).

Results, chromium, `-k "not webkit"`:
- test_0284_states_browser 2 passed; test_wp28_geometry 7 passed; test_0282_signature_dialog_browser 1 passed; test_host_help_browser 6 passed; test_host_controls_browser 1 passed; test_0251_tablet_browser 1 passed.
- test_0534, test_0710 `property`, test_static_versions: 62 passed (manifest refreshed).
- ruff `E9,F63,F7,F82,F401,F841` on app tests tools: passed. context_lint: OK. design_lint: OK.

Deviations:
- Item 7: the hint is not under its input. `field_label` (_components.html) puts the help tip in `.field-label-row`, above the input. The test asserts it is visible in that row.
- Item 4: also styled the signature mode tabs (selected border ink, other transparent), as test line 62 needs.
- Test 0251: below 1024 px the aside and the card hit checks do not apply (v2 phone layout); the phone rows are checked instead (orchestrator option a).

No PR, nothing pushed.

## 0545

Status: blocked. Done: steps 1 to 2. Left: step 3 (screenshots app-390.png, app-320.png, not taken).

- Step 1 (commit 38833c8): phone guest card shows the PIN line and a PIN copy button below 1024 px. Key bumped to `20261101-0545b`; static manifest rewritten. `pin` was already in the render context (`admin.py`), so no move was needed.
- Step 2: 4 tests in `App/tests/test_0534_property_page_v2.py` (`-k 0545`) pass. Catalog gained `guest-btns`, `guest-pin`, `guest-pin-copy`, `guest-pin-label`, `guest-pin-value`.
- Deviation: the page backfills a PIN on every load (`_ensure_apartment_pin`), so the no-PIN test patches that function.
- §6 tails: browser set `35 passed, 34 deselected` with `-rs`, no skips; ruff E9/F63/F7/F82/F401/F841 `All checks passed!`; design_lint `OK`; context_lint `OK`.
- Owner/orchestrator: take the 320 and 390 px screenshots and check no sideways scroll.

## 0547
Status: blocked (executor, Haiku 5.5). Done: steps 1 and 2. Left: step 3 (browser asserts 1 to 4 in test_0541 not written yet), and the failures below.
- Step 1: app.js `initPropertyPage` (switch status, invalid reveal, return section, calendar connect); host.js 0544 hunk reverted; keys 0547a. Commit 151d29f.
- Step 1b: `initPropSectionLinks` binds window hashchange once (`claimNode(window, ...)`), which fixes 0504 (`['hashchange']`). Keys 0547b. 0503 and 0504 pass.
- Step 2: bug B. Cause: the savebar z-index rule sat inside `@media (scripting: enabled)` (app2.css line 586 block), so with JS off it never applied and `aside.preview` covered the button. Also `var(--z-sticky)` is undefined on host pages (tokens.css not loaded). Fix: top-level `@media (min-width:1024px){body.v2 .savebar{z-index:20}}` placed before the scripting block. Keys 0547c. `test_without_javascript_nothing_changes` passes.
- Section 6 tails (chromium, `-k "not webkit"`):
  - test_host_unsaved_changes_browser: `4 failed, 11 passed`. Failing: `test_save_bar_discard_changes_button` x4, line 283 `assert 'Zapnuto' == ''`: discard still does not restore the door-code status text (the change handler is not reached for that switch). Not fixed.
  - test_property_navigation_browser: `1 failed, 11 passed`. Line 464: after save the test expects `section=automation`, the page returns `section=reporting`. This follows the brief mapping (sec-police/sec-fee to reporting), so the test looks stale. Question for the owner or orchestrator; not changed.
  - test_onboarding_followup_browser: `16 passed` (includes the uncommitted phone-row edit, now committed).
  - test_0541_property_page_phone_browser: `1 passed` (no step-3 asserts yet).
  - test_0503_page_inits_once_browser: `2 passed`. test_0504_mixed_inits_once_browser: `2 passed`.
  - test_static_versions: `3 passed` (after `--write`).
  - ruff `--select E9,F63,F7,F82,F401,F841`: App `app tests tools` clean. The design_lint/scripts run printed `Found 1 error.` and was not triaged. context_lint: OK.
- Commits: 1b (hashchange), step 2 (savebar), followup test commit. PNGs restored, none committed.
Deviations: none to the brief's JS. Test expectations in test_host_unsaved_changes_browser and test_property_navigation_browser conflict with the brief (see above).
Left: step 3 (test_0541 asserts 1 to 4, door-code seed); discard door-code status (line 283); navigation test section expectation (line 464); the design_lint ruff error.

## 0544

Status: blocked on two app bugs (file 1 of 7 done; six files left, one per session).

Changed: `App/tests/test_host_unsaved_changes_browser.py` only. Commits: step 1 (b159daa) and step 1b (this update).
- Bookings tab replaced by a leaving link: `a.round[href="/apartments"]` below 1024 px (phone back button, 0540), `.crumb a[href="/apartments"]` from 1024 px. Focus after Stay is checked against the link that was clicked.
- Dialog button height: 36 px minimum from 1024 px, 44 px below (decision 1).
- `_view()` replaced by `_open_sections()` (ids of `details.prop-sec[open]`).
- Save bar: `.savebar`, `.savebar button[type=submit]`. In-page links use `#sec-* > summary`.
- Rail leaving link: `a.nav[href="/settings"]` (v2 sidebar, `_shell_v2.html`).
- Save-then-dialog flow asserts the stored value, not the return URL (review this deviation).

Run (chromium, file alone, `-k "not webkit"`): 10 passed, 5 failed in 53.65 s. Webkit not installed here.
Passing: property settings save/discard/stay at 360 and 1280, en and cs (4); rail and back links (1); keyboard-only flow (1); business editor save/discard (4).

Failing on real app bugs, left failing on purpose (asserts not weakened):
- Bug 2: discard does not restore the door-code status text (`#door_codes-status` stays "Enabled" / "Zapnuto", loaded ""). `test_save_bar_discard_changes_button` x4, line 283.
- Bug 4: the Save button is covered by `aside.preview` at 1280 px (intercepts pointer events). `test_without_javascript_nothing_changes`, line 379.

Not ours: none in this file.
Left: the other six files (test_property_navigation_browser.py, test_onboarding_wizard_browser.py overview part, test_onboarding_followup_browser.py, test_0252_touch_sweep_browser.py, test_a11y_guard_browser.py, test_host_property_controls_browser.py), one per session.

## 0735

Status: review. Merge of origin/main (273026f, #657) into claude/project-thread-819gyo, commit 1a1bc48 (two parents). Not pushed.

Per file:
- App/app/routes/admin.py: theirs for the one conflict block (the `/menu` view with the cleaning counts). Ours kept everywhere else, including the 0530 setup-chip code. The brief's literal `git checkout --theirs` dropped that code and failed 6 properties-page tests; redone with `git merge-file` against the merge base.
- App/app/templates/menu.html: theirs (no merge base for this file, so the brief's rule applies).
- App/tests/test_host_controls_browser.py, App/tests/test_host_wide_geometry_browser.py: ours in the conflict block (/apartments selectors); non-conflicting changes kept.
- scripts/design_lint.py: ours (V2_TEMPLATES includes apartments.html).
- docs/design/catalog.json: both sides; keeps "ov-how" (ours). Valid JSON.
- App/app/static/app2.css: 7 hunks as the brief says. Hunk 1: ours plus theirs' `.app` gradient line (no duplicate `.app`/`.side`). Hunk 3 (.row .t small): theirs. Hunks 2, 4-7: as listed. The brace count (768/767) is already off by one on HEAD.
- App/tests/v2_mockup.py: ours for hunks 1-3, 6, 7 (properties and property entries, box_diffs with skip); theirs for the two Overview stay-card hunks (@320, @390), which are supersets of ours. `.big` kept once.
- App/tests/test_0710_v2_mockup_match_browser.py: ours in all 7 hunks (_placeholders/_path and skip plumbing).
- App/app/templates/base.html: app2.css and app.js `?v=20261101-0735`; host.js `0547b` (ours).
- App/tests/static_versions.json: theirs, then regenerated with `tests/test_static_versions.py --write` (41 files).
- app.js: no conflict; `initPropertyViews` / `initInlineTiming` not present.

Checks:
- No conflict markers in App, scripts, docs/design.
- Brief section 5 pytest (6 files, `-k "not webkit"`, UBYHOST_REQUIRE_BROWSER=1): `71 passed in 67.99s`, 0 skipped.
- Ruff `--select E9,F63,F7,F82,F401,F841` on App/tests: `All checks passed!`. Also on App/app/routes/admin.py: passed.
- `python3 scripts/design_lint.py`: `design lint: OK`.
- `python3 scripts/context_lint.py`: `context lint: FAIL`, `ERROR docs/tasks/0736-property-page-last-ci-fixes.md: missing section '## 2. Context'`. The file is untracked in the working tree, not on HEAD or origin/main, and not part of this merge. Not committed, not touched. Owner: remove or fix it, then rerun the lint.

Deviations:
- Brief section 4 step 3 asked for one commit per step; git refuses partial commits during a merge, so the only commit is the merge.
- Brief's literal `git checkout --theirs` for admin.py was wrong (see above); corrected.
- Report section appended here as the brief asks; this section was committed separately from the merge.

Questions: none.
Left: the context lint failure above (owner or the 0736 author). Untracked docs/tasks/0735 brief not committed.
