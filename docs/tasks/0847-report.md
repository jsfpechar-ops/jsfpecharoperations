# 0847 report

Status: review

## Files

- `App/app/routes/stay_fees.py`: `FEE_COPY_FIELDS`, `fee_copy_source`, `copy_from` on unset list rows, `POST /stay-fees/{apartment_id}/copy-setup`.
- `App/tests/test_stay_fee_copy_setup_0847.py`: new, 4 tests.
- `docs/tasks/0847-report.md`: this file.

Nothing is committed or pushed (orchestrator instruction for this session). The changes are uncommitted on `claude/project-thread-2t66ph`. No PR opened.

## Commands

1. `.venv/bin/python -m pytest tests/test_stay_fee_copy_setup_0847.py -q --tb=short -x 2>&1 | tail -30`
```
....                                                                     [100%]
4 passed in 1.68s
```
2. `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_fee_*.py -q --tb=short -x 2>&1 | tail -30`
```
..............ss........................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 75%]
.....................................................................    [100%]
283 passed, 2 skipped in 43.30s
```
The 2 skips are `tests/test_invoice_autofill.py:383` and `:452`, gated on `UBYHOST_SHOTS_DIR` (screenshot capture). Not related to this change.

## Section 7

- [x] Copy writes exactly `FEE_COPY_FIELDS` from an owned, same-municipality, active source; refuses other place, active target, foreign source, target with a filing, archived or missing source.
- [x] List rows for unset properties carry `copy_from` (set in code; no test asserts the list rows directly, only `fee_copy_source`).
- [x] Commands 1 and 2 pass.

## Deviations

- Step 1: the block was inserted after the two existing blank lines below `_fold_place`, not after one blank line plus the block's own two leading blanks. This keeps two blank lines between functions (no triple blank).
- Test fixture: the brief's filing-refusal test used a target with only a rate. Finalize refused it ("The report can't be created yet"), so no filing was made and the copy went through. Fixed by giving that target the council fields (VS, authority, account, IBAN) the finalize test's property carries. The test now also asserts the filing row exists before the copy.
- A scratch copy `/tmp/x` was created during debugging and removed.
- No CSS cache-key bump and no `test_static_versions.py --write` (no CSS touched). Orchestrator should note this at the end.

## Questions

None.

## Owner steps left

- Review the uncommitted diff, commit as `0847`, and open the PR when the orchestrator says so.
- Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
