# 0727 report: lone stay card

Status: blocked

Acceptance (brief §7) is not met: at 390 px the lone stay card is 310 px wide, the needs-you cards are 350 px. See Blocker.

## Changes
- `App/app/static/app2.css`: added `body.v2 .hs .card:only-child{flex:1 1 auto}` after line 245 (step 1).
- `App/tests/v2_mockup.py`: BOX_OVERRIDES width keys for `.hs .card`, `.kind`, `.nm`, `.meta` at 320 and 390 (step 2).
- `App/app/templates/base.html`: app2.css key `20261101-0727` (step 3).
- `App/tests/static_versions.json`: rewritten by `--write` (step 3).
- `docs/tasks/screenshots-0727/overview-390.png`: screenshot (step 4).

## Measured widths (app, from the failure output and the screenshot)
- `.hs .card`: 240 px at 320, 310 px at 390. The brief guessed 280 and 350; the measured values were used.
- `.kind`: 202 px at 320, 272 px at 390. `.nm` and `.meta`: 142 px at 320, 212 px at 390. These children follow the card width, so they were added too.

## Blocker
`App/app/static/app2.css` line 310: `body.v2 .hs{min-width:0;max-width:100%}`. The row is capped at the main content width (350 px at 390), so its `margin:0 -20px` cannot widen it. The lone card fills the row's inner box (350 - 40 = 310 px). Not changed: the brief says to apply only step 1. Options for the owner or orchestrator: drop `max-width:100%` from line 310 for the `.hs` row, or widen the lone card with `calc(100% + 40px)`.

## Commands (App/, last lines)
- `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_0520_overview_today.py -q --tb=line -rs | tail -10`: `30 passed in 30.09s`, 0 skipped.
- `UBYHOST_SHOTS_V2=1 ... -k screenshots`: `1 passed, 21 deselected in 13.54s`.
- `tests/test_static_versions.py --write`: `wrote ... (41 files)`; then `3 passed in 0.16s`.
- `python3 scripts/design_lint.py | tail -1`: `design lint: OK`.
- `python3 scripts/context_lint.py | tail -1`: `context lint: OK`.

## Deviations
- Descendant width overrides (`.kind`, `.nm`, `.meta`) added beyond the brief's card-only entries; the test failed on them.
- Measured widths used instead of the brief's 280 and 350.
- Screenshot PNGs restored and stray PNGs removed per step 4.

## Owner steps left
- Decide the fix for line 310 (see Blocker), then rerun the commands above.
