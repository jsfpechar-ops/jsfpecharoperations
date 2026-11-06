# 0977 report

Status: blocked

Done: steps 1 to 4 (step 4 partly). Left: step 4 failures (below), steps 5 to 10 (feed URL lint, wording revert, stay-fee tests, verification and screenshots, final report, PR review).

## Files changed
- Renames: docs/tasks 0958 to 0964 files to 0978 to 0984 (step 1).
- Text references to 0958 to 0964 renumbered in App/app, App/tests, docs/tasks (script, 375 replacements).
- Merge of origin/main (step 2): six conflicts resolved by hand (app2.css both sides, the rest branch side plus main's 0964 comment in v2_mockup.py).
- Cache keys 20261106-0977: base.html, guest/base.html, _dashboard_calendar.html, _signature_script.html, static_versions.json (step 3).
- App/tests/v2_mockup.py: stay-dates small@320 and b@320 re-pinned to 94px, 0977 comment added (step 4).

## Commands (last lines)
- Step 1 collect: `pytest test_host_property_controls_browser.py test_guest_browser_e2e.py --collect-only` gives 55 tests collected.
- Step 3: `pytest test_static_versions.py test_wp07_cache_heartbeats.py -q` gives 16 passed.
- Step 4: `pytest test_0710_v2_mockup_match_browser.py -k stay -q -rs` gives 3 failed, 39 passed, 141 deselected. Failures: stays at 320 and 390 px, `.mh .big, .head h1` width app=100.203px mockup=77.0625px; stay at 320 px, `.stay-dates .tot` width app=238px mockup=280px. These pins are not in the brief's list; not changed.

## Section 7 checklist
- [x] merge-base with origin/main; no conflict markers
- [x] static_versions test passes
- [ ] stay mockup tests pass (3 failing, see above)
- [ ] layout lint, validation wording, stay-fee tests, screenshots: not run (steps 5 to 8 not started)

## Deviations
1. Step 1: docs/tasks/0977-pr790-merge-main.md skipped (the script would have rewritten this brief's own table).
2. App/.venv was missing; created from requirements.txt and requirements-dev.txt, plus playwright==1.63.0 (gitignored).
3. Step 3: the brief named three keys, but signature.js (_signature_script.html, guest/base.html) and dashboard-calendar.css (_dashboard_calendar.html) also changed in step 1; the static test refused to write until their keys were bumped to 20261106-0977.
4. Step 2: kept main's "# 0964:" comment line in v2_mockup.py (brief section 5 says main's 0964 comments stay).

## Questions
- Are the `.mh .big` (stays 320/390) and `.stay-dates .tot` (320) mismatches present on origin/main too? Not checked (tool budget).

## Owner steps
None yet. PR #790 is not merge-ready: the mockup test must pass before the brief can continue.

## Run 2 (steps 4b to 6)

Status: blocked

Done: steps 1 to 4b. Left: steps 5 to 10 (feed URL lint, wording revert, stay-fee tests, verification and screenshots, final report, push).
Stop reason: executor 25-tool-call limit reached (executor.md). Steps 5 and 6 were not started.

### Step 4b (commit 5b049ac3)
- Main check: `test_0710_v2_mockup_match_browser.py -k stay` on origin/main: 42 passed, 0 skipped. The three failures are caused by the branch.
- stays h1 at 320 and 390: the existing `stays:.mh .big, .head h1@320/@390` pins (139.609px, height 42px, in `BOX_OVERRIDES`) won over new duplicate keys, so the new keys were reverted. The existing pins now read `100.203px` / `34.5px` with comment `0968`. Deviation: edited the existing lines, not added new ones.
- `.stay-dates .tot` at 320: scoped the branch `.stay-dates b` nowrap rule in `app2.css` to `(min-width:360px) and (max-width:1023px)`, bumped app2.css to `20261106-0977b` (base.html and static_versions.json, regenerated). Still 238px vs 280px, so the existing `stay:.stay-dates .tot@320` pin (252.031px) was set to 238px with comment `# 0977: nowrap stay dates`. Deviation: the brief's fallback, plus the CSS scope change, which did not by itself fix the width.

### Commands
- `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stay" -q --tb=line -rs | tail -30`: 42 passed, 141 deselected, 0 failed, 0 skipped (final run).
- `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short | tail -30`: 3 passed.
- Steps 5 and 6: not run.

### Open items
- Steps 5 to 10 not done. Feed URL lint (`test_layout_lint_browser.py`) and screenshots still pending.
- Main's own `stay` pins were changed (`0968` h1 and the `.tot@320` width). Main's state is no longer pinned by these values; the owner should confirm this in review.

## Run 3 (steps 5 and 6)

Status: in-progress

Done: steps 5 and 6. Left: steps 7 to 10 (stay-fee tests, verification and screenshots, final report, push).

### Step 5: feed URL cell, layout lint
- Lint command (`test_layout_lint_browser.py`, 390/768/1280 browser run): 4 passed, 0 failed, 0 skipped. No `table-squeezed` finding on `td.feed-url` appeared, so the expected CSS fix was not needed. No edit to `app2.css`, no `static_versions` regeneration, no commit for step 5.
- Step 5.3 (mockup re-check): `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stay" -q --tb=short -rs`: 42 passed, 141 deselected, 0 failed, 0 skipped.

### Step 6: validation wording revert (commit b819600c)
- Anchor grep before the edit: 6 source lines (validation.py 1, validation_i18n.py 1, host_vi_i18n.py 1, validation.go 1, golden.json 2). Two gitignored `.pyc` files also matched; not committed.
- sed applied to the five files. `grep -rn "web login required" App go` after the edit: no output.
- `grep -rln "web login required" App/tests docs/context`: no hits (no stop needed).
- `scripts/validation_golden.py` regenerated the golden: only the two sed-edited lines differ in `go/`.
- `cd go && go test ./internal/validation/...`: ok.
- `cd App && .venv/bin/python -m pytest tests/test_validation.py tests/test_validation_i18n.py tests/test_ubyport_*.py -q --tb=short -x`: 76 passed, 0 failed, 0 skipped (3 warnings, unrelated).
- Commit: `0977 step 6: restore web-service login wording (Python and Go parity)`, 5 files, 6 insertions and 6 deletions.

### Deviations
- Step 5: the brief expected `table-squeezed` findings. None occurred, so steps 5.2, 5.4 and 5.5 were skipped (nothing to change).
- Step 6: the sed also renamed the English key in `App/app/host_vi_i18n.py`. Its Vietnamese value was left unchanged, as the brief says.
- Pytest and browser runs were backgrounded because the lint run exceeded the 120 s foreground timeout. Output was read from the task file.

### Open items
- Steps 7 to 10 not started: stay-fee tests, `context_lint`, screenshots at 390/768/1280, design-system checklist, final report, push.
- Push of this run's commit is in the next step.

## Run 4 (steps 7 to 10)

Status: blocked

Done: step 7 (commit a38b7059, 4 tests added, route code unchanged); step 8 rows 1, 2, 3, 4, 5 run; step 9 report; step 10 push attempted. Left: screenshots were copied but NOT viewed (tool budget), so the per-page UX notes and the design-system checklist are not done; the invoice test and 4 mockup pins are open (below).

### Step 7: tests for filing sent/paid routes (commit a38b7059)
- Added `_filing`, `_token`, `_mark`, `_row` helpers and 4 tests at the end of `App/tests/test_stay_fee_detail.py` (no new file, no route change).
- `pytest tests/test_stay_fee_detail.py -q --tb=short -x`: 26 passed, 0 failed, 0 skipped.
- Row 3 (`pytest tests/test_invoice_*.py tests/test_stay_fee*.py`): first run with -x: 1 failed, 14 passed, 2 skipped. Full rerun without -x: 1 failed, 350 passed, 2 skipped (skips: `test_invoice_autofill.py:383` and `:452`, "set UBYHOST_SHOTS_DIR"; env not set in this row, not a code skip).
- Failure: `test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896` (layout at 320, 1024, 1280 px: `.ui-choice-card` text 0 px from edge, `input#buyer_ico` controls 10.5 px apart, `p.hint` 12 px). Not a named brief item; not fixed (would mean CSS outside the brief). Stop rule applied.

### Step 8: verification
- Row 1 `test_layout_lint_browser.py` (UBYHOST_REQUIRE_BROWSER=1): 4 passed, 0 failed, 0 skipped.
- Row 2 `test_0710_v2_mockup_match_browser.py test_host_stay_detail_layout_browser.py test_host_property_controls_browser.py -rs`: 4 failed, 191 passed. Seen failures: `overview at 390 px` (`.hl` margins 0 vs mockup 8/28/8 px), `properties at 320 px` and `properties at 390 px` (`.big, .head h1` width 150.547 vs 142.391 px). The fourth failure was not read. Skips not visible in tail output (not verified). Not changed.
- Row 3 `test_static_versions.py test_wp07_cache_heartbeats.py test_stay_fee_detail.py test_validation.py test_validation_i18n.py`: 79 passed, 0 failed, 0 skipped (1 PIL DecompressionBombWarning).
- Row 4 `go test ./internal/validation/...`: ok (cached).
- Row 5 `python3 scripts/context_lint.py`: "context lint: OK" (WARN lines are informational).

### Screenshots (copied, not viewed)
- Copied to `docs/tasks/screenshots-0977/`: stay-detail-390.png, stay-detail-768.png, stay-detail-1280.png, setup-calendar-390.png, setup-calendar-768.png, setup-calendar-1280.png (from `/tmp/shots/layout-lint/`; `setup-calendar` is the property calendars page).
- No `stay-detail-320` file exists.
- Per-page notes ("390: ...; 768: ...; 1280: ...") and the `.stay-dates .tot` check: NOT written. Design-system checklist: NOT ticked.

### Deviations
- Step 7 row 3 failure and step 8 row 2 failures are outside the brief's named pins; not fixed (executor rule: no fixing unnamed areas).
- Screenshots copied without viewing (budget at 21 tool calls).

### Questions
- Are the invoice buyer-block spacing failure and the mockup `overview`/`properties` pins present on origin/main? Not checked.

### Owner steps
None. PR #790 is not merge-ready. The next run must: view the six screenshots, fix or justify the four browser failures, and run the invoice row with `UBYHOST_SHOTS_DIR` set.

## Run 5 (step 11: triage)

Status: blocked

Done: step 11 items 1 to 5. Left: the two overview `.hl` failures (stopped per step 11.3).

Per test (main = `origin/main` worktree, same command):
- `test_v2_page_matches_mockup_styles[overview-320]` and `[overview-390]`: passes on main; fails on branch. `.hl` margin-right 0 vs 8 px, margin-bottom 0 vs 28 px, margin-left 0 vs 8 px. Caused by commit 551808e7 (`ov-title-row` wrapper around the dashboard h1). Action: STOPPED, not pinned, per step 11.3.
- `test_v2_page_matches_mockup_styles[properties-320]` and `[properties-390]`: passes on main; fails on branch. `.big, .head h1` width 150.547 vs 142.391 px, height 34.5 = 34.5 px. Caused by commit 551808e7 (`props-title-row`, page-help icon moved out of h1 on purpose). Action: pinned in `App/tests/v2_mockup.py` as `properties:.big, .head h1@320|390` (width 150.547px, height 34.5px). Deviation: commit 551808e7 has no brief number, so the comment names the commit SHA; the key is page-scoped because no properties key existed for this selector.
- `test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896`: fails on main too (Playwright `selectNodeContents` TypeError) and on branch (`guest at 320px: text 0.0 px from the edge of div.ui-choice-card (min 16)`). Pre-existing on main: known-issues line added. Not fixed.

Counts:
- Item 1 rerun (branch): 3 failed, 193 passed, 0 skipped (overview-320, overview-390, invoice).
- Item 4 rerun (`test_invoice_autofill.py`, screenshots on): 1 failed, 20 passed, 0 skipped.

Deviations: screenshots written to the session scratchpad instead of `/tmp/shots`. Worktree removed.
Owner steps: none. Overview `.hl` finding needs a decision (pin or fix the wrapper) before PR #790 can go green.

## Run 6 (step 12: overview pin, invoice buyer block spacing)

Status: blocked

Done: step 12 items 1, 2, 4 (partly), 5 and 6. Left: step 12 item 3 `test_layout_lint_browser.py` and `test_static_versions.py` (not run: executor call cap). Owner steps: none.

- Item 1: `ov-title-row` margin `0 8px 28px` confirmed (app2.css line 922). Pinned `overview:.hl@320` and `overview:.hl@390` in `App/tests/v2_mockup.py` to the measured branch values (margin 0px on all three sides), comment names 551808e7.
- Item 2 CSS (app2.css, scoped to `body.v2 .invoice-customer`): `.ui-choice-card` gets `padding:16px` (added to the existing rule); new rules after `.ui-choice-card-label>strong`: `.invoice-lookup{padding:16px}`, `.invoice-lookup-row{gap:12px}`, `.help-tip{margin-left:15px}`, `.hint{font-size:13px}`. Key `20261106-0977e` (base.html, static_versions.json regenerated). Deviation: key bumped to 0977d and 0977e because the version script refuses a changed app2.css under the same key.
- Item 2 test `test_invoice_buyer_block_spacing_0896`: 1 passed, 0 skipped (after 4 CSS iterations; the test file is unchanged).
- Item 3 run A (`test_0710_v2_mockup_match_browser.py`, `test_host_stay_detail_layout_browser.py`, `test_host_property_controls_browser.py`, invoice 0896): 196 passed, 0 failed, 0 skipped.
- Item 3 run B (`test_invoice_autofill.py`, UBYHOST_REQUIRE_BROWSER=1, shots on): 21 passed, 0 failed, 0 skipped.
- Item 3 not run: `test_layout_lint_browser.py`, `test_static_versions.py`. Status stays blocked until they pass.
- Item 4: copied invoice `-390`, `-768`, `-1280` PNGs to `docs/tasks/screenshots-0977/` (see commit).
- Item 5: known-issues line for the invoice test rewritten (origin/main Range TypeError; branch fixed in 0977).


## Run 7 (step 12 item 3: finish the tests)

Status: blocked

Done: step 12 item 3 run. Left: `scripts/context_lint.py` fails (below). Owner steps: none.

- `test_layout_lint_browser.py` (UBYHOST_REQUIRE_BROWSER=1, shots on): 4 passed, 0 failed, 0 skipped (227.7 s).
- `test_static_versions.py` and `test_wp07_cache_heartbeats.py`: 16 passed, 0 failed, 0 skipped.
- `python3 scripts/context_lint.py`: FAIL. `docs/context/known-issues.md` ~2566 tokens > cap 2500. No docs changed in this run; not fixed (fix is split or compact known-issues.md). Status stays blocked until it passes.
- Screenshots: `docs/tasks/screenshots-0977/property-calendars-{390,768,1280}.png` are copies of `/tmp/shots/layout-lint/property-detail-configured+open-{390,768,1280}.png` (property overview with the Calendars accordion opened by the lint's OPEN_ALL). The lint has no dedicated calendars-tab shot (EXTRA_ROUTES has only property-bookings, property-bookings-empty, stay-fees). The closed variant was the only one I looked at (390, shows the Calendars card "2 calendars"); the open variant was copied but not viewed. The setup-calendar-* files are the wizard and were not used.
- Brief header Status line set from `todo` to `blocked`.

## Orchestrator review (after run 7)

- Tests: mockup/stay/property/invoice spacing 196 passed; invoice autofill 21 passed; layout lint 4 passed; static versions 16 passed; all 0 skipped. Context lint OK after dropping the 0977 known-issues line (branch fixes that test; file was over its cap).
- Stay detail 390: dates and "1 guest · 2 nights" on one line, centred. Pre-existing on main: Havel FAB overlaps the right end of "Send to UbyPort". 1280: no gap between the guest table and "Police reporting".
- Invoice 390 (guest and company): buyer card padded, IČO row spaced, nothing clipped; the "?" after Company sits wide of its label (cosmetic).
- Property calendars 390 (open): the feed URL text in the expanded "URL" box starts flush at the box's left edge (no inner padding) and the caret touches "URL"; the inner "Calendars" heading repeats the accordion title. Not silenced: needs brief 0985 before merge.
- Not merge-ready until 0985 (feed URL box padding, caret gap; optionally Havel FAB clearance) is done.
