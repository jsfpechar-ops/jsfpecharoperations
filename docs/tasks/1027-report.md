# 1027 report

Status: review. Steps 1 to 3 by Haiku 5.5 (blocked at step 4). An Opus executor finished steps 4, 6, 7 and 8 on branch `claude/fee-rate-dates`.

## What changed, in plain words

- Each counted night is now charged at the rate that applied on that night. Example: 30 CZK until 12 March and 40 CZK from 13 March. A guest staying 10 to 14 March pays 30 + 30 + 40 + 40 = 140 CZK.
- The council PDF shows one line per rate for a period that has a rate change (2 nights x 30 = 60, 2 nights x 40 = 80). Each line still passes the check that nights x rate = amount.
- A sealed period stores its per-rate split. A rate added later never changes a sealed period.
- `stay_fee_filing.correction_rate`: a corrected flat period keeps its sealed rate. A corrected period with a rate change is priced per night again.

## Money impact

- If an apartment has no history rows, or only the 2000-01-01 backfill row, every total is the same as before. The existing stay-fee and invoice tests pass unchanged.
- Totals change only when a dated row exists, and from 1028 on only a rate change made after that date adds one.
- A stay of more than 60 nights still owes 0.

## Root cause of the step 4 failure

`rate_segments` holds `[rate, nights]` pairs, but the reverted code read them as `(nights, rate)`. Each PDF line's amount was still right, because nights x rate gives the same product either way. The line's night count, though, was the rate, so `validate()` rejected the document with "Report totals do not match facility rows". `save()` then failed, and the pages returned HTML instead of a PDF. Fix: unpack as `rate, nights`. Validation is unchanged.

## Other fixes beyond the brief

- When bed-days removed exceed the last-day-rate nights, the extra comes off the other rates, highest first. `total_czk` is now the sum of the per-rate lines, so the PDF and the total always agree. The old code dropped the negative line, and the PDF total would not have matched.
- `record()` reads only the history rows; it no longer adds the column fallback. Before, a second identical call inserted again. The baseline row for an apartment without history now uses `previous`, the rate before the save. If that is 0 (fee not set up), the first rate applies from the beginning, as before. With no rate at all it writes nothing.
- `charge_for_reservation` takes the stay dates from its own query. Callers pass only `{"id": ...}`, so the earlier code raised KeyError (4 tests in test_stay_fee_obec_0898 failed).
- `schedule_for` returns the flat rate for an apartment without an id (an unsaved apartment, or test dicts).

## Commands (last lines)

- `pytest tests/test_stay_fee_rate_dates_1027.py`: 11 passed
- `pytest tests/test_stay_fee*.py tests/test_invoice_*.py tests/test_guest_pay*.py tests/test_property_form_save.py tests/test_static_versions.py -rs`: 428 passed, 2 skipped. Both skips are in invoice_autofill and run only when UBYHOST_SHOTS_DIR is set for screenshots; they are not stay-fee tests.
- `python3 scripts/context_lint.py`: OK

## Acceptance

- [x] Migrations 0038 / 00009, 2000-01-01 backfill
- [x] Totals unchanged with no history or the backfill only
- [x] Mixed period priced per night, PDF split per rate, sealed segments kept
- [x] A later rate row never changes a sealed period
- [x] More than 60 nights owes 0
- [x] No new dependency; SQL only through `db`

## Questions for the owner

1. Bed-day adjustments are priced at the rate on the period's last day. Removals larger than those nights come off the other rates, highest first. Is that acceptable?
2. A period that spans a rate change gets one PDF line per rate. Will the office accept that?
3. A host who turns the fee off (rate 0) and on again later: the nights in between are priced at 0. Is that acceptable?
