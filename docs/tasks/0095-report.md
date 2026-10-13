# 0095 report: 0087 review fixes

Status: review

## SHAs

- Base: `e96eefb7f97bc33df1f5160363acd539fea2458e` (0087 PR #381 head before this brief)
- Result: `2007d82d0a75454f179d57b1a1c8ba4ebf86bac1` 

## Summary

Password field: one hint sentence, eight-dot placeholder when a password is saved, no duplicate placeholder copy. Guest message on edit shows stored value only (blank stays blank). Evidence browser test gated on `UBYHOST_CAPTURE_0087`; geometry opens the property page before sidebar toggles; unused i18n keys removed; `test_integration_head_browser_failures_recorded` removed. Mark validation test asserts exact English error text.

## Diff stat

See `git diff --stat` at result SHA (template, i18n, setup_wizard import, copy-correction tests, police_defaults assertion, refreshed `property-edit-*` PNGs and `measurements.json`).

## Commands (last 5 lines each)

Focused §6 run:

```
50 passed, 3 warnings in 8.79s
```

Capture:

```
1 passed, 1 warning in 6.32s
```

Full suite:

```
6 failed, 3162 passed, 5 skipped, 7 warnings in 477.29s (0:07:57)
```

Ruff: `All checks passed!`

Root `python3 scripts/context_lint.py`: `context lint: OK`

Base `98c600be…` six browser failures (re-verified):

```
FAILED tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 1 warning in 19.00s
```

## §7 acceptance

- [x] Password copy and placeholder behaviour (EN/CS hints; dots only when saved; blank save keeps secret).
- [x] Guest message honest on edit; default on create unchanged.
- [x] Browser run without capture leaves evidence dir unchanged except intentional commits.
- [x] Dead import cleanup; listed unused strings removed; ruff clean.
- [x] Screenshots and geometry measurements under `docs/tasks/0087-evidence/` (capture on).
- [x] `0087-report.md` notes `test_police_defaults.py`; base six-failure proof retained.
- [ ] CI on PR #381 head (owner/orchestrator).

## Evidence paths

- `docs/tasks/0087-evidence/property-edit-{360,390,1280}-{en,cs}.png` (updated)
- `docs/tasks/0087-evidence/measurements.json`
- Other capture names from `test_copy_correction_pages_browser_evidence` (housebook, stay-fee, setup-address-error, property-new) when capture run on a clean tree.

## Deviations

None.

## Questions

None.
