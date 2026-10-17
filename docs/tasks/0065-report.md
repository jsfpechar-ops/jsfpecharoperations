# 0065 report: Review fixes for 0061, 0055, 0048

## Files

| Path | Change |
|---|---|
| `App/app/routes/invoices.py` | `fill_from_guest` always re-renders the form; shows `invoice.fill_guest.none` when no guest; defence-in-depth `fill_*` guard before `_draft` |
| `App/app/ares.py` | Cache only HTTP 404 and successful named results; cap cache at 1000 entries |
| `App/app/templating.py` | Logo map: `airbnb.svg`, `booking.svg`, `echalupy.svg` only |
| `App/app/static/platforms/` | Added cropped SVGs; removed `Vrbo.svg`, `Trip.com_logo.svg.webp`, old icon basenames |
| `App/app/host_i18n.py` | EN/CS `invoice.fill_guest.none` |
| `App/tests/test_invoice_autofill.py` | `test_fill_guest_without_complete_guest_does_not_issue` |
| `App/tests/test_ares.py` | Timeout-not-cached + 404-cached tests |
| `App/tests/test_source_badge.py` | Updated logo paths; vrbo/trip text-only; e-chalupy; stays-list screenshot test |

## Stop condition §8

Checked `invoice_form.html`: `fill_buyer_from_register` and `fill_from_guest` post to `/invoices` but are handled before issue; preview uses `formaction="/invoices/preview"`. No other non-issue POST buttons found.

## Tests

From `App/` after `git rebase origin/main`:

```
6 failed, 3140 passed, 5 skipped, 7 warnings in 465.20s
```

Failures (all browser geometry, unchanged by this task):

- `tests/test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry`
- `tests/test_host_quiet_dashboard_browser.py::test_dashboard_geometry_locales_and_screenshots`
- `tests/test_host_stay_actions_browser.py::test_stays_guest_link_copy_is_status_independent_and_token_guarded`
- `tests/test_host_wide_geometry_browser.py::test_host_wide_lanes_align`
- `tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes`
- `tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned`

Task tests: `tests/test_invoice_autofill.py`, `tests/test_ares.py`, `tests/test_source_badge.py` — 30 passed, 2 skipped (screenshot tests without `UBYHOST_SHOTS_DIR`).

Root: `python3 scripts/context_lint.py` — OK.

## Screenshots

Captured with `UBYHOST_SHOTS_DIR=/uby-0065/artifacts/screenshots` via `test_stays_list_platform_badge_screenshots`:

| Width | File |
|---|---|
| 360 | `/uby-0065/artifacts/screenshots/stays-platform-badges-360.png` |
| 390 | `/uby-0065/artifacts/screenshots/stays-platform-badges-390.png` |
| 1280 | `/uby-0065/artifacts/screenshots/stays-platform-badges-1280.png` |

Stays list (`/reservations?lang=en`) shows Airbnb, Booking.com, and e-chalupy badges using `/static/platforms/airbnb.svg`, `booking.svg`, and `echalupy.svg`.
