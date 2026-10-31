# 0462 report: batch D (blocked)
Status: blocked
Branch: task/0462-full-suite-on-postgres | Base: 2a56193

## Done
- App/tests/conftest.py `postgresql_init_db_reset`: `last_path` replaced by `seen = set()`; truncate only when `seen and path not in seen`; `seen.add(path)`; docstring second sentence updated. Applied as specified; not verified green (see below).

## Not done
- Step 3 (ci.yml: remove `continue-on-error` from `test-postgres-full`): not applied. The job must not gate merges while the test is red.
- Step 4 (this report as review-ready, brief `Status: review`): not set. Brief stays `in-progress`.

## Results
- PostgreSQL (schema reset first), `tests/test_0376_ai_gates.py tests/test_havel_page.py tests/test_0396_leon_opt_in.py tests/test_endtoend.py`:
  `1 failed, 56 passed in 31.81s`
  Failing: `tests/test_havel_page.py::test_the_seventh_message_starts_a_fresh_conversation` (line 101). Expected 0 failed.
- SQLite, same files, no env: `1 failed, 56 passed in 10.61s`. Same failing test.
- SQLite at base 2a56193 (conftest stashed): `1 failed, 56 passed in 10.07s`. Same failing test.

## Analysis
- The conftest wrapper returns before any logic on SQLite, so the SQLite failure cannot come from the change. It is an ordering problem that already exists in this 4-file subset at base. CI's full run may order modules differently and pass.
- On both backends the POST returns the normal form, not the "fresh conversation" text. So the seventh-exchange branch in `havel` was not reached. Hypotheses (unverified): the `limit_state` monkeypatch or `ai` client state leaking from an earlier module, or the signed history not matching the `uid` of the `host` fixture user.
- The truncate-on-new-path fix does not address this. The brief's diagnosis is incomplete for the 4-file subset.

## Open for the orchestrator
- Decide whether the next brief runs the full `tests/` order (CI-equivalent) to see if the test passes there, or diagnoses the `havel` seventh-exchange path with the module-scoped `host` fixture.
- Owner: nothing to do yet. Do not set `continue-on-error` removal until the PostgreSQL run is green twice in CI.
- Open item for later (candidate K-PG04): reencrypt script refuses to write on PostgreSQL without a verified backup source. Its six tests in `test_data_keys.py` are sqlite_only.
