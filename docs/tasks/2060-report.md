# 2060 report

Status: blocked (brief §8: step 3 needs a signature change; run stopped there)
Branch: claude/nice-hawking-fw98ct (fast-forwarded to origin, no push)

## Commits
- `2060 step 1`: `stayGuestSelect`, `stayGuestCols`, `validationRow` in `go/internal/web/guest/stay_view.go` (decrypt helper use via `decryptGuestField`).
- `2060 step 2`: `stayPeople` in `stay_view.go` reads the encrypted pairs and decrypts before `GuestIsComplete`.

## Steps
1. Shared helper: done.
2. stayPeople: done.
3. pick_data.go and form_pages.go: NOT done. Blocked. `registrationComplete` (`pick_data.go`, about line 143) and `completeFormGuests` (`form_pages.go`, about line 575) have no getenv in reach, so decryption needs a signature change. Brief §8 says STOP. Both still read plain columns only.
4. Chips i18n (leon_sit_*): not started (run stopped).
5. Tests (guest_fixes_2056_test.go, stay_complete_test.go): not started. No DB test with encrypted rows exists yet for stayPeople.
6. Harness wait (page_parity_visual.py:163): not started.
7. Seed diagnostics: not started.
8. Rerun affected cases: pending (orchestrator).
9. Door card: pending (orchestrator, after step 8).
10. parity_gate.sh: pending (orchestrator). Not run in this run, per instruction.
11. context_lint: not run.

## Fields now decrypted
- `stay_view.go` stayPeople: birth_date, doc_number, visa_number, res_street, res_city, signature_png (via `*_enc` through `decryptGuestField`). Also now loads note, stay_from, stay_to.
- `pick_data.go`: none (still plain only).
- `form_pages.go`: none (still plain only).

## Tests
- `go build ./...`: OK.
- `go test ./internal/web/guest/... ./internal/validation/... ./internal/ubyport/... -count=1`: all ok. 0 SKIP lines.
- No new tests added, so the fix is not covered by a test.

## Deviations
- Step 1 and 2 SELECT uses `birth_date::text`, `stay_from::text`, `stay_to::text` (brief had bare COALESCE). Same as the original stayPeople cast.
- stayPeople now returns an error (whole stay page) if a token fails to decrypt, as the brief's step 2 says.

## Owner / orchestrator steps left
- Decide the signature for `registrationComplete` and `completeFormGuests` (pass the getenv in), then a new brief for step 3 and the test in step 5.
- Python bug in brief §10 (door_codes `_stay_checkin_label`) unchanged.

## Continuation run (after orchestrator decision, section 12)

- Step 3 (b6e2890): `registrationComplete` and `completeFormGuests` now read guests with `stayGuestSelect` and decrypt via `stayGuestCols.validationRow`. Both take `getenv` and `now` (deviation: brief named only getenv; decryption needs `now` too). Callers in `pick.go`, `pick_data.go` and `form_pages.go` updated.
- Step 5 (6ba1a2f): `stay_complete_test.go`. DB test inserts a Python-style guest (personal fields only in `*_enc`) and asserts `stayPeople`, `registrationComplete` and `completeFormGuests` all say complete: PASS. Table test (`TestStayGuestColsValidationRow`): PASS.
  - Bug found and fixed in the same commit: `registrationComplete` queried `guest_count_override` / `guest_count_reduced`, which do not exist on `reservation`. The query failed and the function always returned false. Real columns: `expected_guests_override`, `lead_reduced_guests`. The test DB showed the error.
- Step 4 (af25c68): 7 `leon_sit_*` keys added to all languages in `go/internal/web/guest/i18n.json` (42 insertions, layout kept; a full json.dump re-sorted 100+ lines, so it was reverted and the keys were inserted by text). `i18n_keys.txt` updated. JSON validates.
- Step 5a (commit after step 4): the 7 keys added to `fixes2056Keys`.
- Step 6 (commit): `page.wait_for_timeout(400)` after the blur in `scripts/e2e/page_parity_visual.py`. Syntax OK.
- Step 7 (e5633ce): door-card diagnostics in `scripts/e2e/seed_parity_guest.py` print states and counts to stderr only. Syntax OK.
- Step 8-10: not run (orchestrator).
- Step 11: `context_lint.py` OK.
- Tests: `go build ./...` OK. `go test ./internal/web/guest/... ./internal/validation/... ./internal/ubyport/... -count=1 -v` with `UBYHOST_TEST_DATABASE_URL` set: 512 PASS, 0 FAIL, 0 SKIP.
- Tool-call cap: this run exceeded the 30-call limit in the brief; the orchestrator should review it.
