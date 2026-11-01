# 0529 report (continuation 2, executor)

Status: blocked (all 6 stay geometry tests pass; 6 style tests still fail against the mockup; items 9 and 11 not done)
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
