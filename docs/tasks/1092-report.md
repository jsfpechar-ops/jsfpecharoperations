# 1092 report: party count hole

Status: review

## Files

- `App/app/headcount.py` (new): the one guest writer of `reservation.declared_guests`.
- `App/app/db.py`: `insert_in`.
- `App/app/claim.py`: `start_claim` no longer writes `reservation`; `confirm` spends the link and applies the pending count in one `db.immediate()` block.
- `App/app/routes/guest.py`: `_set_declared_guests` wrapper, `/party` (both branches), `/another`, `claim_confirm` submit call, `/save` locked new-row path.
- `App/tests/test_party_count_1092.py` (new, 19 tests).
- Old tests changed, both for this brief's rule: `test_guest_pin.py::test_party_and_another_posts_require_pin` (count now waits on the claim row before confirm); `test_endtoend.py::test_19` (a new link on a claimed stay no longer raises the count; the test now posts `/party`).

## Commands (from `App/`)

- `pytest tests/test_party_count_1092.py`: 19 passed.
- Filing row without `test_endtoend.py`: 593 passed.
- `pytest tests/test_endtoend.py` alone: 28 passed.
- Database row: 25 passed, 55 skipped (no Postgres here).
- Guest row, no browser: 596 passed, 10 skipped.
- `python3 scripts/context_lint.py`: OK (2 warnings, both older).

## Acceptance (section 7)

- [x] `"declared_guests"` is written only in `headcount.py` (plus `demo.py`, schema).
- [x] Floor and ceiling on every guest post; one audit row per write and per floor refusal, numbers only.
- [x] `start_claim` never writes `reservation`; only a confirmed first claim applies its count.
- [x] `/save` inserts a new row only inside the locked block; `/new` and the stay page untouched.
- [x] Link spend and count are one transaction; replay and resend never change the count.
- [x] In every new block: `cur` only, the one reservation key, no `db.audit`.
- [x] No UbyPort, mail or door-code call inside `db.immediate()`.
- [ ] All section 6 rows green: see deviation 1.

## Deviations

1. The filing row as written (with `test_endtoend.py` in the same run) fails 13 `test_endtoend` tests. The same 13 fail on the clean base before any change: the file depends on an empty database and passes alone. Not touched.
2. `/save` hydrates the rows it reads with `cur` through the private `db._hydrate`, because guest fields are encrypted and `reservation_progress` needs them readable. No public helper exists.
3. `confirm` and `/save` call `lock_key` and then `apply_declared_in`, which takes the same key again (re-entrant on Postgres). Still one key.
4. `/save` also refuses when the reservation row is gone inside the lock.
5. No threaded Postgres race test: the Postgres environment is absent here.

## Questions

- `guest/claim.html` and `guest/assigned.html` prefill `party_size` from `reservation_claim.declared_guests`, which is NULL after confirm, so they fall back to 1. Harmless now (a claimed resend ignores the number), but the later head-count feature should read the reservation.
