# 0314 report

Status: review
Base: c541510 (0324 branch HEAD). origin/main is ee05eb7; brief said 92646d3.

## Files changed
- App/app/havel_actions.py (new): checks and card data for the five actions.
- App/app/routes/havel.py: `_feed_count`, `_card`, card path with "not prepared" fallback.
- App/app/templates/_havel_card.html (new): the card.
- App/app/static/host2.css: card rules appended; key 20261025-0314 in base.html.
- App/app/static/havel.js: Cancel handler only; key 20261025-0314 in base.html.
- App/app/templates/base.html: two cache keys.
- App/tests/test_havel_actions.py (new), App/tests/test_havel_cards_browser.py (new).
- App/tests/static_versions.json (regenerated).
- docs/design/catalog.json, docs/design/pages/havel.md.
- docs/tasks/screenshots-0314/card-stay-390.png, card-stay-1280.png, card-pin-390.png.

## Commands (last lines)
- test_havel_actions.py: `11 passed`.
- test_havel_actions, page, topics, engine: `43 passed`.
- test_havel_cards_browser.py + test_havel_browser.py: `4 passed`, 0 skipped (chromium-1243).
- test_design_guardrails_browser, test_a11y_guard_browser, test_static_versions: `17 passed`, 0 skipped.
- tests/test_havel*.py: `49 passed`.
- scripts/design_lint.py: `design lint: OK`. scripts/context_lint.py: `context lint: OK`.

## Section 7
- [x] Stay card: question title, property dot, dates with weekday, nights, guests, e-mail; inputs behind "Change"; Cancel removes card and focuses the box; primary confirm posts with _csrf to /reservations.
- [x] PIN card: red warning, danger button, posts to regenerate-pin; browser lands on guests card (test asserts URL).
- [x] Guest-link card: no form (test asserts no havel-card-form).
- [x] Not-prepared (no calendar): no card, reason sentence plus form link.
- [x] Three screenshots looked at; guards pass; lints OK; static manifest written.

## Screenshots
- card-stay-390.png: card under bubble, title "Add this stay?", facts, Change, Cancel and primary "Add stay". The fixed bottom nav and a MFA nudge overlap the lower part in this full-page capture (capture artifact, not card layout).
- card-stay-1280.png: same card at desktop width, left under the bubble, correct layout, dates "Fri 30. 10. – Sun 1. 11.".
- card-pin-390.png: red warning text, outlined danger "Make a new PIN" beside quiet Cancel. The Havel bubble also shows a red focus outline (existing focus behaviour, not from the card); brief said nothing else red.

## Deviations
- Base commit noted above (brief said 92646d3).
- havel.js and host2.css keys: brief said 20261024-0324; actual were 20261025-0324b / 0324d. Used 20261025-0314.
- Unit guest-link test patches guest_slug.link_key (the real one reads apartment_slug); route tests assert "/l/" not the token, since the real link is a slug.
- Route card uses host_i18n.lang_from_request (not request.state.lang) for cleaning words.
- browser test imports `ready` and `host` fixtures from test_havel_actions; origin yields (url, cookie, pid).
- Brief browser commands used chromium-1194; used /opt/pw-browsers/chromium-1243 per instructions.
- Test run by me modified docs/tasks/screenshots-0324 PNGs; reverted with git checkout, not committed.

## Questions
- The red focus outline on the Havel bubble in the PIN screenshot: fix in a later brief or accept?

## Owner steps left
- Run the owner steps in the brief on staging (stay add, PIN, sync without calendar, guest link).
