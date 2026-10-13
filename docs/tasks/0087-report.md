# 0087 report: Remove address parsing and unnecessary host explanations

Status: review

## SHAs

- Base (integration): `98c600be8e3e3cde2779e6b955f25f1c4992c1b0`
- Result: _(updated on push after review fixes)_

## Summary

Structured `addr_*` fields only (no `address_line` parser). UbyPort header fields flattened; credential help in Guide `#ubyport-credentials`. Generic editable guest-message default. House book legal copy in Guide `#housebook`; Help link on register. External data-box shortcut removed from stay-fee detail. Unused route helpers and obsolete i18n keys removed.

## Files

Per brief §3 plus `test_copy_cleanup.py`, `test_ubyport_sample_pdf.py`, `test_endtoend.py` (template assertions). `test_police_defaults.py`: replaced police-derived open/close checks with visible-field checks and **`test_property_page_shows_mark_error_when_abbreviation_missing`** (zkratka error stays on the property page).

## Tests

Focused:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 \
  .venv/bin/python -m pytest tests/test_address_split.py tests/test_setup_wizard.py \
  tests/test_host_property_controls_browser.py tests/test_host_copy_corrections.py tests/test_police_defaults.py -q -rs
```

Browser evidence capture (optional, does not write during normal runs):

```bash
UBYHOST_CAPTURE_0087=1 UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_host_copy_corrections.py::test_copy_correction_pages_browser_evidence -q
```

Screenshots land in `docs/tasks/0087-evidence/` only when `UBYHOST_CAPTURE_0087=1`. The browser test always checks clipping/overflow, sidebar expanded/collapsed at 760–2048, edit/setup-error/stay-fee/house-book pages, and writes `measurements.json` on capture.

## Pre-existing full-suite browser failures (evidence)

Captured on integration HEAD **before** 0087 application commits: `docs/tasks/0087-evidence/integration-head-browser-failures.txt` (SHA `98c600be…`, **6 failed**, 48.29s). Same six tests still fail on the 0087 branch; CI main job skips them because `UBYHOST_REQUIRE_BROWSER` is unset.

## §7 acceptance

- [x] No address parsing; structured fields; house-book accordion removed; guest default editable; exports work.
- [x] Regressions including missing-zkratka error on property page.
- [x] Browser geometry/clipping checks EN/CS; capture via `UBYHOST_CAPTURE_0087=1` for screenshots + `measurements.json`.
- [x] No schema/dependency/live outbound calls.
- [ ] Full suite green: six integration-baseline browser tests remain (documented above).

## Evidence paths

- `docs/tasks/0087-evidence/integration-head-browser-failures.txt`
- `docs/tasks/0087-evidence/measurements.json` (with capture)
- `docs/tasks/0087-evidence/property-new|property-edit|housebook|stay-fee|setup-address-error-{width|lang}.png` (with capture)

## Owner steps

1. Review PR on `task/0087-host-copy-address-corrections` → `task/production-host-ux-integration`.
2. Re-run focused tests; optionally `UBYHOST_CAPTURE_0087=1` for fresh screenshots.
3. Stage integration candidate with synthetic data after correction lane.
4. Approve staged SHA before `main`/production.
