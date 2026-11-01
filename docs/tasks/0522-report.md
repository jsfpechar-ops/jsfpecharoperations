# 0522 report

Status: blocked

## Files changed
- App/app/templates/reservations.html
- App/app/host_i18n.py
- App/app/host_vi_i18n.py

## Commands
Not run. Stopped at the tool-call checkpoint (25) after step 5.

## Steps
- Step 1 to 5: committed (eb40283, 5b991d3, 0eba939, 000d4d1, step 5 commit on this branch).

## Deviations
- Done: steps 1 to 5. Left: section 6 tests and lint, section 7 acceptance (`git diff --stat origin/main`), screenshots not taken.
- Step 2 also removed the old `stay-col-guests` th and td (step 4 asked for it). End state is the same.
- Guest column header now uses `stays.table.guest`. The cell `data-label` still says `stays.table.stay` because the brief names only the header text. Decide whether to change it.
- Keys `stays.table.arrival`, `stays.table.departure`, `stays.table.property` are new. The existing `calendar.arrival`/`calendar.departure` texts ("Check-in", "Check-out") and `stays.table.apartment` cs text ("Ubytování") did not match the brief copy, so no reuse.
- Step 4 uses `date_cz` for both dates, as the brief says. The step 4 anchor used `date_short` before.

## Questions
- Confirm the `data-label` question above.

## Owner steps left
- None yet. Orchestrator opens the PR after the tests pass.
