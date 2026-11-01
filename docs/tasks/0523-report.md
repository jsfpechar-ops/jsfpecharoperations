# 0523 report

Status: blocked
Done: steps 0 to 4 (plus the step 5 key bump and manifest). Left: step 5 test run, screenshots, browser tests, context lint, section 7 check, PR.

## Commits
- 0523 step 0: reservations.html stay cell data-label changed to stays.table.guest.
- 0523 step 1: host2.css, new block at the end, @media (min-width:1024px) scoped to .stays-view (guest 32%, pay and actions 1% nowrap, grey th background); @media (max-width:1023.98px) hides th.stay-col-pay.
- 0523 step 2: catalog.json, 3 classes added to classes and class_notes.
- 0523 step 3: payments.py payments_page reads reservation_id (digits only) into selected_reservation_id; payments.html option gets selected.
- 0523 step 4: App/tests/test_0523_stays_list.py, 7 tests.
- 0523 step 5 (partial): base.html host2.css?v=20261101-0523; static_versions.json regenerated with --write.

## Command tails
- 0522 set (test_design_stays, test_archive_stays_on_page, test_stays_empty_workspace): `27 passed in 2.01s`
- test_payments_dashboard.py: `11 passed in 1.55s`
- test_0523_stays_list.py: `7 passed in 1.83s`
- `python3 scripts/design_lint.py`: `design lint: OK`
- Not run: step 5 pytest set, browser tests, context_lint, test_static_versions.py (the --write ran, no check after it).

## Screenshots
None taken.

## Deviations
- The brief says the stays-view styles live in host2.css. No stays-view or stay-col rule existed there, so step 1 adds a new scoped block at the end of the file.
- Brief step 3 names the loop variable "stay". The template loop variable is `s`, so the option uses `s`.
- Test (e) in the brief: data-stays-housebook already exists on the export link in reservations.html; no template change was needed.
- Step 4 test data: a second owner account is created in the test and removed in a finally block.

## Questions
- Does the 32% guest column width match the approved mockup? No mockup file was given to me.

## Owner steps left
- None until the executor finishes the test run.

## Session 2 (executor, continued)
Status: blocked
Done: steps 0 to 5 (screenshots committed as `0523 step 5 screenshots`). Left: fix the geometry failures below, then rerun the browser set, then open the PR.

Commits this session: `9bc4543 0523 step 5 screenshots` (test_0523_stays_list.py gated capture test, docs/tasks/screenshots-0523/reservations-cs-1280.png and reservations-cs-390.png). No push, no PR.

## Command tails
- Server set (section 6, first command): `49 passed in 5.61s`
- Browser set (section 6, second command, -rs, no -x so every file reports): `8 failed, 28 passed in 188.46s (0:03:08)`. Skipped: none shown.
  - FAILED test_stays_fit_lane_at_every_width_and_sidebar_state: `('en/360/expanded', 328, [215.625, 239.625, 239.625, 239.625, 239.625])`
  - FAILED test_every_host_page_passes_the_layout_guard: `14 layout findings {'page-scroll': 1, 'past-right-edge': 13}`. All on `/reservations` at 1280 px: `th.stay-col-actions`, `td.ui-cell-acts.row-actions.stay-col-actions`, and the More-actions button sit past the right edge (table right edge 1322 px, viewport 1280 px).
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none about this task's files)

## Diagnosis (for the owner or orchestrator)
- At 1024 px, the stays table is 936 px wide with a 1032 px scroll width. The 0522 `host2.css` gives the same 1032 px scroll width on this fixture, so the 1024 px overflow pre-dates step 1.
- At 1280 px the table overflows by about 42 px. I did not check this against the 0522 CSS.
- Removing `white-space:nowrap` from the pay and actions cells did not change the actions cell width (137 px), so nowrap is not the cause at 1024 px.
- The 32% guest width and the `width:1%` pay and actions cells are the likely source. This is a decision, not a guess to make here: the brief says a geometry rule failing is a stop condition (section 8), and the 32% width was accepted by the owner.

## Edited assertions (section 8)
None. No existing test was edited. The browser failures above are the layout guard and the fit-lane test, not old-column selectors.

## Deviations
- The screenshot capture test asserts only that `.stays-view` exists. The overflow check was removed from it because the layout tests own that rule. The test writes PNGs only when `UBYHOST_CAPTURE_0523=1`.
- Browser set run without `-x` so all failing files show. Still 0 skipped.

## Questions
- Which should give: the 32% guest width, the nowrap on the pay and actions cells, or the 1280 px overflow (possibly pre-existing)? The owner or orchestrator should decide. Also, is `test_stays_fit_lane` at `en/360/expanded` (328 px) caused by step 1? Not yet checked.

## Owner steps left
- None until the geometry decision above is made.
