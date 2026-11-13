# 1206 report: restricted app role (K-S11)

Status: blocked
Done: steps 1 to 4 and 5 except the test-map row. Left: test-map row (step 5, last bullet).

## Files changed (git diff --stat vs 7b0c8e12)

- deploy/lightsail/scripts/pg-app-role.sql (new, 84 lines)
- deploy/lightsail/scripts/pg-app-role.sh (new, 23 lines, chmod +x)
- App/tests/test_pg_app_role_script.py (new, 9 tests)
- .github/workflows/ci.yml (+14, step "App works as the non-superuser role")
- docs/SECURITY.md, docs/LIGHTSAIL.md, docs/OPERATIONS.md, docs/ENVIRONMENT.md, docs/context/known-issues.md (K-S11 row, 102 lines)

docker-compose.yml unchanged.

## Verification

- `bash -n deploy/lightsail/scripts/pg-app-role.sh`: no output, exit 0 (pass)
- `App/.venv/bin/python -m pytest tests/test_pg_app_role_script.py -q`: 9 passed
- `pytest test_pg_app_role_script.py test_pg_cutover_script.py test_pg_backup_scripts.py -rs`: 92 passed, 0 skipped
- ci.yml parsed with venv python yaml: ok
- `python3 scripts/context_lint.py`: "context lint: OK" (WARN lines are pre-existing)
- `grep -c $'\t'` on the SQL: 0
- Not run locally: the SQL itself (no Postgres here). CI step 4 is its first run.

## Section 7 ticks

- [x] new test file passes; cutover and backup tests pass
- [x] docker-compose.yml unchanged; no file outside section 3 (plus ci.yml and docs per step 4-5)
- [x] safety property test (compose never names ubyhost_app)
- [x] ci.yml parses and the step sits after "Fail if PostgreSQL tests were skipped"
- [x] known-issues.md 102 lines; context_lint OK
- [ ] secret grep on the staged diff: not run

## Deviations

- Step 5 test-map row not done: docs/context/test-map.md has no `test_pg_cutover_script` row (no pg_ rows at all). Brief section 8 says stop on a missing anchor, so I did not invent a row.
- OPERATIONS.md runbook condensed to 6 lines (brief asked 6 to 8 lines with steps 1-9 condensed).

## Questions

- Which test-map row should carry `test_pg_app_role_script.py`? Confirm the row or name one to add.

## Owner steps left

- Unchanged from brief section "Owner steps" (steps 1-11). Nothing in production changes until the owner edits `.env`.
