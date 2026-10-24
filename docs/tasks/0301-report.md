# 0301 report: stay row aligns to top

Status: review

## Files changed

- App/app/static/host2.css: added `.invoice-items-grid tbody tr[data-stay-row] { align-items: start; }` inside the `@container (max-width: 850px)` block (line 860).
- App/app/templates/base.html: host2 key `?v=20261024-0300` to `?v=20261024-0301`.
- App/tests/static_versions.json: regenerated with `--write` (35 files).

## Commands

- `.venv/bin/python tests/test_static_versions.py --write`: wrote manifest (35 files).
- `.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py tests/test_static_versions.py -q --tb=short -rs`: `8 passed, 1 warning in 22.52s`, 0 skipped.

## Section 7

- [x] The §6 commands pass.

## Deviations

- Commit made once at the end (brief §9), not per step as executor.md asks.
- No 390 px screenshot taken: the brief names no screenshot step, and the layout change was not visually verified.

## Questions

- None.

## Owner steps left

- Visually check the stay row at 1280 px and 390 px, then merge via `scripts/merge-pr-on-green.sh` (not run here).
