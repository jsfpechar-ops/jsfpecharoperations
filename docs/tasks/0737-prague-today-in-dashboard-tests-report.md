# 0737 report: dashboard tests use the Prague date

Status: review

## Files changed

- `App/tests/test_0520_overview_today.py`: 5 `date.today()` calls replaced with `deadlines.local_now().date()`; `deadlines` added to `from app import ...`. `date` kept (still used as a type hint).
- `App/tests/test_dashboard_queue_copy.py`: 1 `date.today()` call replaced; `deadlines` added to the import; `date` removed from `from datetime import` (unused).

## Commands (last 5 lines)

Before (unmodified files, machine clock 23:21 UTC):
- `TZ=UTC pytest ... -q`: `FAILED ... test_task_cards_translate_time_context` / `7 failed, 11 passed in 3.48s`
- `TZ=Pacific/Pago_Pago pytest ... -q`: `FAILED ... test_task_cards_translate_time_context` / `7 failed, 11 passed in 2.22s`

After (commit `33136afc`):
- `TZ=UTC pytest ... -q`: `18 passed in 2.37s`
- `TZ=Pacific/Pago_Pago pytest ... -q`: `18 passed in 2.19s`
- `pytest ... -q -rs` (default TZ): `18 passed in 2.18s`, 0 skipped
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `python3 scripts/context_lint.py | tail -2`: see Deviations / result below

## Acceptance (brief §7)

- [x] Both files pass normally and with TZ=Pacific/Pago_Pago.

## Deviations

- Commit trailer: the brief names `Claude Opus 5.5`; the session attribution is `Claude Haiku 5.5`. Used Haiku.
- Two commits: `33136afc 0737 step 1` (code) and the report commit.

## Questions

None.

## Owner steps left

- Review and merge the PR with `scripts/merge-pr-on-green.sh` (not run by the executor).
