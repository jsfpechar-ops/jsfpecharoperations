# 0040 filter and list presentation report

Status: review

## Scope and changes

The original-red capture measured the shared title/results left-edge mismatch on
Stays, Invoices, and unset Stay Fees: 38px at 1440, 158px at 1680, 278px at
1920, and 342px at 2048. The shared CSS owner restored the centered lane; that
owner and validation own the final cross-page geometry matrix and acceptance
report.

Changed paths:

- `App/app/templates/stay_fees.html`: all-unconfigured periods use a compact,
  semantic Property/Status/Actions table. Configured and mixed tables retain
  their existing metrics; unset rows in a mixed table show explicit em dashes
  in each metric cell instead of a spanning cell.
- `App/app/templates/reservations.html`: added stable column hooks to the
  existing Stays headers/cells and a portal-link hook for measured row sizing.
  Existing values, links, and actions are preserved. The shared CSS owner owns
  the corresponding track and no-wrap rules.
- `App/app/templates/_list_filter.html`: the draft footer uses the existing
  localized `confirm.cancel` label (Cancel / Zrušit), matching Stays and
  avoiding the previously rendered raw `common.cancel` key.
- `App/app/host_i18n.py`: shortened the existing EN/CS `invoices.empty` body
  copy so the explanation appears once below the unchanged empty-state title.

## Validation and evidence

- Required Chromium run of `tests/test_host_filter_panels_browser.py` and
  `tests/test_stay_fee_list.py`: **13 passed, 0 failed, 0 skipped** on the final
  Cancel label. It covers filter draft/commit, mobile and desktop geometry,
  date/month controls, and fee list behavior.
- `tests/test_invoice_ux.py`, `tests/test_host_i18n.py`, and
  `tests/test_list_filter.py`: **20 passed, 0 failed**.
- The combined required Chromium filter, fee, and wide-lane run reported
  **14 passed, 0 failed, 0 skipped**. Validation completed the expanded
  444-combination geometry matrix with **0 lane mismatches**. Its final suite
  rerun is pending after stale-contract corrections and enhanced empty-month
  CSS; validation owns that final result and report.
- The actual unset-fee page capture is
  `/workspace/generated_images/host-wide-audit/after/after-fees-unset-en-1440.png`.
  It shows the compact three-column table, aligned setup actions, and the
  corrected Cancel label. The completed matrix and validation report carry the
  final route and viewport capture status.

No backend, query, archive, export, invoice calculation, or route behavior was
changed. No commits or pushes were made.
