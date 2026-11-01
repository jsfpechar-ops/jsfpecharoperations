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
