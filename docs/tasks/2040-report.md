# 2040 report (executor run, fourth attempt)

Status: blocked

## Done

- Step 0 (already applied) and step 0b: `scripts/e2e/parity_env.sh` now uses a UTF8 cluster at `/var/tmp/parity-pg-utf8` (commit `2040 step 0b`). Step 1 check: accepting connections, venv python present, import check `ok`, `SHOW server_encoding` = `UTF8`.
- Step 2 smoke: `admin-home 390 identical`, `{"rows": 1, ...}`.
- Step 3: `scripts/e2e/parity_cases.py` created, 64 pages.
- Step 4: `scripts/e2e/page_parity_visual.py` edited (table cases x cs/en, PARITY_GROUP, error rows, markdown report). Compiles.
- Step 5: all four groups ran.
- Step 6: 3 of the visible rows inspected (budget). Not inspected: the rest.
- Step 8: `context_lint` OK. `test_go_page_parity_screenshots.py`: 2 passed, 1 skipped (skip is in the existing file, not this change; not fixed).

## Verdicts (rows, 390/768/1280)

| Group | Rows | identical | invisible | visible | error |
|---|---|---|---|---|---|
| L (legacy, not run) | 0 | | | | |
| A | 78 | 55 | 0 | 23 | 0 |
| B | 90 | 86 | 1 | 3 | 0 |
| C | 62 | 42 | 0 | 18 | 2 |
| D | 126 | 102 | 0 | 12 | 12 |

Expected 384 rows; 356 produced. Missing 28 rows: each error case yields one error row instead of three width rows. Full per-case tables: `/var/tmp/parity-visual/report-A.md`, `report-B.md`, `report-C.md`, `report-D.md`.

## Visible differences (inspected)

- Two-factor prompt modal ("Add a second way in?"): it appears on one stack only. It is one-shot state (`PRE_SQL` clears `two_factor_prompted_at`), so the first stack to render consumes it. Example: `/var/tmp/parity-visual/booking-sites-en/booking-sites-en-390-side.png`. Likely cause of the visible rows on later pages, not yet proven.
- `booking-sites-en` at 390: the page content under the modal differs (Python shows the fee-flat list, Go shows the booking-site page). Example as above.
- `2fa-setup-en` at 390: both sides look alike at this scale; the pixel diff was not located. Example: `/var/tmp/parity-visual/2fa-setup-en/2fa-setup-en-390-side.png`.
- `admin-customer-en` at 390: the modal is on both sides, but the page underneath is laid out at different heights. Example: `/var/tmp/parity-visual/admin-customer-en/admin-customer-en-390-side.png`.

## Errors

- `payments-consent` cs and en: error, message not captured (side image missing).
- `leon-settings` cs and en, `leon-setup-{cards,import,try,switch_on,done}` cs and en: Go or Python returned 404 for `/apartments/2/leon/...` (the error text in the report names the URL and status).

## Not inspected

All other visible rows (about 50), including `apt-guide*`, `property-page-review`, `booking-site-setup`, `dev-ui`, `reservation-detail`, `onboarding-en@768`.

## Deviations

- Done: steps 0b, 1 to 5, 8 (partial). Left: step 6 for the remaining visible rows, step 7 full table (see the four report files above).

## Questions

- Error rows: why do `leon-settings` and `leon-setup-*` 404 on the Go or Python side? Owner decision or a seed fix.
- The `two_factor_prompted_at` one-shot state needs a decision: separate the 2FA prompt per stack, or clear it in the probe before each case.

## Owner or next-chat steps

- Next chat: inspect the remaining visible rows (at most 12 images), and re-run the missing rows for `payments-consent`, `leon-*`, and `apt-guide*` after fixing the error causes.
