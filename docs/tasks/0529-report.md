# 0529 report (continuation 2, executor)

Status: blocked (continuation 4: fixes 1 to 4 done; 25-call checkpoint reached)
Branch: task/0529-v2-stay-detail-rest (not pushed)

## Done
- Section 10 items 1 to 8 (earlier sessions).
- Horizontal scroll fixed: culprit was `[data-copy-state-icon]` (absolute badge) escaping the copy button. Fix: `.host-stay-detail{overflow-x:clip}`, `.host-stay-detail [data-copy]{position:relative}`.
- Crumb "Stays" link: `.host-stay-detail .crumb a{display:inline-block;min-height:24px;line-height:24px}`. Passes.
- Phone `<h1>`: the phone title `div.big` is now `<h1 class="big">` (only one visible h1 per width).
- Closed settings and file-by-hand details: `.host-stay-detail details:not([open])>:not(summary){display:none}`. Their hidden content had been pushing the lowest-content check to 1243 px.
- Help-tip `?` min-width 44 px below 1024.
- Key `20261101-0529d` in base.html, manifest written (41 files).
- Filing forms: `grep -c 'action="/reservations/'` = 12, unchanged (not re-checked after this session's edits; no form markup changed).

## Deviations
- Item 4: the app has no share-2 icon; the round copy button uses icon('copy', 20).
- Item 3: no menu-caret markup in reservation_detail.html; not verified in a screenshot.
- Item 6: the z-index of the security prompt was not checked. Probes that clicked its "later" button timed out once at 390 px, so it may be flaky. Not investigated.

## Left
- Item 9: the empty `<div class="card">` wrapper around `details#file-by-hand` (line 293) still renders. Render it only with submissions.
- Item 11: ordering test, `#police-card`, `guest-doc` class, update of test_host_stay_detail_layout_browser.py, 360 px check. Not started.
- PAGES entry `stay` (brief §2) needs selector fixes: `.code` is not in the desktop mockup stay view; `.head h1`, `.head .sub`, `.crumb` are missing in the app at phone widths (desktop-only selectors); desktop table td border colour differs (app rgb(28,28,26), mockup rgb(235,235,231)); `main h2`, `main .card`, `main .pill` differ at 768 px.
- Screenshots (`UBYHOST_SHOTS_V2=1 ... -k screenshots`), Read of stay-1280 and stay-390, §6 non-browser run.
- Sidebar "Stays" nav: shell-owned, not fixed.
- Untracked, not committed: App/.venv (never commit), docs/tasks/screenshots-0710/menu-*.png.

## Test tail (shared test -k stay, after this session's fixes)
```
      main table td border-bottom-color: app=rgb(28, 28, 26) mockup=rgb(235, 235, 231)
      .code: missing in mockup stay
    assert not ['main table td border-bottom-color: app=rgb(28, 28, 26) mockup=rgb(235, 235, 231)', '.code: missing in mockup stay']
/tmp/wt0529/App/tests/test_0710_v2_mockup_match_browser.py:125: AssertionError: stay at 1440 px: 2 style differences
6 failed, 6 passed, 21 deselected in 47.49s
```
Failing: test_v2_page_matches_mockup_styles[stay-320, -390, -768, -1024, -1280, -1440]. All test_v2_page_geometry[stay-*] pass.

## Section 10 run (executor, continuation 3)
Status: blocked. Stopped at the 25-call checkpoint.

Done (commits 32fd6c33, 4df2a21c, plus the WIP commit below):
- Decision 1: one `<h1 class="big">` in `.head`; phone h1 removed. Below 1024 only `.head .crumb` and the head `.sub` are hidden; flex order puts `.stay-top`, then `.head`, above the phone sub lines. `.big` is no longer hidden at 1024+. Phone title is full width.
- Decision 2: `.code` removed from desktop `selectors`, kept in `phone_selectors`. Table td border colour: the rule is the shared `td{border-bottom}` at app2.css line 33, so it is shell-owned, not fixed.
- Decision 6: `.actbar` z-index 10. The security prompt is `<dialog open>` with no z-index in app2, so `body.v2 #security-prompt{z-index:20}` was added. Not verified visually.
- Item 9: removed the outer `<div class="card">` around `details#file-by-hand`. The submissions card was already conditional.
- Item 11: `id="police-card"`, guest doc type in `td.guest-doc`. Ordering test now expects guests, reports, quick-edit. Test expects `#stay-quick-edit` to be DETAILS. `test_0525_stay_detail.py` regex now targets `guest-doc`.
- Key 0529e in base.html; static versions written.

Test results (not all green):
- `-k stay` on test_0710 (before the phone h1 width change): 6 failed, 6 passed.
  - 1024, 1280, 1440: only `main table td border-bottom-color` (shell-owned).
  - 320, 390: 16 diffs each: `h2.sec` width 118 vs 350, `.facts` height, `.row .ic` colour (state colour vs mockup demo green), `.row .t` widths, `.card` height, `.actbar .btn` missing in mockup pobyt, `.list .row` border (shell-owned).
  - 768: compares the desktop mockup with the phone layout (PHONE_WIDTHS = 320, 390). Test-design item, not fixed.
- `test_host_stay_detail_layout_browser.py`: fails at `.guest-card .guest-facts` count 0 (phone markup), not investigated.
- `test_0525_stay_detail.py`: 5 passed, 1 failed (`ValueError: substring not found`, the doc-label test after the regex change), not investigated.

Left (not run or not fixed):
- Rest of §6 (one file at a time), filing forms at 12.
- Read of stay-1280 and stay-390 after this change.
- Pobyt mockup pair: copied `mockup-None-320/390.png` as the pobyt pair; confirm the naming.
- Sidebar "Stays" nav: shell-owned, not fixed.


## Continuation 4 (executor, orchestrator fixes 1 to 4)

Done (commits on task/0529-v2-stay-detail-rest, not pushed):
- Fix 1: copy badge rules moved from host.css (385-406, reduced motion) to app2.css, scoped `body.v2`, plus `@keyframes host-copy-check`. `.host-stay-detail{overflow-x:clip}` removed; shared geometry tests still pass without it.
- Fix 2 and 3: the single row menu (`row_menu_begin/end`, one render) is placed by CSS: at 1023 px and below, absolute at top 6 px, right 64 px, next to the copy round button. Visual check still needed.
- Fix 4: phone action bar is the header CTA (one form, one render); `.stay-head-cta` is placed at the bottom by CSS below 1024 px; the duplicate `.actbar` markup was removed. Key `20261101-0529g`, manifest written (41 files).
- Phone guests h2 full row; phone h1 line height 1.15.
- Screenshots: stay-*.png copied to docs/tasks/screenshots-0529/ and mockup-stay-1280/390/320 copied; mockup-None-* deleted. These were taken BEFORE the CTA move: retake.

Test tails (last lines):
- test_0710 -k stay: 6 failed, 6 passed. Geometry tests pass. Style: 1024/1280/1440 only `main table td border-bottom-color` (shell-owned). 320/390: 14 diffs (`.big` height, `.sub` margin, `.facts` height, `h2.sec` height, `.list .row` border (shell-owned), `.row .ic` state colour (data), `.row .t` widths, `.card` height, `.actbar .btn` missing in mockup because the mockup calls it `.bar`). 768 compares the desktop mockup (test design, shell).
- test_0525_stay_detail.py: 6 passed.
- test_design_stay_detail.py: 2 passed.
- test_design_guardrails_browser.py: 11 passed.
- test_host_stay_detail_layout_browser.py + test_host_stay_actions_browser.py: 2 passed.
- test_0199_phone_geometry_browser.py: 3 passed.
- test_a11y_guard_browser.py: 3 passed.
- test_static_versions.py: 3 passed.
- test_host_wide_geometry_browser.py: 7 failed, 3 passed (sidebar and dashboard tests, not the stay page; not checked against the base commit).
- test_onboarding_followup_browser.py: killed at the 300 s limit; not finished.
- design_lint.py: FAIL, `T3 class not in catalog: police-failed` (docs/design/catalog.json not updated).
- context_lint.py: OK.

Edited assertions (intent kept):
- test_design_stay_detail: order is now guests, reports, police card, quick edit (mockup order).
- test_0525: the doc number check is scoped to the guest row (`guest-card-head` is gone).
- test_host_stay_detail_layout_browser: the fact grid is now `#guests` table or list (visible one); content check is the name only (the table no longer shows the birth year or document number); geometry check kept.
- test_design_guardrails_browser: the guest fact check uses the table row cells; `ui-section` removed from `#reports` (class `stay-reports`) and `#file-by-hand` (class `stay-section`) because they are containers, not panels. Please review this one.

Deviations:
- Menu placement and CTA placement are CSS-only; the copy is in the DOM once.
- `missing_ok` for `.actbar .btn` did not stop the mockup mismatch; the stay style test still fails on it.

Left:
- design_lint: add `police-failed` to docs/design/catalog.json.
- Retake stay screenshots at 320/390 after the CTA move; Read stay-1280 and stay-390 once.
- Phone style diffs listed above: owner decision on the `.sub` margin and `.facts` height (shell-owned or data).
- Run test_onboarding_followup_browser.py with a longer timeout.
- Sidebar and dashboard geometry (test_host_wide_geometry_browser): check on 0528 base.
- Not pushed; no PR opened.

## Final pass (section 11, executor run 2)
Status: blocked (tool-call cap; stays list fixes left).
Done: steps 1 (partly, shell items untouched), 2 (run, not fixed), 3 (filing forms = 12), 4 (screenshots copied), 5 (police-failed already in catalog classes and class_notes; design_lint OK; context_lint OK; static versions OK after key bump).
Orchestrator fixes done (commit 7f864756): `.sub`, `.facts`, `.card`, `.grp` margin-left/right 0 in `BOX_OVERRIDES` (tests/v2_mockup.py); `.chip.on` border-color `!important` in app2.css; app2 key bumped to `20261101-0529g`.
Stays 0710 (`-k "stays or stay"`): 6 failed. Chip and margin items pass now. Left (shell or data owned): `.row .ic` tone (fixture waiting vs mockup finished); `.sub` margin-bottom 8 vs 10; `.facts` height 139 vs 158; `h2.sec` height 33 vs 28; `.list .row` height 82 vs 76; `.row .t` widths; `.card` height 95 vs 102 at 390.
Step 2, file by file (one pytest process per file, `--tb=line -rs`):
- Pass: test_0523_stays_list (8), test_design_stays (3), test_archive_stays_on_page (10), test_stays_empty_workspace (14), test_0199_phone_geometry_browser (3), test_a11y_guard_browser (4), test_static_versions (3), test_0525_stay_detail (6), test_design_stay_detail (2), test_wp25_reported_bugs (29), test_host_stay_detail_layout_browser (1), test_host_filter_panels_browser (4 on rerun; one failure in the first run, not reproduced).
- Fails, stays list (our branch rewrote `reservations.html`; old classes gone): test_host_list_layouts_browser (2: `.stay-col-reporting`, `.stay-report-deadline`), test_host_list_page_layout_browser (3: `.row-primary-link` missing, "no clickable row"), test_host_wide_geometry_browser (8: `.stays-view .stay-col-reporting`, `.stay-col-stay`, `.stay-report-deadline` missing), test_design_guardrails_browser (2: sidebar search border and table row border selectors), test_host_stay_actions_browser (1: `td.stay-col-reporting [data-tone]`), test_onboarding_followup_browser (12: `tr[data-href^="/reservations/1?"] .row-primary-link`; new markup uses `.stay-identity-link`), test_overhaul (3: `test_reservations_sorted_earliest_first` (0 date cells), `test_the_stay_page_reads_as_one_ordered_grammar` (order), `test_the_receipt_download_moves_into_the_report_row_menu` (section id `reports` not found on stay page)).
- Not fixed: these selectors encode the old stays-list markup; converting them is a test-selector rewrite plus possible layout checks, not done in this run. They are stays-related, so ours to fix in the next run.
- Shell base check: not yet run. Our branch touches `reservations.html`, `reservation_detail.html` and app2.css; the failing list tests use stays-list selectors, so none are "fails on the shell base too" so far.
Screenshots: `docs/tasks/screenshots-0529-final/` holds stays-390/1280, stay-390/1280 (app) and mockup-stays-390/1280, mockup-stay-390/1280. Not yet viewed.
Left for next run: step 2 fixes above; view the four app shots once and list differences; rerun the §6 list.
