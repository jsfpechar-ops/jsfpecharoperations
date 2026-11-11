# 1095 report: head-count H1, the server count rule

Status: review

## Files changed

Section 3 files only, plus two deviations: the version pins 43 to 44 in `App/tests/test_migrations.py` and `App/tests/test_db_postgres.py`, as 1082 and 1089 did.

## Step 1 callers

No Python caller of `expected_guest_count` or `reservation_progress` feeds it from a SELECT that names columns: all read `SELECT *` or `r.*`. The only named SELECT is `headcount.apply_declared_in` (changed in step 5). `refresh_registration_completed_at` has no copy of the rule; it goes through `reservation_progress`.

## Commands (last lines)

- `test_headcount_1095.py test_party_count_1092.py`: `68 passed` (48 new, the 22 of 1092 untouched).
- Filing row with the two files above: `13 failed, 717 passed, 1 skipped`. All 13 are `test_endtoend.py` test_06 to test_23, an order dependence that is the same on the untouched base (`13 failed, 671 passed, 1 skipped` on the 1094 checkout). `test_endtoend.py` alone: `28 passed`.
- Database row: `136 passed, 55 skipped` (Postgres-only and browser rows of that list; no local `UBYHOST_DATABASE_URL`).
- Retention and door codes: `6 failed, 219 passed`; all 6 are `[*-webkit]` cases of `test_door_code_window_browser.py` (no WebKit in this container; same before the change).
- `tests/test_guest_*.py` without browser: `765 passed`.
- `test_guest_browser_e2e.py -rs`: `55 passed`, 0 skipped.
- `test_host_redesign.py test_stay_missing_guest_rows.py` (remove empty slot): `21 passed`.
- Ruff (E9,F63,F7,F82,F401,F841): `All checks passed!`
- Go: `gofmt -l .` empty, `go vet ./...` clean, `go test ./internal/headcount/ ./internal/ubyport/ ./internal/calendar/ -count=1`: all `ok`, 0 skipped. The DB tests RAN against a local Postgres 16; the `TestRefreshRegistrationCompletedAt` table is unchanged and green, the three new reduction cases pass.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Section 7

- [x] Filing unchanged for a stay with no reduction, Python and Go, flag on and off.
- [x] The count is in no payload; a count change writes no guest row and never moves a stored `registration_completed_at`.
- [x] One shared `cases.json` (13 rows), read by Python and Go, both green.
- [x] The grep shows only `reporting.py`, `headcount.py`, `db.py`, `demo.py`, `routes/admin.py`, the archived template and the Go SELECT lines.
- [x] Flag off: route 404, nothing written, `/party` and remove empty slot as before. Default off. 1092 pins pass off and on.
- [x] Cut-off and cap refuse lowering only; one constant `NO_HOUR_CUTOFF_HOUR`.
- [x] Each block uses `cur` only and one `lock_key`; audit, mail, door code and submit run after the commit.
- [x] Audit details are numbers and `source=lead`. Retention line and ENVIRONMENT row present.
- [x] Migrations 0044 and 00015 (version 44), additive.
- [ ] Section 6 all green: see the two pre-existing failures above. Browser e2e 0 skipped. Shot: `docs/tasks/screenshots-1095/claim-reduced-390.png` (host count 4, reduction 2: the stepper shows 2).
- [x] Diff touches section 3 files only, plus the pin named above.

## Deviations

- Version pins 43 to 44 in `test_migrations.py` and `test_db_postgres.py` (not in section 3).
- Fix round 1: goose 00015 integer columns are BIGINT, as in 00014 and `db.postgres_schema_status` (the brief said INTEGER). Local Postgres 16: `test_db_postgres.py` 55 passed; after the goose Up sections, 0 column mismatches at version 44 (no goose binary here, so `pg_schema.py check` itself is left to CI).
- `App/tests/test_ticket_wallet_v3.py`: the pin on the claim template's starting number follows the new expression (`claim.declared_guests or 1`; the route fills it from the one rule).
- Steps 1 to 8 are one commit, not one commit per step.
- Two phones: tested in both orders one after the other plus a `lock_key` spy, not with two threads.
- The first baseline run overlapped my first edits; the base result above was taken again on an untouched checkout.

## Deploy order

`deploy/lightsail/scripts/deploy.sh` applies the goose files with the new image (line 219) before `docker compose up` starts the new containers (line 253), so 00015 is in place before the Go code selects `lead_reduced_guests`.

## Questions for the owner (flag stays off)

1. Cut-off with no check-in hour: midnight at the start of arrival day (built), or 15:00? A stay arriving today can then not be lowered at all. Change `NO_HOUR_CUTOFF_HOUR` only.
2. Cap of 6: every change counts, only lowering is refused at the cap. OK?
3. `/party` after the cut-off (flag on): a claimed lead's lowering is refused; the stay then files by the quiet path or the deadline cap.
