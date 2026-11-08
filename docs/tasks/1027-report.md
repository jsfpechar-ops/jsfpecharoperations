# 1027 report (executor, Haiku 5.5)

Status: blocked. Done: steps 1 to 3, and 5 (read only). Left: step 4 (PDF rows split), 6 to 9.

## Files changed
- App/app/migrations/0038_stay_fee_rate_history.sql (new, step 1)
- App/migrations_pg/00009_stay_fee_rate_history.sql (new, step 1)
- App/app/stay_fee_rate.py (new, step 2)
- App/app/stay_fee.py (step 3: per-night amounts, scope-boundary zeroing, property_period, charge_for_reservation, _rate_segments, _apply_adjustments)
- Step 4 (hlaseni split) was committed, failed, and reverted (commits ac00bbef, a4c935bd). Net: no change.

## Commands and last lines
- Step 3: `.venv/bin/python -m pytest tests/test_stay_fee.py tests/test_stay_fee_adjustment.py -q --tb=short -x` -> `54 passed in 2.97s`
- Step 4 attempt: `tests/test_stay_fee_downloads.py tests/test_stay_fee_finalize.py` -> `10 failed, 3 passed`. Every failure is a save or PDF that returns HTML instead of a PDF. `stay_fee_filing.save` calls `hlaseni` then `render`, and `validate()` raises ValueError. I did not find the cause in budget.
- After revert: downloads + finalize + test_stay_fee + test_stay_fee_adjustment -> `67 passed in 2.88s`
- Not run: step 1 init_db check, step 7 tests (file not written), test-map row, context_lint.

## Acceptance (section 7)
- [x] Migration files 0038 / 00009 with 2000-01-01 backfill (not yet exercised by a test).
- [x] Totals unchanged for existing stay-fee tests (54 and 67 green).
- [ ] Mixed period split per rate in PDF (step 4 reverted).
- [ ] Sealed period not re-priced (step 6 not done).
- [ ] Over-60-night stay still 0: amounts zeroed in `_apply_scope_boundary`, not yet tested.
- [x] No new dependency; SQL through db.

## Stopped on (section 8)
1. Step 4 check failed twice (the 10-failure run, then the revert). Stopped per executor rule.
2. Section 8 trigger: code multiplies nights x rate for a period that may be mixed. Not touched (routes are out of scope):
   - App/app/routes/guest.py:2198 `persons` amount = `liable_nights * rate` from `charge`.
   - App/app/routes/guest.py:2301 fee summary = `days * rate` with the flat column rate.
   Both are wrong once 1028 writes history rows. Behaviour is unchanged in 1027 because no history is written yet.

## Deviations
- Step 0: brief names branch `claude/dated-rates-1027` and `checkout -B origin/main`. Work stayed on `claude/fee-rate-dates` in the given worktree, with `origin/main` merged (already up to date, no conflict).
- Step 2 `record()`: when an apartment has no history rows, I insert a baseline row at 2000-01-01 with the current column rate, then the requested row. The brief literally says the first row is stored at 2000-01-01. That would apply the new rate to earlier nights. Please confirm.

## Questions for the owner
1. Bed-day adjustments priced at the period's last-day rate: acceptable?
2. One PDF facility row per rate for a period that spans a rate change: acceptable to the office?
3. Confirm the baseline-row reading of `record()` (deviation above).

## Owner steps left
- Decide the routes/guest.py items (2198, 2301) before 1028, or reopen 1027 to fix them.
