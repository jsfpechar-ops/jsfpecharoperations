# 1006 report: direct bookings host states

Status: review

## Files changed

`App/app/booking_direct.py` (decline under `db.immediate()` + `lock_key("booking_site_dates", apartment)` with a CAS `UPDATE ... WHERE status IN ('requested','expired')`, `rowcount != 1` -> `not_confirmable`; new `_mail_declined`, kind `site_booking_refunded`, key `site_booking:<id>:declined`), `App/app/booking_manage.py` (`can_retry` only for card rows, `status_key`), `App/app/templates/booking_site_setup.html` (badge uses `status_key`), `App/app/routes/payments.py` (direct flash on host cancel), `App/app/booking_webhook.py` (host confirm text `host_text_direct` for direct), `App/app/host_i18n.py` (5 keys EN + CS), `App/tests/test_booking_direct_0998.py` (4 tests).

## Commands

- Brief §6 (8 files): `144 passed, 2 warnings in 5.64s`.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py tests/test_booking_site_host_browser.py tests/test_booking_manage_browser.py -rs`: `13 passed in 244.04s`, 0 skipped.
- One-off seeded browser run (not committed): requested, expired, confirmed (paid) and declined direct rows; layout guard, no side scroll, no small targets at 390; then host cancel of the paid direct row shows the new flash and the row is `cancelled`.

## §7

- [x] Decline after confirm returns `not_confirmable`, booking stays `paid` (`test_decline_after_confirm_keeps_paid`).
- [x] Declined direct row shows "Zrušeno", no "Retry refund" (screenshots `/mnt/project-files/pr803-review/after1006/booking-site-{390,768,1280}.png`).
- [x] Host cancel of a direct booking flashes the new text (asserted in the seeded browser run).
- [x] Declined guest gets one mail (`test_decline_mails_guest`).
- [x] Each new key appears twice in `host_i18n.py`.

## Deviations

- `test_direct_confirm_host_mail_not_paid` monkeypatches `booking_webhook._host_email` (the fixture apartment has no legal entity, so no host mail was sent and the test would pass vacuously).
- Running the browser tests rewrote committed screenshots in `docs/tasks/screenshots-0819/0821/0822`; reverted, not committed.
- The after-cancel 390 screenshot caught a page transition mid-fade; the flash text was asserted in the DOM.

## Questions

None.

## Owner steps

None.
