# 1080 report

Status: review

## Files changed
- `App/app/i18n.py`, `App/app/guest_uk_i18n.py`: new key `mail_fee_update_vs` (en, cs, de, es, fr, uk), old wording.
- `App/app/mail_notify.py`: `build_fee_update` uses `mail_fee_update_vs`.
- `App/tests/test_fee_update_1078.py`: key swapped, added to `NEW_KEYS`, `vs="V"` in values; `stay` fixture gives the legal entity an IBAN and restores it at teardown.

## Commands
- Brief tests: `120 passed, 1 skipped` (skip: the Postgres-only two-connection sweep test, needs `UBYHOST_DATABASE_URL`).
- `test_a_higher_total_without_the_iban_rail_has_no_variable_symbol`: passes.
- `python3 scripts/context_lint.py`: FAIL, only because the brief lacks the nine `## 1.` to `## 9.` section headings (orchestrator file; not changed here).

## Deviations
None. Attempt 1 stopped because the rails came out `['cash']`; steps 6 and 7 fixed that.

## Questions
None.

## Owner steps left
Merge PR #869 with `scripts/merge-pr-on-green.sh` once CI is green.
