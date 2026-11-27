# Report 2093: Automation choice cards with examples, stay send time & copy

- Replaced Property settings `#automation` `<select>` with the 3 `choice_card` options (`scheduled`, `immediate`, `manual`) + `?` tooltips with Mon `15:00` examples in `cs`/`en`/`vi`; aligned Onboarding Step 3 order and copy.
- Added `ScheduledSendAt` Prague timestamp display on Stay detail (`stay_detail.tmpl` and comfy lower) and updated status pills and `/guide#reporting` copy (zero em-dashes).
- Verified green with Postgres 16 across `properties`, `onboarding`, `staydetail`, `stays`, `hostweb`, `hostweb/layout`, `public`, and `web/hostweb`.
- Owner/UX follow-up: run `test_go_pages_layout_lint_browser.py` and inspect 390/768/1280 screenshots on Property settings, Wizard Step 3, and Stay detail before merging out of draft.
