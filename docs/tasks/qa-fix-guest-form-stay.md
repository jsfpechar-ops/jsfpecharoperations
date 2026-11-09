# qa-fix-guest-form-stay: guest stay flow after saving

Source: QA findings guest-form-a/b/c, guest-checkin-v2. Status: review (draft PR).

## Verified and fixed
- **guest-form-b-05** (real): a finished stay outside the lead window answered 404 right after the last save when mail is off, because only the claim cookie kept access. `_reservation_for_guest` now also lets a device that saved a person into that same stay (signed owned-guest cookie) open the stay page, which shows the confirmation. Other devices still get the closed page.
- **guest-form-b-03, guest-checkin-07** (partly): the locked, wrong-device and already-filed pages now have "Back to your stay" and "Contact your host" (jumps to the host card). Wording in en, cs, de, es, fr, uk.
- **guest-form-b-01, -02** (soft only): a non-blocking "Check this entry" note on the stay page and the next-person form when a person this device saved shares a document number, or name plus birth date, with another person in the stay. Never rejects, never changes filing data, never names the other person.

## Deferred (not in this PR)
- Edit or delete a person after saving (owner decision: not now). b-03 main ask, checkin-07 "view/correct".
- b-04 / checkin-02 JS-off signature, b-06 draft, b-07 / checkin-05 child hint, b-08, b-09 capacity cap, b-10 / checkin-08 font and tap sizes, b-11, b-12, b-13, checkin-01 Enter key, -03, -04, -06, -09, -10: other scopes.

## Tests
`tests/test_guest_stay_confirmation.py`, `test_guest_*.py`, `test_guest_browser_e2e.py`, `test_host_geometry.py`, `test_layout_lint_browser.py` (0 skipped).
