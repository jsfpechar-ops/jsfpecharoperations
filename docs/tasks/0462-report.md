# 0462 report: batch D (done)
Status: done
Branch: task/0462-full-suite-on-postgres | Base: 2a56193

## Done
- App/tests/conftest.py `postgresql_init_db_reset`: `last_path` replaced by `seen = set()`; truncate only when `seen and path not in seen`; `seen.add(path)`. (Batch C.)
- Batch D: `test_the_seventh_message_starts_a_fresh_conversation` now stubs `havel.support_blocked` with monkeypatch. It relied on a leaked weekly `havel_support` cap from an earlier module, because `_clean` does not reset that scope. Test-only change.
- Batch D: `continue-on-error` removed from job `test-postgres-full` in `.github/workflows/ci.yml`, so the PostgreSQL job now gates merges.

## Results (batch D)
- PostgreSQL (schema reset first), `tests/test_0376_ai_gates.py tests/test_havel_page.py`: `18 passed in 14.89s` (0 failed).
- SQLite, same files, no env: `18 passed in 5.93s` (0 failed).
- SQLite, `tests/test_havel_page.py` alone: `10 passed in 2.24s`.

## Open for the owner
- Nothing blocking. Candidate K-PG04 (later): reencrypt script refuses to write on PostgreSQL without a verified backup source; its six tests in `test_data_keys.py` are sqlite_only.
