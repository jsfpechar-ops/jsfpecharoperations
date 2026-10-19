# 0135 report

Status: blocked (steps 1 to 5 run; step 6 checks run, no new commit)

## Files changed
- App/app/templates/reservation_detail.html (steps 1 and 2)
- App/app/static/host.css (step 3: four dead .stay-jump rules removed)
- docs/design/catalog.json (step 3: template enforced; legacy list from lint, 47 tokens)
- App/tests/test_send_controls.py, test_wp28_ui_sweep.py, test_onboarding_followup_browser.py, test_wp28_geometry.py, test_design_stay_detail.py (step 4)

## Commits
- 6cb1a78 0135 step 1: head and CTA
- 23151f7 0135 step 2: mechanical class and role replacements
- 70afe21 0135 step 3: catalog enforces the detail template; drop stay-jump rules
- 0135 step 4: tests to v2 markup; new stay detail test

## Commands
- Step 1 compile: `ok` / `compiled`
- Step 2: `ok`
- Step 3: `python3 scripts/design_lint.py | tail -3` gives `design lint: OK`
- Step 4 pytest (8 files, no -x): `2 failed, 130 passed, 1 warning in 7.03s`

## Section 7
- [ ] not ticked: browser tests and screenshots (step 5) not run, blocked.
- [x] lint passes with reservation_detail.html enforced; host.css has no stay-jump rule.

## Deviations
- test_design_stay_detail.py: the page-level check for class="btn" and class="pill" is scoped to the `<main>` element. base.html's shared confirm and unsaved dialogs (after `</main>`) carry class="btn" and are not this page's markup. The template-level check is unchanged.
- test_wp28_ui_sweep.py line 143: `<details class="panel" id="file-by-hand">` changed to `class="ui-section"`, because step 2 renamed that element's class. The assertion is kept.
- Done: steps 1 to 4 (commits above). Left: step 4 fix in tests/test_overhaul.py, step 5, step 6.

## Step 5 (browser, 0 skipped required)
- Run: `2 failed, 23 passed, 1 skipped in 83.61s`
- FAIL tests/test_host_stay_detail_layout_browser.py:47 at 360 px: a `nav.stay-jump a` box at x=319.6, width 111.8, right edge 431 > 361. The old `.stay-jump` rule had `flex-wrap: wrap` and was deleted with Anchor H; `.ui-tabs` does not wrap. The fix needs CSS in host2.css, which section 5 forbids.
- FAIL tests/test_wp28_geometry.py:175: `#file-by-hand` padding is 0, the test wants 12. Step 2 changed `class="panel"` to `ui-section`, which has no padding in host2.css.
- SKIP tests/test_wp28_geometry.py:197 "the stay is not overdue on this date". The brief requires 0 skipped.
- Screenshots: /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135/stay-detail-en-390.png and .../stay-detail-en-1280.png. At 390 px: back link, title, meta line and property line are correct, one coral "Send to UbyPort" button, Generate invoice secondary. The four jump links render as rounded pills wrapping to two rows, so acceptance "no pill-shaped jump links" fails. At 1280 px the jump nav is not visible, and the rest of the page looks correct.
- Evidence folder restored with git checkout; nothing from it is committed.

## Step 6
- `design_lint.py`: OK. `ruff --select E9,F63,F7,F82,F401,F841`: no output.

## Blocked
- Fixed in eb11627: tests/test_overhaul.py:450 asserts `'class="panel stay-settings" id="stay-quick-edit"'`. Step 2 changed that element to `class="ui-section stay-settings"`. The file is not in brief section 3, so I stopped (section 8).
- tests/test_overhaul.py `test_demo_reset_removes_only_named_mock_data` fails with `sqlite3.IntegrityError: FOREIGN KEY constraint failed` at App/app/db.py:1375. Not in the brief's known-failure list. I did not check whether it predates this branch.

## Questions
- Owner: allow host2.css for a wrap rule on `.stay-jump`/`.ui-tabs` and padding for `.ui-section` in `#file-by-hand`, or a different fix. Also: why the jump nav is hidden at 1280 px. Also: the overdue-stay skip (date-dependent) needs a fixed date or fixture to meet 0 skipped.
- Owner: add tests/test_overhaul.py to section 3 for the one-line markup update, and say whether the demo-reset failure is known.

## Owner steps left
- None until the questions above are answered.

## 0135-fix-1 (step 5 rerun)

Status: review

- Step 1 commit 1c00fb4: `reservation_detail.html` (ui-card on `#filed-by-hand`, `#file-by-hand`), `test_wp28_ui_sweep.py`, `test_host_stay_detail_layout_browser.py` (360 px nav assertion rewritten for scrolling tabs), `test_wp28_geometry.py` (v2 deadline hook). Tests: `52 passed`, `design lint: OK`.
- Step 2 browser run: `26 passed, 1 warning in 99.61s`, 0 skipped. Overdue test runs and passes.
- Screenshots (fresh, 12:10, this run): `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135/stay-detail-en-390.png` shows four underline tabs in one row (last tab "Stay s" cut at the edge, scrolls); the hand-filing row is a bordered card; one coral button. `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135/stay-detail-en-1280.png` shows tabs under the property line, the hand-filing card, and the stay settings form. A bottom mobile nav bar overlaps the 390 capture mid-page; that is the app shell, not this change.
- Lint: ruff `--select E9,F63,F7,F82,F401,F841`: All checks passed.
- Evidence folder restored with git checkout; nothing from it is committed.
- 0135 report screenshots were stale (captured before step 3); replaced.

Owner steps left: none.
