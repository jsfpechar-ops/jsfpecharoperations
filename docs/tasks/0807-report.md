# 0807 report

Status: blocked

## Files changed (uncommitted, per the owner's instruction)
- `App/app/static/app2.css`: appended to the end of the 0801 block (after `.setup-wizard-copy`):
  - Step a: `body.v2 .wiz-page .setup-wizard-lede{color:var(--ink)}`
  - Step b: `body.v2 .wiz-page .ui-choice-card input:focus-visible{outline:none}` and `body.v2 .wiz-page .ui-choice-card:has(input:focus-visible){outline:2px solid var(--acc);outline-offset:2px}`
- `App/tests/test_onboarding_wizard_browser.py`: step c only. The header/exit assertion in `check_controls` is now `header["x"] + header["width"] <= exit_button["x"] + 1 or header["y"] + header["height"] <= exit_button["y"] + 1`.
- `App/app/templates/base.html`: step f, `app2.css?v=20261102-0800` changed to `?v=20261102-0807`.
- `App/tests/static_versions.json`: rewritten by `python tests/test_static_versions.py --write` (41 files).
- Browser tests rewrote PNGs under `docs/tasks/0102-evidence` (left as they are, not restored).

## Step d (copy buttons): no CSS change made
The width and height check (tolerance 1 px) already passes at 360, 390 and 1280. The failing assertion at test line 1421 is the 1280 px check `abs(boxes[0]["y"] - boxes[1]["y"]) <= 1`. The three copy cards are stacked (`.setup-wizard-cards` is a single column), so the second button sits 216 px lower. Making them share a row would change the approved layout, which is a stop condition in brief section 8. Not done.

## Final test tails (section 6 and extra runs)
- `test_onboarding_wizard_browser.py` (full file, after a to c): `10 failed, 75 passed`. Later run with `-k "not guest_sharing"`: `2 failed, 71 passed, 12 deselected`. Guest_sharing run: `8 failed, 4 passed`.
- `test_0800_v2_remaining_pages_browser.py -k setup`: `36 passed, 54 deselected`.
- `test_design_setup_wizard_browser.py test_static_versions.py`: `10 passed`.
- `test_static_versions.py` after `--write`: `3 passed`.
- `python3 scripts/design_lint.py`: `design lint: OK`.
- `python3 scripts/context_lint.py`: FAIL, `ERROR docs/tasks/0808-v2-remaining-pages-geometry.md: needs a 'Status: ...' line`. This is another task's file, not touched here.

## Still red
1. Guest_sharing `test_phone_guest_sharing_and_clear_setup_actions`, all 6 `True-*` params (360, 390, 1280; en, cs): `wait_for` on `[data-page-skeleton]` times out. The element loses `hidden` but Playwright still reports it not visible. Not diagnosed; not in the brief.
2. Guest_sharing `False-1280-en` and `False-1280-cs`: the 1280 same-row y check described under step d.
3. `test_deferred_police_journey_without_javascript[1280-en]` and `[1280-cs]`: line 1178 `box["height"] >= 36` fails for the exit button (`height 24`, `width 30.6`) at 1280. A fix would be a min-height on `.setup-wizard-exit .ui-btn`, which changes the approved head. Not guessed.

## Deviations
Done: steps a, b, c, f, and the section 6 commands that were run. Step d: no change needed for the width check, and the layout question is left open. Step e: still red, see above. No commit, PR or push, because the owner said the orchestrator commits.

## Questions
1. Should the 1280 copy-button test expect stacked cards (the current layout), or should the three cards share a row?
2. Should the 1280 exit button meet the 36 px minimum, or should the test keep 24 px at desktop width?
3. What breaks the skeleton `start()` on the wizard page in the True variants?

## Owner steps left
- Answer the questions above, then the orchestrator or a new session continues from step d/e.
- The orchestrator commits the changed files listed above with `0807 step k` messages, then opens the PR.
