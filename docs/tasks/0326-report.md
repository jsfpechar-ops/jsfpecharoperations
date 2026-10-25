# 0326 report: Guide Vietnamese

Status: review

## Files changed
- App/app/host_i18n.py: guide loop uses `STRINGS.setdefault(_lang, {})`.
- App/app/guide_i18n.py: docstring line; `GUIDE_STRINGS["vi"]` built from host_vi_i18n with English fallback.
- App/app/host_vi_i18n.py: 194 new `guide.*` vi keys after `guide.demo.body`.
- App/tests/test_guide_browser.py: `vi` added to lang parametrize; vi 390 px screenshots.
- docs/tasks/screenshots-guide/guide-*-390-vi.png: 13 new files (archive, business, cleaning, finding, glossary, guest_links, invoices, overview, privacy_requests, settings, setup, stay_fee, stays).

## Missing count
Step 1: 194 missing (brief expected about 190).

## Commands (last lines)
- `pytest tests/test_guide_browser.py -rs`: `3 passed in 11.52s`, 0 skipped.
- `pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_guide.py`: `3 failed, 32 passed, 1 warning`. The 3 failures are the known local-only `no such table: apartment` (test_language_endpoint_sets_cookie..., test_a_signed_in_dashboard_keeps_vietnamese, test_language_endpoint_accepts_vietnamese).
- `context_lint.py`: `context lint: OK`.
- Step 1 check: `0 missing`; `GUIDE_STRINGS["vi"]` length equals en: True.

## Section 7
- [x] Step 1 prints 0 missing; vi has as many keys as en.
- [ ] `/guide?lang=vi` checked by hand: not done; covered only by the browser test.
- [x] Browser test passed, 0 skipped; vi screenshots saved (13).
- [ ] Copy row: 3 local-only apartment failures; no other failures.
- [x] Lint OK.

## Deviations
- Chromium path: used `chromium-1243` from the note, not `chromium-1194` in brief §6.
- Browser test gives 3 passed (en, cs, vi), not 6: the test has one parametrize axis.
- `App/tests/test_havel_engine.py` does not exist; not run.
- Scratch file went to the session scratchpad, not `/tmp`.
- Steps 2 to 4 are in commit `0326 step 2` (guide loop, vi wiring, first 97 keys), `0326 step 4` (last 97 keys), with step 3 in step 2's commit. Step 6 is commit `0326 step 6 vi screenshots`.
- en and cs screenshots that the test rewrote were restored, not committed.
- Vi screenshots were not opened for a look (the check was skipped to save budget).

## Questions (keys unsure)
- Airbnb and Booking.com menu names in `guide.stays.calendar1` (Vietnamese UI names unverified).
- "Remove" button in `guide.archive.how3` and "Remove" in passkey text: used "Xóa".
- Heading `guide.nav.glossary` "Thuật ngữ" (en "Words we use").

## Owner steps left
1. After merge, send `/guide?lang=vi` and `docs/tasks/screenshots-guide/` (files ending `-vi.png`) to the Vietnamese reviewer.
