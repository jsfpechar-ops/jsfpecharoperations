# 0087 report: Remove address parsing and unnecessary host explanations

Status: review

## SHAs

- Base (integration): `98c600be8e3e3cde2779e6b955f25f1c4992c1b0`
- Result: `05a495de9e9acf7eccd75a7a8f0b2d8ffda2881b`
- App baseline cited in brief: `7b27d09402f9656b0c606c131793310925936526` (main); integration branch already carries planning-only commits ahead of that app SHA.

## Summary

Restored seven-field property addresses (no `address_line` parser UI or route helper). Flattened UbyPort header fields; credential guidance moved to Guide `#ubyport-credentials`. Generic editable guest-message default. House book legal copy moved to Guide `#housebook` with a Help link on the register page. Removed external data-box login shortcut from stay-fee detail. Setup address errors keep draft field values.

## Files (§3 + required regression updates)

Application and task files per brief §3. Also updated `App/tests/test_copy_cleanup.py`, `test_ubyport_sample_pdf.py`, `test_endtoend.py` so template assertions match intentional removals (not listed in §3; narrow follow-up).

## Tests

Focused (from `App/`):

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 \
  .venv/bin/python -m pytest tests/test_address_split.py tests/test_setup_wizard.py \
  tests/test_host_property_controls_browser.py tests/test_host_copy_corrections.py tests/test_police_defaults.py -q -rs
```

Last lines: `44 passed, 1 warning in ~8s` (0 skipped).

Full suite + coverage:

```bash
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 \
  .venv/bin/python -m pytest tests -q -rs --cov=app --cov-report=term-missing --cov-fail-under=86
```

Last lines: `6 failed, 3158 passed, 6 skipped, 7 warnings in ~485s` · coverage **89.59%** (fail-under 86). Required-browser skips: **0**.

Pre-existing failures (same on integration HEAD without 0087 edits): `test_host_feedback_browser`, `test_host_quiet_dashboard_browser`, `test_host_stay_actions_browser`, three `test_host_wide_geometry_browser` stay/dashboard lane tests (action clipping / copy live-region timing in this cloud VM).

`ruff` (E9,F63,F7,F82,F401,F841): clean. `python3 scripts/context_lint.py`: OK.

## §7 acceptance

- [x] No address parsing in reachable host forms/saves; structured fields visible; house-book accordion removed; guest default editable; exports unchanged.
- [x] Task regressions in `test_host_copy_corrections.py` and updated focused tests pass.
- [x] Browser evidence EN/CS at listed widths in `docs/tasks/0087-evidence/` (synthetic data).
- [x] No schema, dependency, or live outbound calls.
- [ ] Full suite green on integration: **blocked by six pre-existing browser geometry/feedback tests** (documented above); no new failures beyond those and the three updated template tests.

## Evidence

Screenshots: `docs/tasks/0087-evidence/property-new-{360,390,760,1024,1280,1440,1680,1920,2048}-{en,cs}.png`, `housebook-{360,390,1280}-{en,cs}.png`.

## Source vs runtime boundary

Reviewed source had no literal Czech “Poslat datovou schránkou” send button; only `stay_fee_detail.html` external `mojedatovaschranka.cz` shortcut (removed). Production deploy SHA not verified here.

## Owner steps

1. Review this report and PR `task/0087-host-copy-address-corrections` → `task/production-host-ux-integration` (not `main`).
2. Confirm CI on the result SHA; note six known geometry/feedback browser failures on integration baseline.
3. After correction lane completes, stage the integration candidate with synthetic data per runbook.
4. Approve exact staged SHA before any `main`/production promotion.
