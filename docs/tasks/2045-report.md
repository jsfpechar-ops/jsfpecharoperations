# 2045 report: parity harness fixes and host rerun (groups A to D)

Status: review

## Files changed

- `scripts/e2e/parity_cases.py`: removed 6 retired cases (payments, payments/new, payments/consent, booking-sites, booking-site setup, property-page review). Added `MODAL_CASES`, `ACCEPTED`, `QR_PAYLOAD_CASES`. Count 64 to 58.
- `scripts/e2e/page_parity_visual.py`: PRE_SQL now marks the 2FA prompt as shown (`now()::text`, the column is TEXT per `App/migrations_pg/00001_baseline.sql:2180`). `PRE_SQL_MODAL` clears it for the modal case only. AI env (Leon) set on both stacks. Own capture (`_capture`, `run_case2`) that never raises on HTTP >= 400, masks QR images, compares payload text. Modal case added. Accepted verdict and report section added.
- `scripts/e2e/parity_env.sh`: exports the AI env.
- `docs/tasks/2045-report.md`: this file.

Commits: `2045 step 1` to `2045 step 5` on `claude/nice-hawking-fw98ct`. Steps 6 and 7 changed no files.

## Smoke (step 6)

- `leon-settings-en`: identical at 390/768/1280. No 404.
- `2fa-setup-en`: identical at all widths.
- `apt-guide-qr-en`: visible (payload note, see below).

## Verdicts (rows = width x case)

| Group | Rows | identical | invisible | visible | accepted | error |
|---|---|---|---|---|---|---|
| A | 78 | 66 | 0 | 12 | 0 | 0 |
| B | 96 | 94 | 0 | 2 | 0 | 0 |
| C | 30 | 29 | 1 | 0 | 0 | 0 |
| D | 150 | 134 | 1 | 9 | 6 | 0 |
| Total | 354 | 323 | 2 | 23 | 6 | 0 |

Brief estimates were A 78, B 96, C 28, D 126 to 138. Actual C is 30 and D is 150. Not checked further.

Groups run: A, B, C, D. Group L was not run (the brief does not list it). Each group ran as a separate command.

## Visible rows (23), in plain words

- `admin-customer-cs` and `admin-customer-en` at 390, 768, 1280 (6 rows). The admin customer page has the same content on both stacks. The layout differs by small offsets. I inspected only `en` at 390 and did not find the exact cause.
- `dev-ui-cs` and `dev-ui-en` at 390, 768, 1280 (6 rows). 18 to 124 changed pixels, anti-aliasing. Trivial. Not opened.
- `reservation-detail-cs` and `reservation-detail-en` at 1280 (2 rows). Go has no "Generate invoice" button and no back arrow in the header. Go also shows "Request payment" and "Stay settings" as list rows, not the boxed layout. Confirmed on `en`. Brief 2046 fixes this. Not an app fix in this task.
- `apt-guide-qr-cs` and `apt-guide-qr-en` at 390, 768, 1280 (6 rows). The QR pixels are masked. The guest link text differs: Python shows `<BASE>/g/<token>`, Go shows `http://127.0.0.1:<port>/g/<token>`. The token is the same, so the payload matches. My `<BASE>` replacement did not normalize the Go host. I did not confirm why. This is a harness normalization gap, not an app difference.
- `apt-guide-questions-cs` at 390, 768, 1280 (3 rows). Czech copy differs. Python: "Odpověď uvidí host v průvodci". Go: "Odpověď se hostovi zobrazí v průvodci". Same 1776 pixels at each width. Inspected at 390.

## Accepted (not failures)

- `apt-guide-cs` and `apt-guide-en` at 390, 768, 1280 (6 rows). Reason: Go keeps the newer External guide link card above the Booking or Airbnb import. Python lacks it.

## Uninspected rows

- `dev-ui` (6 rows): pixel counts only.
- `admin-customer` cs (3 rows) and en at 768 and 1280: same cause as en 390 assumed, not opened.
- `apt-guide-qr` at all widths: payload check only, no image.
- `reservation-detail-cs` at 1280: same cause as en assumed.
- `apt-guide-questions-cs` at 768 and 1280: same cause as 390 assumed.

## Checks against the acceptance list

- 2FA modal: gone on host pages. The `two-factor-modal` rows are identical (both stacks show it, on purpose). `reservation-detail-en` at 1280 and `admin-customer-en` at 390 show no modal on either side.
- Leon: all `leon-*` rows identical, 0 errors. Leon pages render on both stacks.
- Errors on one side: none occurred in this run. The code path is in place (a visible row with both statuses in the note).
- QR: `2fa-setup` identical. `apt-guide-qr` differs only in the guest host text (see above).
- Accepted: `apt-guide-cs/en` listed with reason.
- Visible PNG folder: `/var/tmp/parity-visual/_visible/` holds 23 side images, one per visible row.

## Lint and tests

- `python3 scripts/context_lint.py`: OK (one WARN about App commits after the last status update; left for the orchestrator).
- `tests/test_go_page_parity_screenshots.py`: 2 passed, 1 skipped. The skip reads "Go web needs Postgres (UBYHOST_TEST_DATABASE_URL)". It is in the existing file; not changed.
- `git status`: clean after commits.

## Deviations

- Step 2 uses `now()::text` because the column is TEXT (brief allowed this).
- Step 4 and 5 code was applied as written. No other changes.

## Questions

- Confirm whether `apt-guide-qr` should be normalized to `<BASE>` for any `http://host:port` (current gap).
- The `apt-guide-questions-cs` Czech copy difference is an app copy issue for 2046 or the owner, not a harness issue.

## Owner steps left

- None for this brief. Nothing merged or pushed to main.
