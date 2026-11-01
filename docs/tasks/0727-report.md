# 0727 report: lone stay card

Status: done

## Changes
- `App/app/static/app2.css`: step-1 rule `body.v2 .hs .card:only-child{flex:1 1 auto}` after line 245, plus `body.v2 .hs:has(> .card:only-child){margin-left:0;margin-right:0;padding-left:0;padding-right:0}` (orchestrator decision; line 310 kept).
- `App/tests/v2_mockup.py`: BOX_OVERRIDES width keys for `.hs .card`, `.kind`, `.nm`, `.meta` at 320 and 390.
- `App/app/templates/base.html`: app2.css key `20261101-0727b`; `App/tests/static_versions.json` rewritten by `--write`.
- `docs/tasks/screenshots-0727/overview-390.png`: 390 px screenshot.

## Measured widths (app)
- `.hs .card`: 280 px at 320, 350 px at 390 (matches the content width of the needs-you cards).
- `.kind`: 242 / 312 px. `.nm` and `.meta`: 182 / 252 px.

## Edge check
Read of the 390 screenshot: the lone card's left and right edges sit on the same gutters as the needs-you cards (about x 20 and 370). This is a visual check. Pixel-exact equality within 1 px was not measured separately.

## Commands (App/, last lines)
- `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_0520_overview_today.py -q --tb=line -rs | tail -6`: `30 passed in 29.15s`, 0 skipped.
- `UBYHOST_SHOTS_V2=1 ... -k screenshots`: `1 passed, 21 deselected in 13.26s`.
- `python3 scripts/design_lint.py | tail -1`: see final reply.
- `python3 scripts/context_lint.py | tail -1`: see final reply.

## Deviations
- Added the `:has` rule the coordinator asked for, which is beyond the brief's step 1.
- Descendant overrides (`.kind`, `.nm`, `.meta`) were needed because the test compares them.
- Screenshot PNGs restored and stray PNGs removed.

## Owner steps left
- None.
