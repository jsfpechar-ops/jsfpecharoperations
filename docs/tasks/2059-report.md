Status: blocked

## Done
- Step 1 (commit "2059 step 1"): page_parity_visual.py blurs the active element before each screenshot; JSON endpoints compared by parsed equality. Parses cleanly.
- Step 2: autofocus present in both pin templates (App/app/templates/guest/pin.html, go/internal/web/guest/templates/pin.tmpl).
- Steps 3+4 (one commit, "2059 step 3"): seed `issued()` adds stay `g-stay-issued-done` (claimed, complete synthetic guest, lock_provider ttlock, checkin/checkout hours, door code with pin_enc). Case added to GUEST_CASES. Cookie covers the new stay.
- Step 5: run with PARITY_ONLY='g-stay-issued-done*' (the filter is a glob; the exact name matches nothing).
- Step 6: H (132 rows, 114 identical, 18 visible, 0 error, 0 tracebacks) and P (12 rows, 7 identical, 2 invisible, 3 visible, 0 error).
- Step 9: context_lint OK. Guest browser and geometry tests: 57 passed, 0 skipped.

## Blocked / not run
- Step 5 stop rule: the door-code card is NOT shown on either side. Both cs 390 and 1280 show the "how many persons" form, not the door card. Python shows "Osoba 1 · uloženo", Go shows "Osoba 1 · nevyplněno". Stop per brief §8.
- Step 7 (full parity_gate.sh): not run (stop rule).
- Step 6 Go tests (2 new tests in go/internal/web/guest/fixes_2056_leftover_test.go): not written, not run.

## Visible rows (H and P reruns)
- g-stay-issued-done cs/en, all widths: card missing on both sides (see above).
- g-guide-apt and g-guide-stay cs/en, all widths: still differ (real, from 2058 areas; diff about 6k to 58k px).
- g-pin-hub-cs 390 and 1280, g-pin-hub-en 1280: still differ after blur (diff about 1000 to 1120 px). Blur did not remove the difference; cause not confirmed.
- g-leon-apt and g-leon-stay: now identical (JSON compare works).

## Notes
- Finding (App, not changed): door_codes._stay_checkin_label crashes (TypeError) when apartment.checkin_hour or checkout_hour is NULL. Seed now sets both.
- Leftover parity servers after each run: 0.
- PNG folder: /var/tmp/parity-visual/<case>-<lang>/ (e.g. g-stay-issued-done-cs/g-stay-issued-done-cs-390-side.png).
- Commit trailer used: Claude Opus 5.5 (as the brief asked).
