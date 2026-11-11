# 1120 report

Status: review

## 1. Files changed

```
 App/app/guest_mail_pref.py                   | new
 App/app/migrations/0045_guest_details_mail.sql | new
 App/migrations_pg/00016_guest_details_mail.sql | new
 App/tests/test_guest_mail_pref.py            | new
 App/tests/test_migrations.py                 | 45 not 44
```

## 2. Commands (last 5 lines)

`pytest tests/test_migrations.py`: `14 passed in 1.95s`

`pytest tests/test_guest_mail_pref.py`: `8 passed in 0.24s`

`pytest tests/test_migrations.py tests/test_db_*.py tests/test_goose_migrations.py`: `23 passed, 59 skipped in 3.82s`

`context_lint.py`: `context lint: OK`

## 3. §7 acceptance

- [x] Migration pair exists (0045 / 00016).
- [x] `8 passed` on `test_guest_mail_pref.py`.
- [x] migration/db/goose tests pass.
- [x] Only §3 files (+ task status/report).

## 4. Deviations

- Brief 1095 on base branch already uses migration **44** (`lead_reduced_guests`). Guest-details migration is **0045** / **00016** (version 45); pinned max **45** in `test_migrations.py`.
- `legal_acceptance.method` must be `clickwrap` (CHECK constraint); brief excerpt had `test`.

## 5. Questions

None.

## 6. Owner steps left

None for 1120.
