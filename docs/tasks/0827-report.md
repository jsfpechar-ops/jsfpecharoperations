# 0827 report

Status: review
Executor: Haiku 5.5. Not committed, not pushed.

## Files changed (working tree only)

- `App/app/static/app2.css`: block between `/* 0825 empty state centred (start/end) */` replaced with a flex chain (main column flex; `.ui-page`, `.ui-body-list` and the page wrapper flex 1 0 auto; empty block centred). No pixel constants, no negative margins.
- `App/app/templates/base.html`: `app2.css?v=20261102-0827`.
- `App/tests/static_versions.json`: rewritten by `--write` (41 files).
- Screenshots overwritten: `/mnt/project-files/records-pages/empty-<page>-<width>.png` (8 files, viewport size).
- Temp measuring and screenshot tests created and deleted.

## Measurements (empty user, EN; block centre minus centre of head bottom to viewport bottom, px; target within 24)

| Page | 390 | 1280 |
|---|---|---|
| submissions | -40 | -38 |
| invoices | -28 | -24 |
| housebook (text box) | -18 | -16 |
| stay-fees | -28 | -24 |

No vertical scroll once the security prompt closes (scrollHeight 844 and 900). The prompt is absolute-positioned and extends scroll height until it closes, so measure after it closes.

## Commands (last lines)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <brief files> -q -rs --tb=short`: `49 passed, 118 deselected in 80.68s`. 0 failed, 0 skipped.
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`: `6 passed in 0.37s`.

## Deviations

- Offsets are -16 to -40 px, outside the 24 px target on 4 of 8 shots. The orchestrator accepted these offsets as optical centre (message in this chat) and asked me not to touch the phone padding.
- Likely cause, not changed: on phone `body.v2 main` has `padding-bottom:104px` (app2.css ~line 243) while the v2 tab bar is `display:none` (app2.css line 130).
- The 0825 block measured +24 on invoices and stay-fees in my first run (the 0825 report said +52/+58). The difference is unexplained.

## Questions for the orchestrator

None open.

## Owner steps left

None. No deploy or server step.
