# 0963 report (B05: P04, P05, P06, P09)

Status: blocked

Reason: row 4a has 4 failures and row 5 has 1 failure. All 5 also fail on base 7b0355c (proof below), so they are not caused by this batch. The brief's gate is "every row passes", so the orchestrator decides.

## Commits (branch codex/0963-b05-property-wrappers)
- 40088a45 `0963 step 4`: test race wait fix, archive "?" markup and CSS fix, app2.css key 0963b, static manifest regenerated.
- `0963 step 5`: this report (SHA in the final reply).
- `0963 status`: brief status line set to blocked.

## Test race (diagnosis accepted)
The scroll under a still pointer opened the archive tip through JS. The test asserted before the 150 ms close timer. Fix: `page.locator("#archive-help").wait_for(state="hidden")` before the unchanged assertion.

## Markup fix (help-stranded and 24 px tap target)
- `_property_editor.html`: the Archive button and its "?" sit in one `span.prop-archive-action`, so they wrap together.
- `app2.css` (appended): `.prop-archive-action` is inline-flex, nowrap. At max-width 1023 px, `.prop-archive-action .help-tip-btn` is 44x44. The 0833 rule `.property-settings-form .help-tip-btn` (24 px) was overriding it.
- Thresholds unchanged: lint same-line and gap of 32 px or less; geometry tap target 44 px on phones.
- Result: property-320 geometry passes. Row 4b (layout lint) passes.

## Fee-navigation deselection
`tests/test_host_fee_navigation.py::test_frozen_report_order_and_forms` is deselected in row 4a. Base proof: `/tmp/ubyhost-b05/base-fee.raw` on 7b0355c fails with `'Your records' in page` false.

## Rows (zero skipped in every row)
| Row | Result |
|---|---|
| 0963 + 0534 (the 2 new tests are in the browser file) | 20 passed, 4 deselected |
| 2a static and property | 73 passed |
| 2b property, onboarding, first | 335 passed |
| 3 copy and i18n | 46 passed |
| 4a host, 1 deselected | 223 passed, 4 failed |
| 4b design guardrails and layout lint | 15 passed |
| 5 v2 mockup | 182 passed, 1 failed |

Failures, all also failing on base 7b0355c:
- 4a: `test_host_ux_acceptance.py`: `test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host` (door_codes has no editor), `test_every_page_family_fits_every_width_language_and_rail_state`, `test_page_families_through_rail_cards_search_and_back`, `test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus`. Base: 4 failed.
- 5: `test_0710 ... test_v2_page_matches_mockup_styles[stay-320]`, `.stay-dates b` height 56 vs 28 px.

Harness notes: rows 2b and 4a were killed once (exit 143) and rerun. Row 3 on a fresh DB fails with "no such table", so it ran on a copy of a migrated test DB.

`context_lint.py`: OK (warnings only). `git diff --check`: clean.

## Screenshots (opened, 390/768/1280, EN and CS)
- archive-390: "Archive property" and "?" on one row, 44 px tip, not clipped.
- archive-768: same row, no overflow.
- archive-1280: button and 24 px "?" together, no overflow.
- archive-confirm-390: shared confirm dialog ("This item will move to Archived.", Cancel, Delete), existing behaviour.
- police-open-en-390: only the top crop shows (help popover over the example letter); subsections not visible in this crop.
- police-open-cs-390: "Připojení k UbyPortu" heading with the sample link beside it, then the IDUB and credential fields, then the "Ubytovací zařízení" subsection heading.
- copy-dialog-en-390 and cs-390: bottom sheet inside the viewport, rounded top corners, no dark border; Copy and Cancel visible.
- copy-dialog-en-768 and en-1280: rounded white dialog, Copy and Cancel, no square border.
- Stay fee heading: no dedicated screenshot; the accordion title is confirmed by the passing 0963 test.
- 320 px archive tip: covered by the geometry and lint tests (no separate screenshot).

## Section 7 ticks
- [x] Stay fee: one title, numbered settings first (0963 test passed; no separate screenshot).
- [~] Police: subsection headings confirmed in police-open-cs-390 only; the EN crop does not show them.
- [x] Archive: no accordion, one button, confirm opens; Cancel path covered by the test.
- [x] Copy chooser: rounded surface at 390, 768 and 1280, bottom sheet at 390.
- [x] No nested forms (test_property_navigation_browser passed), no duplicate ids.
- [x] 0 skipped in every row.
- [x] `git diff --stat 7b0355c..HEAD` lists only section 3 files plus the brief and report.

## Deviations
- Run without `-x` for full counts.
- Rows 2b and 4a rerun after an external SIGTERM.
- Row 3 run on a migrated DB copy.

## Done / Left
- Done: tests, fix, lint, screenshots, base proof.
- Left for orchestrator: decide on the 5 pre-existing failures (deselect or fix); EN police subsections not visually checked. No owner steps for the executor.
