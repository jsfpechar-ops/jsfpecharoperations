# 0849 report

Status: blocked

## Files changed (uncommitted, branch claude/project-thread-2t66ph)

- App/app/routes/invoices.py: `date_from` in `_stay_options`, `QUICK_STAYS` and `_quick_stays` above `_last_stay_price_hint`, picker context `quick_stays`.
- App/app/templates/invoice_stay_picker.html: quick list, select kept below.
- App/app/static/host2.css: 0849 block appended. Cache-key bump skipped (owner: orchestrator does it).
- App/tests/test_invoice_stay_pages.py: three tests appended.
- Not run: base.html key, static_versions.json, test_static_versions.py --write (owner exclusions).

## Steps

- 1 done. 2 done. 3 CSS done, bump skipped. 4 done. 5 commands run, screenshot not taken (0890).
- No commits, no push, no PR (owner instruction).

## Command tails

1. `tests/test_invoice_stay_pages.py`: `12 passed in 2.28s`
2. `test_invoice_*.py test_stay_fee*.py test_static_versions.py -x`: `1 failed, 171 passed, 2 skipped`. Failure: `test_stay_fee_bulk_0845.py::test_bulk_seals_the_same_amounts_as_the_single_button` (untracked file from another run; stay_fee_filing.latest returns None).
3. `test_host_*.py test_host_geometry.py test_design_guardrails_browser.py -x -rs`: `1 failed, 31 passed, 1 skipped`. Failure: `test_host_fee_navigation.py::test_frozen_report_order_and_forms` ("Your records" missing). Skip: `test_host_copy_corrections.py:369` (browser checks, UBYHOST_REQUIRE_BROWSER not set).

Rerun of the stay-fee and fee-navigation files: 4 failed, 5 passed (same cause, in files other runs modify: stay_fees.py, stay_fee_auto.py).

## Deviations

- Stopped at §8 (test fails twice). Failures are outside this brief's files; stay-fee files are modified by concurrent runs.
- Commands 2 and 3 were not clean: 0 skipped not met (2 skips in cmd 2, 1 in cmd 3).
- `grep -n quick_stays` returns 2 lines, not 3 as the brief says (the code matches the brief text).

## Questions

- Confirm the stay-fee and fee-navigation failures are from the concurrent runs, not from this change.

## Owner steps left

- Orchestrator: bump host2.css key and run `tests/test_static_versions.py --write` once.
- Re-run commands 2 and 3 after the concurrent stay-fee work settles; screenshot at 390 px via 0890.
