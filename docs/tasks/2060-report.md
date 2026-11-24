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
